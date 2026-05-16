#!/usr/bin/env python3
"""A2.1 offline training for ACOPF-guided DCOPF score parameters."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from ac_ext.experiments.analyze_dcopf_flow_scores import (  # noqa: E402
    average_precision_binary,
    build_truth_fail_label,
    compute_abs_flow,
    compute_base_limit,
    compute_continuous_flow_score,
    compute_hybrid_limit,
    compute_raw_success_fail_score,
    compute_train_percentile_limit,
    load_truth_csv,
    make_metric_safe_score,
    roc_auc_score_binary,
    topk_stats,
)


DEFAULT_MARGIN_GRID = (1.0, 1.2, 1.5, 2.0, 3.0)
DEFAULT_Q_GRID = (90.0, 95.0, 97.5, 99.0)
DEFAULT_EPSILON_GRID = (5.0, 10.0, 20.0)
DEFAULT_TOPK = (50, 100, 200, 500)
DEFAULT_LOPS = (0.005, 0.008, 0.011, 0.014, 0.017, 0.020)
DEFAULT_K_INITIAL = 200
DEFAULT_TAIL_AUDIT = 50
DEFAULT_EXPAND_FACTOR = 1.5
DEFAULT_MAX_EXPAND_ROUNDS = 3
COMPLEXITY_ORDER = {
    "raw_success_fail": 0,
    "base_margin": 1,
    "train_percentile": 2,
    "hybrid": 3,
}


@dataclass
class Candidate:
    method_family: str
    score_name: str
    score_version: str
    score: np.ndarray
    margin: float | None
    q: float | None
    epsilon: float | None
    pseudo_limit: np.ndarray | None
    n_bad_success_flow_score: int


def parse_int_list(raw: str) -> tuple[int, ...]:
    values = []
    for part in raw.split(","):
        item = part.strip()
        if item:
            values.append(int(item))
    if not values:
        raise ValueError("expected at least one integer")
    return tuple(values)


def parse_float_list(raw: str) -> tuple[float, ...]:
    values = []
    for part in raw.split(","):
        item = part.strip()
        if item:
            values.append(float(item))
    if not values:
        raise ValueError("expected at least one float")
    return tuple(values)


def float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    value_f = float(value)
    if math.isnan(value_f):
        return None
    return value_f


def float_for_json(value: Any) -> Any:
    if isinstance(value, (np.floating, float)):
        value_f = float(value)
        if math.isnan(value_f):
            return None
        if math.isinf(value_f):
            return "inf" if value_f > 0 else "-inf"
        return value_f
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def simulate_failure_label_guard(
    *,
    score: np.ndarray,
    fail_label: np.ndarray,
    k_initial: int,
    tail_audit: int,
    expand_factor: float,
    max_expand_rounds: int,
) -> dict[str, Any]:
    n_samples = int(score.shape[0])
    ranking = np.argsort(-score, kind="mergesort")
    k_current = min(n_samples, max(1, int(k_initial)))
    expand_rounds = 0
    tail_audit_count = 0
    tail_audit_failure_hits = 0
    guard_passed = False
    fallback = False
    fallback_reason = "none"
    truth_evaluated = np.zeros(n_samples, dtype=bool)

    while True:
        topk_indices = ranking[:k_current]
        if topk_indices.size > 0:
            truth_evaluated[topk_indices] = True

        audit_start = k_current
        audit_end = min(n_samples, audit_start + tail_audit)
        audit_indices = ranking[audit_start:audit_end]
        tail_audit_count += int(audit_indices.shape[0])

        if audit_indices.size > 0:
            truth_evaluated[audit_indices] = True

        hits_this_round = int(np.sum(fail_label[audit_indices]))
        tail_audit_failure_hits += hits_this_round

        if hits_this_round == 0:
            guard_passed = True
            break

        if expand_rounds >= max_expand_rounds or k_current >= n_samples:
            fallback = True
            fallback_reason = "rank_inversion_guard_exceeded"
            break

        expand_rounds += 1
        expanded = int(math.ceil(k_current * expand_factor))
        k_current = min(n_samples, max(k_current + 1, expanded))

    if not guard_passed:
        k_current = n_samples
        l0_truth_calls = n_samples
    else:
        l0_truth_calls = int(np.sum(truth_evaluated))

    final_topk = ranking[:k_current]
    fail_total = int(np.sum(fail_label))
    observed_failure_recall = float("nan")
    if fail_total > 0:
        observed_failure_recall = float(np.sum(fail_label[final_topk]) / fail_total)

    return {
        "K_initial": int(min(n_samples, max(1, int(k_initial)))),
        "K_final": int(k_current),
        "l0_truth_calls": int(l0_truth_calls),
        "tail_audit_count": int(tail_audit_count),
        "tail_audit_failure_hits": int(tail_audit_failure_hits),
        "failure_label_rank_inversion_hits": int(tail_audit_failure_hits),
        "failure_label_guard_passed": bool(guard_passed),
        "failure_label_fallback_reason": fallback_reason,
        "failure_label_fallback_flag": bool(fallback),
        "observed_failure_recall_inside_final_k": observed_failure_recall,
    }


def evaluate_subset(
    *,
    subset_name: str,
    score: np.ndarray,
    fail_label: np.ndarray,
    line_outage_prob: np.ndarray,
    mask: np.ndarray,
    topk_values: tuple[int, ...],
    k_initial: int,
    tail_audit: int,
    expand_factor: float,
    max_expand_rounds: int,
    per_lop: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if per_lop:
        lop_values = sorted({float(x) for x in line_outage_prob[mask].tolist()})
        submasks = [(lop, mask & np.isclose(line_outage_prob, lop)) for lop in lop_values]
    else:
        submasks = [(None, mask)]

    for lop, submask in submasks:
        if not np.any(submask):
            continue
        y = fail_label[submask].astype(bool, copy=False)
        score_sub = score[submask]
        metric_score = make_metric_safe_score(score_sub)
        guard = simulate_failure_label_guard(
            score=score_sub,
            fail_label=y,
            k_initial=k_initial,
            tail_audit=tail_audit,
            expand_factor=expand_factor,
            max_expand_rounds=max_expand_rounds,
        )

        row: dict[str, Any] = {
            "split": subset_name,
            "line_outage_prob": "" if lop is None else float(lop),
            "n_samples": int(y.shape[0]),
            "n_fail": int(np.sum(y)),
            "fail_rate": float(np.mean(y)),
            "AUROC": roc_auc_score_binary(y, metric_score),
            "AUPRC": average_precision_binary(y, metric_score),
            "n_inf_score": int(np.sum(np.isinf(score_sub))),
            "n_finite_score": int(np.sum(np.isfinite(score_sub))),
        }
        for k in topk_values:
            recall, precision = topk_stats(y, score_sub, k)
            row[f"top{k}_recall"] = recall
            row[f"top{k}_precision"] = precision
        row.update(guard)
        rows.append(row)

    return rows


def candidate_parameters(candidate: Candidate) -> dict[str, Any] | None:
    if candidate.method_family == "raw_success_fail":
        return None
    if candidate.pseudo_limit is None:
        return None
    return {
        "margin": float_or_none(candidate.margin),
        "q": float_or_none(candidate.q),
        "epsilon": float_or_none(candidate.epsilon),
        "pseudo_limit": [float(x) for x in candidate.pseudo_limit.tolist()],
    }


def candidate_record(
    *,
    candidate: Candidate,
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    val_per_lop_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    train_global = next(row for row in train_rows if row["split"] == "train_global")
    val_global = next(row for row in val_rows if row["split"] == "val_global")
    selection_row = {
        "max_tail_audit_failure_hits": max(
            int(row["tail_audit_failure_hits"]) for row in val_per_lop_rows
        ),
        "max_K_final": max(int(row["K_final"]) for row in val_per_lop_rows),
        "mean_l0_truth_calls": float(
            statistics.mean(float(row["l0_truth_calls"]) for row in val_per_lop_rows)
        ),
        "mean_top200_recall": float(
            statistics.mean(float(row["top200_recall"]) for row in val_per_lop_rows)
        ),
        "mean_AUPRC": float(
            statistics.mean(float(row["AUPRC"]) for row in val_per_lop_rows)
        ),
        "complexity_rank": int(COMPLEXITY_ORDER[candidate.method_family]),
    }
    selection_tuple = (
        selection_row["max_tail_audit_failure_hits"],
        selection_row["max_K_final"],
        selection_row["mean_l0_truth_calls"],
        -selection_row["mean_top200_recall"],
        -selection_row["mean_AUPRC"],
        selection_row["complexity_rank"],
        candidate.score_name,
    )

    return {
        "candidate": candidate,
        "train_global": train_global,
        "val_global": val_global,
        "val_per_lop": val_per_lop_rows,
        "selection_row": selection_row,
        "selection_tuple": selection_tuple,
    }


def append_metric_rows(
    rows: list[dict[str, Any]],
    candidate: Candidate,
    subset_rows: list[dict[str, Any]],
) -> None:
    for row in subset_rows:
        merged = {
            "score_name": candidate.score_name,
            "score_version": candidate.score_version,
            "method_family": candidate.method_family,
            "margin": candidate.margin,
            "q": candidate.q,
            "epsilon": candidate.epsilon,
            "n_bad_success_flow_score": candidate.n_bad_success_flow_score,
        }
        merged.update(row)
        rows.append(merged)


def markdown_metric(value: Any, ndigits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, str):
        return value
    value_f = float(value)
    if math.isnan(value_f):
        return "N/A"
    if math.isinf(value_f):
        return "inf" if value_f > 0 else "-inf"
    return f"{value_f:.{ndigits}f}"


def build_report(
    *,
    args: argparse.Namespace,
    npz_path: Path,
    truth_csv_path: Path,
    best_overall: dict[str, Any],
    best_trained: dict[str, Any],
    raw_record: dict[str, Any],
) -> str:
    best_candidate: Candidate = best_overall["candidate"]
    trained_candidate: Candidate = best_trained["candidate"]

    def param_text(record: dict[str, Any]) -> str:
        candidate: Candidate = record["candidate"]
        params = candidate_parameters(candidate)
        if not params:
            return "`dcopf_failed -> +inf`, solved -> `0`"
        return (
            f"`margin={params['margin']}`, `q={params['q']}`, "
            f"`epsilon={params['epsilon']}`"
        )

    raw_is_best = best_candidate.method_family == "raw_success_fail"
    hardest_rows = sorted(
        best_trained["val_per_lop"],
        key=lambda row: (
            int(row["tail_audit_failure_hits"]),
            int(row["K_final"]),
            float(row["fail_rate"]),
            -float(row["top100_recall"]),
            -float(row["top50_recall"]),
        ),
        reverse=True,
    )
    hardest_text = ", ".join(
        f"`lop={row['line_outage_prob']}` (K_final={row['K_final']}, top100_recall={markdown_metric(row['top100_recall'])}, top50_recall={markdown_metric(row['top50_recall'])})"
        for row in hardest_rows[:3]
    )

    next_step = (
        "Recommend A3 wrapper-level `proxy_mode=\"dcopf_optimized\"` design only after one "
        "more offline confirmation pass, because the best trained physics score already clears "
        "the failure-label guard constraints."
        if not raw_is_best
        else "Do not enter A3 yet. The trained physics score did not beat the raw success/fail "
        "baseline on the validation selection rule. The next method step should be branch-weight "
        "training or formulation-level coefficient/bias optimization."
    )
    comparison_text = (
        "- `raw_success_fail` remained the best overall candidate on the validation selection rule.\n"
        "- This should be reported directly rather than forcing a trained score win.\n"
        "- A1-Guard already makes raw DCOPF very strong, so A2.1 may only match or narrowly trail the raw baseline."
        if raw_is_best
        else "- A trained physics score beat the raw success/fail baseline on the validation selection rule.\n"
        "- This indicates that continuous DCOPF flow stress adds useful ranking signal after A1-Guard objective alignment."
    )

    return f"""# A2.1 DCOPF Score Training Report v001

