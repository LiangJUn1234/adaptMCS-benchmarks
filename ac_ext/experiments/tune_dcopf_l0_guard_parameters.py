#!/usr/bin/env python3
"""A2.2a offline tuning of failure-label Level-0 guard parameters."""

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
    build_truth_fail_label,
    compute_abs_flow,
    compute_base_limit,
    compute_continuous_flow_score,
    compute_hybrid_limit,
    compute_raw_success_fail_score,
    compute_train_percentile_limit,
    load_truth_csv,
    topk_stats,
)
from ac_ext.experiments.train_dcopf_score_parameters import (  # noqa: E402
    simulate_failure_label_guard,
)


@dataclass(frozen=True)
class ScoreCandidate:
    score_name: str
    method_family: str
    score: np.ndarray
    score_priority: int


def parse_int_list(raw: str) -> tuple[int, ...]:
    vals = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not vals:
        raise ValueError("expected at least one integer")
    return tuple(vals)


def parse_float_list(raw: str) -> tuple[float, ...]:
    vals = [float(x.strip()) for x in raw.split(",") if x.strip()]
    if not vals:
        raise ValueError("expected at least one float")
    return tuple(vals)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    cols: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                cols.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def maybe_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    try:
        out = float(v)
    except Exception:
        return None
    if math.isnan(out):
        return None
    return out


def build_score_from_spec(
    *,
    spec: dict[str, Any],
    success: np.ndarray,
    abs_flow: np.ndarray,
    basecase_pf: np.ndarray,
    basecase_pt: np.ndarray,
    train_mask: np.ndarray,
) -> np.ndarray:
    family = str(spec.get("method_family"))
    margin = maybe_float(spec.get("margin"))
    q = maybe_float(spec.get("q"))
    epsilon = maybe_float(spec.get("epsilon"))

    if family == "raw_success_fail":
        return compute_raw_success_fail_score(success)

    if epsilon is None:
        epsilon = 10.0

    if family == "base_margin":
        if margin is None:
            margin = 1.2
        limit = compute_base_limit(
            basecase_pf=basecase_pf,
            basecase_pt=basecase_pt,
            margin=float(margin),
            epsilon=float(epsilon),
        )
    elif family == "train_percentile":
        if q is None:
            q = 95.0
        limit = compute_train_percentile_limit(
            abs_flow=abs_flow,
            success=success,
            train_mask=train_mask,
            q=float(q),
            epsilon=float(epsilon),
        )
    elif family == "hybrid":
        if margin is None:
            margin = 1.2
        if q is None:
            q = 95.0
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
    else:
        raise ValueError(f"unsupported method_family: {family}")

    score, _ = compute_continuous_flow_score(
        success=success,
        abs_flow=abs_flow,
        pseudo_limit=np.asarray(limit, dtype=np.float64),
    )
    return score