## 1. Purpose

- A2.1 ACOPF-guided DCOPF score-parameter training.
- Inspired by ACOPF-guided DCOPF parameter optimization literature.
- The target here is failure-screening / truth-call reduction, not dispatch error.

## 2. Data

- NPZ path: `{npz_path}`
- truth CSV path: `{truth_csv_path}`
- train seeds: `{','.join(str(x) for x in args.train_seeds)}`
- validation seeds: `{','.join(str(x) for x in args.val_seeds)}`
- lops included: `{','.join(str(x) for x in DEFAULT_LOPS)}`

## 3. Candidate score families

- `raw_success_fail`
- `base_margin`
- `train_percentile`
- `hybrid`

## 4. Selection rule

- failure-label guard metrics are prioritized over AUPRC.
- Selection order:
- minimize validation per-lop max `tail_audit_failure_hits`
- minimize validation per-lop max `K_final`
- minimize validation mean `l0_truth_calls`
- maximize validation mean `top200_recall`
- maximize validation mean `AUPRC`
- prefer lower-complexity score families on ties

## 5. Best overall result

- candidate: `{best_candidate.score_name}`
- method family: `{best_candidate.method_family}`
- parameters: {param_text(best_overall)}
- validation mean AUPRC across lops: `{markdown_metric(best_overall['selection_row']['mean_AUPRC'])}`
- validation mean top200 recall across lops: `{markdown_metric(best_overall['selection_row']['mean_top200_recall'])}`
- validation max K_final across lops: `{best_overall['selection_row']['max_K_final']}`
- validation mean l0_truth_calls across lops: `{markdown_metric(best_overall['selection_row']['mean_l0_truth_calls'])}`

## 6. Best trained physics score

- candidate: `{trained_candidate.score_name}`
- method family: `{trained_candidate.method_family}`
- parameters: {param_text(best_trained)}
- validation mean AUPRC across lops: `{markdown_metric(best_trained['selection_row']['mean_AUPRC'])}`
- validation mean top200 recall across lops: `{markdown_metric(best_trained['selection_row']['mean_top200_recall'])}`
- validation max K_final across lops: `{best_trained['selection_row']['max_K_final']}`
- validation mean l0_truth_calls across lops: `{markdown_metric(best_trained['selection_row']['mean_l0_truth_calls'])}`

## 7. Comparison to raw_success_fail

{comparison_text}

## 8. Per-lop findings

- hardest validation lops under the best trained physics score: {hardest_text}
- per-lop guard performance is the primary reason candidates are accepted or rejected

## 9. Next step recommendation

- {next_step}
"""


def build_selection_payload(record: dict[str, Any]) -> dict[str, Any]:
    candidate: Candidate = record["candidate"]
    return {
        "score_name": candidate.score_name,
        "score_version": candidate.score_version,
        "method_family": candidate.method_family,
        "parameters": candidate_parameters(candidate),
        "validation_global": {
            key: float_for_json(value) for key, value in record["val_global"].items()
        },
        "validation_per_lop": [
            {key: float_for_json(value) for key, value in row.items()}
            for row in record["val_per_lop"]
        ],
        "train_global": {
            key: float_for_json(value) for key, value in record["train_global"].items()
        },
        "selection_metrics": {
            key: float_for_json(value) for key, value in record["selection_row"].items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--npz",
        type=Path,
        default=Path("ac_ext/experiments/out/dcopf_flow_features_case118.npz"),
    )
    parser.add_argument(
        "--truth-csv",
        type=Path,
        default=Path("ac_ext/experiments/out/ml_training_data_case118.csv"),
    )
    parser.add_argument("--train-seeds", type=parse_int_list, default=(7, 42, 100, 200))
    parser.add_argument("--val-seeds", type=parse_int_list, default=(300,))
    parser.add_argument("--case", default="case118")
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("ac_ext/experiments/out/dcopf_score_training_case118_v001"),
    )
    parser.add_argument("--margins", type=parse_float_list, default=DEFAULT_MARGIN_GRID)
    parser.add_argument("--percentiles", type=parse_float_list, default=DEFAULT_Q_GRID)
    parser.add_argument("--epsilons", type=parse_float_list, default=DEFAULT_EPSILON_GRID)
    parser.add_argument("--topk", type=parse_int_list, default=DEFAULT_TOPK)
    parser.add_argument("--k-initial", type=int, default=DEFAULT_K_INITIAL)
    parser.add_argument("--tail-audit", type=int, default=DEFAULT_TAIL_AUDIT)
    parser.add_argument("--expand-factor", type=float, default=DEFAULT_EXPAND_FACTOR)
    parser.add_argument("--max-expand-rounds", type=int, default=DEFAULT_MAX_EXPAND_ROUNDS)
    args = parser.parse_args()

    out_dir = args.out_prefix.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    params_path = out_dir / f"dcopf_score_params_{args.case}_v001.json"
    results_csv_path = out_dir / f"dcopf_score_training_results_{args.case}_v001.csv"
    report_md_path = out_dir / f"dcopf_score_training_report_{args.case}_v001.md"

    d = np.load(args.npz)
    truth = load_truth_csv(args.truth_csv)

    sample_id = np.asarray(d["sample_id"], dtype=np.int64)
    seed_arr = np.asarray(d["seed"], dtype=np.int64)
    lop_arr = np.asarray(d["line_outage_prob"], dtype=np.float64)
    if not np.array_equal(sample_id, truth["sample_id"]):
        raise ValueError("sample_id mismatch between NPZ and truth CSV")
    if not np.array_equal(seed_arr, truth["seed"]):
        raise ValueError("seed mismatch between NPZ and truth CSV")
    if not np.allclose(lop_arr, truth["line_outage_prob"]):
        raise ValueError("line_outage_prob mismatch between NPZ and truth CSV")

    truth_success = np.asarray(truth["truth_success"], dtype=bool)
    truth_score = np.asarray(truth["truth_s_any"], dtype=np.float64)
    truth_fail_label = build_truth_fail_label(truth_success, truth_score)
    npz_fail_label = np.asarray(d["acopf_fail_label"], dtype=bool)
    if not np.array_equal(npz_fail_label, truth_fail_label):
        raise ValueError("acopf_fail_label mismatch between NPZ and truth CSV-derived label")

    success = np.asarray(d["dcopf_success"], dtype=bool)
    flow_valid = np.asarray(d["flow_valid"], dtype=bool)
    if not np.all(flow_valid):
        raise ValueError("flow_valid contains false entries; v001 expects fully valid artifact")

    branch_status = np.asarray(d["branch_status"], dtype=bool)
    abs_flow = compute_abs_flow(
        pf=np.asarray(d["PF"], dtype=np.float64),
        pt=np.asarray(d["PT"], dtype=np.float64),
        branch_status=branch_status,
    )
    basecase_pf = np.asarray(d["basecase_PF"], dtype=np.float64)
    basecase_pt = np.asarray(d["basecase_PT"], dtype=np.float64)

    train_mask = np.isin(seed_arr, np.asarray(args.train_seeds, dtype=np.int64))
    val_mask = np.isin(seed_arr, np.asarray(args.val_seeds, dtype=np.int64))
    if not np.any(train_mask):
        raise ValueError("train split is empty")
    if not np.any(val_mask):
        raise ValueError("validation split is empty")

    candidates: list[Candidate] = []
    candidates.append(
        Candidate(
            method_family="raw_success_fail",
            score_name="raw_success_fail",
            score_version="dcopf_raw_success_fail_v001",
            score=compute_raw_success_fail_score(success),
            margin=None,
            q=None,
            epsilon=None,
            pseudo_limit=None,
            n_bad_success_flow_score=0,
        )
    )

    for epsilon in args.epsilons:
        for margin in args.margins:
            limit = compute_base_limit(
                basecase_pf=basecase_pf,
                basecase_pt=basecase_pt,
                margin=float(margin),
                epsilon=float(epsilon),
            )
            score, bad = compute_continuous_flow_score(
                success=success,
                abs_flow=abs_flow,
                pseudo_limit=limit,
            )
            candidates.append(
                Candidate(
                    method_family="base_margin",
                    score_name=f"base_margin_m{margin:g}_e{epsilon:g}",
                    score_version="dcopf_base_margin_v001",
                    score=score,
                    margin=float(margin),
                    q=None,
                    epsilon=float(epsilon),
                    pseudo_limit=limit,
                    n_bad_success_flow_score=bad,
                )
            )

    for epsilon in args.epsilons:
        for q in args.percentiles:
            limit = compute_train_percentile_limit(
                abs_flow=abs_flow,
                success=success,
                train_mask=train_mask,
                q=float(q),
                epsilon=float(epsilon),
            )
            score, bad = compute_continuous_flow_score(
                success=success,
                abs_flow=abs_flow,
                pseudo_limit=limit,
            )
            candidates.append(
                Candidate(
                    method_family="train_percentile",
                    score_name=f"train_percentile_q{q:g}_e{epsilon:g}",
                    score_version="dcopf_train_percentile_v001",
                    score=score,
                    margin=None,
                    q=float(q),
                    epsilon=float(epsilon),
                    pseudo_limit=limit,
                    n_bad_success_flow_score=bad,
                )
            )

    for epsilon in args.epsilons:
        for margin in args.margins:
            for q in args.percentiles:
                limit = compute_hybrid_limit(
                    basecase_pf=basecase_pf,
                    basecase_pt=basecase_pt,
                    abs_flow=abs_flow,
                    success=success,
                    train_mask=train_mask,
                    margin=float(margin),
                    q=float(q),
                    epsilon=float(epsilon),
                )
                score, bad = compute_continuous_flow_score(
                    success=success,
                    abs_flow=abs_flow,
                    pseudo_limit=limit,
                )
                candidates.append(
                    Candidate(
                        method_family="hybrid",
                        score_name=f"hybrid_m{margin:g}_q{q:g}_e{epsilon:g}",
                        score_version="dcopf_hybrid_v001",
                        score=score,
                        margin=float(margin),
                        q=float(q),
                        epsilon=float(epsilon),
                        pseudo_limit=limit,
                        n_bad_success_flow_score=bad,
                    )
                )

    metric_rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    raw_record: dict[str, Any] | None = None

    for candidate in candidates:
        train_rows = evaluate_subset(
            subset_name="train_global",
            score=candidate.score,
            fail_label=truth_fail_label,
            line_outage_prob=lop_arr,
            mask=train_mask,
            topk_values=tuple(args.topk),
            k_initial=args.k_initial,
            tail_audit=args.tail_audit,
            expand_factor=args.expand_factor,
            max_expand_rounds=args.max_expand_rounds,
            per_lop=False,
        )
        val_rows = evaluate_subset(
            subset_name="val_global",
            score=candidate.score,
            fail_label=truth_fail_label,
            line_outage_prob=lop_arr,
            mask=val_mask,
            topk_values=tuple(args.topk),
            k_initial=args.k_initial,
            tail_audit=args.tail_audit,
            expand_factor=args.expand_factor,
            max_expand_rounds=args.max_expand_rounds,
            per_lop=False,
        )
        val_per_lop_rows = evaluate_subset(
            subset_name="val_per_lop",
            score=candidate.score,
            fail_label=truth_fail_label,
            line_outage_prob=lop_arr,
            mask=val_mask,
            topk_values=tuple(args.topk),
            k_initial=args.k_initial,
            tail_audit=args.tail_audit,
            expand_factor=args.expand_factor,
            max_expand_rounds=args.max_expand_rounds,
            per_lop=True,
        )

        append_metric_rows(metric_rows, candidate, train_rows)
        append_metric_rows(metric_rows, candidate, val_rows)
        append_metric_rows(metric_rows, candidate, val_per_lop_rows)

        record = candidate_record(
            candidate=candidate,
            train_rows=train_rows,
            val_rows=val_rows,
            val_per_lop_rows=val_per_lop_rows,
        )
        records.append(record)
        if candidate.method_family == "raw_success_fail":
            raw_record = record

    if raw_record is None:
        raise RuntimeError("raw_success_fail baseline missing")

    best_overall = min(records, key=lambda item: item["selection_tuple"])
    trained_records = [item for item in records if item["candidate"].method_family != "raw_success_fail"]
    best_trained = min(trained_records, key=lambda item: item["selection_tuple"])

    best_overall_name = best_overall["candidate"].score_name
    best_trained_name = best_trained["candidate"].score_name
    for row in metric_rows:
        row["is_best_overall"] = row["score_name"] == best_overall_name
        row["is_best_trained_physics"] = row["score_name"] == best_trained_name

    write_csv(results_csv_path, metric_rows)

    report_text = build_report(
        args=args,
        npz_path=args.npz,
        truth_csv_path=args.truth_csv,
        best_overall=best_overall,
        best_trained=best_trained,
        raw_record=raw_record,
    )
    report_md_path.write_text(report_text, encoding="utf-8")

    top_level_parameters = candidate_parameters(best_overall["candidate"])
    payload = {
        "case": args.case,
        "score_version": "dcopf_score_case118_v001",
        "stage": "A2.1",
        "method_family": best_overall["candidate"].method_family,
        "train_seeds": [int(x) for x in args.train_seeds],
        "validation_seeds": [int(x) for x in args.val_seeds],
        "unseen_benchmark_seeds": [901, 902, 903],
        "score_formula": "if dcopf_failed: high_risk else max(abs_flow / L_j - 1)",
        "failure_handling": "dcopf_failed -> +inf for ranking",
        "selected_by": (
            "lexicographic validation selection: per-lop max tail_audit_failure_hits, "
            "per-lop max K_final, mean l0_truth_calls, mean top200_recall, mean AUPRC, "
            "then lower method complexity"
        ),
        "best_overall": build_selection_payload(best_overall),
        "best_trained_physics": build_selection_payload(best_trained),
        "parameters": top_level_parameters,
        "notes": [
            "A1-Guard aligned Level-0 objective before A2 training.",
            "A2.1 trains DCOPF-derived score parameters, not black-box ML.",
            "This file is offline only and is not yet connected to proxy_mode=dcopf_optimized.",
        ],
    }
    params_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"wrote params: {params_path}")
    print(f"wrote results: {results_csv_path}")
    print(f"wrote report: {report_md_path}")
    print(f"best_overall: {best_overall_name}")
    print(f"best_trained_physics: {best_trained_name}")


if __name__ == "__main__":
    main()