def load_top_trained_specs(results_csv: Path, topn: int) -> list[dict[str, Any]]:
    by_name: dict[str, list[dict[str, str]]] = {}
    with results_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("split") != "val_per_lop":
                continue
            name = row["score_name"]
            by_name.setdefault(name, []).append(row)

    scored: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for name, rows in by_name.items():
        family = rows[0].get("method_family", "")
        if family == "raw_success_fail":
            continue
        max_tail_hits = max(int(float(r["tail_audit_failure_hits"])) for r in rows)
        max_k = max(int(float(r["K_final"])) for r in rows)
        mean_l0 = statistics.mean(float(r["l0_truth_calls"]) for r in rows)
        mean_top200 = statistics.mean(float(r["top200_recall"]) for r in rows)
        mean_auprc = statistics.mean(float(r["AUPRC"]) for r in rows)
        spec = {
            "score_name": name,
            "method_family": family,
            "margin": maybe_float(rows[0].get("margin")),
            "q": maybe_float(rows[0].get("q")),
            "epsilon": maybe_float(rows[0].get("epsilon")),
        }
        key = (
            max_tail_hits,
            max_k,
            mean_l0,
            -mean_top200,
            -mean_auprc,
            name,
        )
        scored.append((key, spec))

    scored.sort(key=lambda x: x[0])
    return [spec for _, spec in scored[:topn]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--npz", type=Path, default=Path("ac_ext/experiments/out/dcopf_flow_features_case118.npz"))
    parser.add_argument("--truth-csv", type=Path, default=Path("ac_ext/experiments/out/ml_training_data_case118.csv"))
    parser.add_argument("--params", type=Path, default=Path("ac_ext/experiments/out/dcopf_score_params_case118_v001.json"))
    parser.add_argument("--training-results", type=Path, default=Path("ac_ext/experiments/out/dcopf_score_training_results_case118_v001.csv"))
    parser.add_argument("--eval-seeds", type=parse_int_list, default=(300,))
    parser.add_argument("--train-seeds", type=parse_int_list, default=(7, 42, 100, 200))
    parser.add_argument("--k-initial-grid", type=parse_int_list, default=(100, 125, 150, 175, 200))
    parser.add_argument("--tail-audit-grid", type=parse_int_list, default=(25, 50, 75, 100))
    parser.add_argument("--expand-factor-grid", type=parse_float_list, default=(1.25, 1.5, 2.0))
    parser.add_argument("--max-expand-rounds", type=int, default=3)
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("ac_ext/experiments/out/dcopf_l0_guard_tuning_case118_v001"),
    )
    args = parser.parse_args()

    out_prefix = args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_csv = out_prefix.with_suffix(".csv")
    out_per_lop_csv = out_prefix.with_name(out_prefix.name + "_per_lop.csv")
    out_best_json = out_prefix.with_name(out_prefix.name + "_best.json")
    out_md = out_prefix.with_suffix(".md")

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

    success = np.asarray(d["dcopf_success"], dtype=bool)
    abs_flow = compute_abs_flow(
        pf=np.asarray(d["PF"], dtype=np.float64),
        pt=np.asarray(d["PT"], dtype=np.float64),
        branch_status=np.asarray(d["branch_status"], dtype=bool),
    )
    truth_fail = build_truth_fail_label(
        np.asarray(truth["truth_success"], dtype=bool),
        np.asarray(truth["truth_s_any"], dtype=np.float64),
    )

    train_mask = np.isin(seed_arr, np.asarray(args.train_seeds, dtype=np.int64))
    eval_mask = np.isin(seed_arr, np.asarray(args.eval_seeds, dtype=np.int64))
    if not np.any(train_mask):
        raise ValueError("empty train split")
    if not np.any(eval_mask):
        raise ValueError("empty eval split")

    params_payload = json.loads(args.params.read_text(encoding="utf-8"))
    best_trained = params_payload["best_trained_physics"]

    score_specs: list[dict[str, Any]] = [
        {"score_name": "raw_success_fail", "method_family": "raw_success_fail", "margin": None, "q": None, "epsilon": None}
    ]

    bt_params = best_trained.get("parameters") or {}
    score_specs.append(
        {
            "score_name": str(best_trained.get("score_name", "best_trained_physics")),
            "method_family": str(best_trained.get("method_family")),
            "margin": bt_params.get("margin"),
            "q": bt_params.get("q"),
            "epsilon": bt_params.get("epsilon"),
            "score_priority": 1,
        }
    )

    top_specs = load_top_trained_specs(args.training_results, topn=3)
    existing = {str(s["score_name"]) for s in score_specs}
    for spec in top_specs:
        if str(spec["score_name"]) in existing:
            continue
        spec["score_priority"] = 2
        score_specs.append(spec)

    basecase_pf = np.asarray(d["basecase_PF"], dtype=np.float64)
    basecase_pt = np.asarray(d["basecase_PT"], dtype=np.float64)

    candidates: list[ScoreCandidate] = []
    for spec in score_specs:
        score = build_score_from_spec(
            spec=spec,
            success=success,
            abs_flow=abs_flow,
            basecase_pf=basecase_pf,
            basecase_pt=basecase_pt,
            train_mask=train_mask,
        )
        priority = int(spec.get("score_priority", 0 if spec["method_family"] == "raw_success_fail" else 2))
        candidates.append(
            ScoreCandidate(
                score_name=str(spec["score_name"]),
                method_family=str(spec["method_family"]),
                score=score,
                score_priority=priority,
            )
        )

    eval_lops = sorted({float(x) for x in lop_arr[eval_mask].tolist()})
    agg_rows: list[dict[str, Any]] = []
    per_lop_rows: list[dict[str, Any]] = []

    for cand in candidates:
        score_eval = cand.score[eval_mask]
        fail_eval = truth_fail[eval_mask]
        lop_eval = lop_arr[eval_mask]

        for k0 in args.k_initial_grid:
            for tail in args.tail_audit_grid:
                for expand in args.expand_factor_grid:
                    lop_metrics: list[dict[str, Any]] = []
                    for lop in eval_lops:
                        m = np.isclose(lop_eval, lop)
                        score_sub = score_eval[m]
                        fail_sub = fail_eval[m]
                        guard = simulate_failure_label_guard(
                            score=score_sub,
                            fail_label=fail_sub,
                            k_initial=int(k0),
                            tail_audit=int(tail),
                            expand_factor=float(expand),
                            max_expand_rounds=int(args.max_expand_rounds),
                        )
                        top100_r, top100_p = topk_stats(fail_sub, score_sub, 100)
                        top200_r, top200_p = topk_stats(fail_sub, score_sub, 200)
                        row = {
                            "score_name": cand.score_name,
                            "method_family": cand.method_family,
                            "K_initial": int(k0),
                            "tail_audit": int(tail),
                            "expand_factor": float(expand),
                            "max_expand_rounds": int(args.max_expand_rounds),
                            "line_outage_prob": float(lop),
                            "n_samples": int(fail_sub.shape[0]),
                            "n_fail": int(np.sum(fail_sub)),
                            "fail_rate": float(np.mean(fail_sub)),
                            "K_final": int(guard["K_final"]),
                            "l0_truth_calls": int(guard["l0_truth_calls"]),
                            "tail_audit_count": int(guard["tail_audit_count"]),
                            "tail_audit_failure_hits": int(guard["tail_audit_failure_hits"]),
                            "guard_passed": bool(guard["failure_label_guard_passed"]),
                            "fallback_reason": str(guard["failure_label_fallback_reason"]),
                            "top100_recall": float(top100_r),
                            "top100_precision": float(top100_p),
                            "top200_recall": float(top200_r),
                            "top200_precision": float(top200_p),
                        }
                        per_lop_rows.append(row)
                        lop_metrics.append(row)

                    pass_all = all(
                        (int(r["tail_audit_failure_hits"]) == 0) and (str(r["fallback_reason"]) == "none")
                        for r in lop_metrics
                    )
                    mean_l0 = float(statistics.mean(float(r["l0_truth_calls"]) for r in lop_metrics))
                    max_k = int(max(int(r["K_final"]) for r in lop_metrics))
                    max_hits = int(max(int(r["tail_audit_failure_hits"]) for r in lop_metrics))
                    mean_top100 = float(statistics.mean(float(r["top100_recall"]) for r in lop_metrics))
                    mean_top200 = float(statistics.mean(float(r["top200_recall"]) for r in lop_metrics))
                    agg_rows.append(
                        {
                            "score_name": cand.score_name,
                            "method_family": cand.method_family,
                            "score_priority": cand.score_priority,
                            "K_initial": int(k0),
                            "tail_audit": int(tail),
                            "expand_factor": float(expand),
                            "max_expand_rounds": int(args.max_expand_rounds),
                            "n_lops": int(len(lop_metrics)),
                            "pass_all_lops": bool(pass_all),
                            "mean_l0_truth_calls": mean_l0,
                            "max_K_final": max_k,
                            "max_tail_audit_failure_hits": max_hits,
                            "mean_top100_recall": mean_top100,
                            "mean_top200_recall": mean_top200,
                        }
                    )

    def key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            0 if bool(row["pass_all_lops"]) else 1,
            float(row["mean_l0_truth_calls"]),
            int(row["max_K_final"]),
            int(row["K_initial"]),
            int(row["score_priority"]),
            str(row["score_name"]),
            int(row["tail_audit"]),
            float(row["expand_factor"]),
        )

    agg_sorted = sorted(agg_rows, key=key)
    best = agg_sorted[0] if agg_sorted else None

    write_csv(out_csv, agg_sorted)
    write_csv(out_per_lop_csv, per_lop_rows)

    best_payload: dict[str, Any] = {
        "stage": "A2.2a",
        "eval_seeds": [int(x) for x in args.eval_seeds],
        "train_seeds": [int(x) for x in args.train_seeds],
        "selection_rule": [
            "pass_all_lops=True",
            "minimum mean_l0_truth_calls",
            "minimum max_K_final",
            "smaller K_initial",
            "simpler score: raw < best_trained_physics < other trained",
        ],
        "best": best,
    }
    out_best_json.write_text(json.dumps(best_payload, indent=2), encoding="utf-8")

    pass_count = sum(1 for r in agg_sorted if bool(r["pass_all_lops"]))
    md = [
        "# A2.2a Guard Parameter Tuning",
        "",
        f"- eval seeds: `{','.join(str(x) for x in args.eval_seeds)}`",
        f"- train seeds (for trained score reconstruction): `{','.join(str(x) for x in args.train_seeds)}`",
        f"- candidates: `{', '.join(c.score_name for c in candidates)}`",
        f"- total grid rows: `{len(agg_sorted)}`",
        f"- pass_all_lops rows: `{pass_count}`",
        "",
    ]
    if best is not None:
        md.extend(
            [
                "## Best Configuration",
                "",
                f"- score: `{best['score_name']}` ({best['method_family']})",
                f"- K_initial: `{best['K_initial']}`",
                f"- tail_audit: `{best['tail_audit']}`",
                f"- expand_factor: `{best['expand_factor']}`",
                f"- pass_all_lops: `{best['pass_all_lops']}`",
                f"- mean_l0_truth_calls: `{best['mean_l0_truth_calls']}`",
                f"- max_K_final: `{best['max_K_final']}`",
                f"- max_tail_audit_failure_hits: `{best['max_tail_audit_failure_hits']}`",
                f"- mean_top100_recall: `{best['mean_top100_recall']}`",
                f"- mean_top200_recall: `{best['mean_top200_recall']}`",
                "",
            ]
        )
    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"wrote aggregate: {out_csv}")
    print(f"wrote per_lop: {out_per_lop_csv}")
    print(f"wrote best: {out_best_json}")
    print(f"wrote report: {out_md}")


if __name__ == "__main__":
    main()
