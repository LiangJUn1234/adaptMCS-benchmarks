#!/usr/bin/env python3
"""Offline analysis of candidate DCOPF flow scores.

This script consumes the branch-level DCOPF flow artifact and compares
candidate score constructions without calling MATLAB. It is designed for the
first A1.1 score-level optimization pass, not for ML training.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


DEFAULT_MARGIN_GRID = (1.2, 1.5, 2.0, 3.0)
DEFAULT_Q_GRID = (90.0, 95.0, 97.5, 99.0)
DEFAULT_EPSILON_GRID = (5.0, 10.0, 20.0)
DEFAULT_TOPK = (50, 100, 200, 500)


@dataclass(frozen=True)
class SplitConfig:
    train_seeds: tuple[int, ...]
    eval_seeds: tuple[int, ...]


def parse_int_list(raw: str) -> tuple[int, ...]:
    values = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        values.append(int(item))
    if not values:
        raise ValueError("expected at least one integer")
    return tuple(values)


def parse_float_list(raw: str) -> tuple[float, ...]:
    values = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        values.append(float(item))
    if not values:
        raise ValueError("expected at least one float")
    return tuple(values)


def parse_optional_float(raw: str) -> float | None:
    item = raw.strip().lower()
    if item in {"", "none", "null", "na"}:
        return None
    return float(raw)


def parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"cannot parse boolean from {raw!r}")


def load_truth_csv(path: Path) -> dict[str, np.ndarray]:
    sample_id = []
    truth_success = []
    truth_s_line = []
    truth_s_volt = []
    truth_s_any = []
    line_outage_prob = []
    seed = []

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sample_id.append(int(row["sample_id"]))
            seed.append(int(row["seed"]))
            line_outage_prob.append(float(row["line_outage_prob"]))
            truth_success.append(parse_bool(row["success"]))
            truth_s_line.append(float(row["s_line"]))
            truth_s_volt.append(float(row["s_volt"]))
            truth_s_any.append(float(row["s_any"]))

    return {
        "sample_id": np.asarray(sample_id, dtype=np.int64),
        "seed": np.asarray(seed, dtype=np.int64),
        "line_outage_prob": np.asarray(line_outage_prob, dtype=np.float64),
        "truth_success": np.asarray(truth_success, dtype=bool),
        "truth_s_line": np.asarray(truth_s_line, dtype=np.float64),
        "truth_s_volt": np.asarray(truth_s_volt, dtype=np.float64),
        "truth_s_any": np.asarray(truth_s_any, dtype=np.float64),
    }


def safe_nanpercentile(values: np.ndarray, q: float, axis: int) -> np.ndarray:
    valid_counts = np.sum(np.isfinite(values), axis=axis)
    with np.errstate(all="ignore"):
        pct = np.nanpercentile(values, q, axis=axis)
    pct = np.asarray(pct, dtype=np.float64)
    pct[valid_counts == 0] = np.nan
    return pct


def compute_abs_flow(pf: np.ndarray, pt: np.ndarray, branch_status: np.ndarray) -> np.ndarray:
    abs_flow = np.maximum(np.abs(pf), np.abs(pt)).astype(np.float64, copy=False)
    return np.where(branch_status, abs_flow, np.nan)


def compute_raw_success_fail_score(success: np.ndarray) -> np.ndarray:
    score = np.zeros(success.shape[0], dtype=np.float64)
    score[~success] = np.inf
    assert np.all(np.isinf(score[~success]))
    return score


def compute_continuous_flow_score(
    *,
    success: np.ndarray,
    abs_flow: np.ndarray,
    pseudo_limit: np.ndarray,
) -> tuple[np.ndarray, int]:
    score = np.full(success.shape[0], np.inf, dtype=np.float64)
    ratio = abs_flow / pseudo_limit[None, :]
    flow_score_success = np.nanmax(ratio - 1.0, axis=1)
    bad_success = success & ~np.isfinite(flow_score_success)
    score[success] = flow_score_success[success]
    score[bad_success] = np.inf
    assert np.all(np.isinf(score[~success]))
    return score, int(np.sum(bad_success))


def make_metric_safe_score(score: np.ndarray) -> np.ndarray:
    """Return a metric-safe score vector with failed samples capped above finite scores.

    Ranking logic should still use `score` with `+inf` for failed samples. This helper
    only exists so AUROC/AUPRC implementations remain compatible with libraries that
    reject infinite inputs.
    """
    metric_score = np.asarray(score, dtype=np.float64).copy()
    finite_mask = np.isfinite(metric_score)
    if np.any(finite_mask):
        cap = float(np.max(metric_score[finite_mask])) + 1.0
    else:
        cap = 1.0
    metric_score[~finite_mask] = cap
    return metric_score


def compute_base_limit(
    *,
    basecase_pf: np.ndarray,
    basecase_pt: np.ndarray,
    margin: float,
    epsilon: float,
) -> np.ndarray:
    base_mag = np.maximum(np.abs(basecase_pf), np.abs(basecase_pt)).astype(np.float64, copy=False)
    return np.maximum(base_mag * margin, epsilon)


def compute_train_percentile_limit(
    *,
    abs_flow: np.ndarray,
    success: np.ndarray,
    train_mask: np.ndarray,
    q: float,
    epsilon: float,
) -> np.ndarray:
    train_success = train_mask & success
    flows_train = abs_flow[train_success]
    limit = safe_nanpercentile(flows_train, q=q, axis=0)
    limit = np.where(np.isfinite(limit), limit, epsilon)
    return np.maximum(limit, epsilon)


def compute_hybrid_limit(
    *,
    basecase_pf: np.ndarray,
    basecase_pt: np.ndarray,
    abs_flow: np.ndarray,
    success: np.ndarray,
    train_mask: np.ndarray,
    margin: float,
    q: float,
    epsilon: float,
) -> np.ndarray:
    base_limit = compute_base_limit(
        basecase_pf=basecase_pf,
        basecase_pt=basecase_pt,
        margin=margin,
        epsilon=epsilon,
    )
    train_limit = compute_train_percentile_limit(
        abs_flow=abs_flow,
        success=success,
        train_mask=train_mask,
        q=q,
        epsilon=epsilon,
    )
    return np.maximum(np.maximum(base_limit, train_limit), epsilon)


def build_truth_fail_label(truth_success: np.ndarray, truth_score: np.ndarray) -> np.ndarray:
    return (~truth_success) | np.isinf(truth_score)


def topk_stats(y_true: np.ndarray, score: np.ndarray, k: int) -> tuple[float, float]:
    n = y_true.shape[0]
    if n == 0:
        return float("nan"), float("nan")
    k_eff = max(1, min(k, n))
    order = np.argsort(-score, kind="mergesort")
    hits = y_true[order[:k_eff]]
    positives = int(np.sum(y_true))
    recall = float(np.sum(hits) / positives) if positives > 0 else float("nan")
    precision = float(np.mean(hits)) if k_eff > 0 else float("nan")
    return recall, precision


def roc_auc_score_binary(y_true: np.ndarray, score: np.ndarray) -> float:
    positives = int(np.sum(y_true))
    negatives = int(y_true.shape[0] - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    order = np.argsort(-score, kind="mergesort")
    y_sorted = y_true[order].astype(np.int64, copy=False)
    score_sorted = score[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    change = np.r_[score_sorted[1:] != score_sorted[:-1], True]
    cut = np.flatnonzero(change)
    tpr = np.r_[0.0, tp[cut] / positives, 1.0]
    fpr = np.r_[0.0, fp[cut] / negatives, 1.0]
    return float(np.trapezoid(tpr, fpr))


def average_precision_binary(y_true: np.ndarray, score: np.ndarray) -> float:
    positives = int(np.sum(y_true))
    if positives == 0:
        return float("nan")
    order = np.argsort(-score, kind="mergesort")
    y_sorted = y_true[order].astype(np.int64, copy=False)
    score_sorted = score[order]
    tp = np.cumsum(y_sorted)
    change = np.r_[score_sorted[1:] != score_sorted[:-1], True]
    cut = np.flatnonzero(change)
    precision = tp[cut] / (cut + 1)
    recall = tp[cut] / positives
    recall_prev = np.r_[0.0, recall[:-1]]
    return float(np.sum((recall - recall_prev) * precision))


def guard_simulation(
    *,
    proxy_score: np.ndarray,
    truth_score: np.ndarray,
    risk_event_label: np.ndarray,
    k_initial: int,
    n_seed: int,
    tail_audit: int,
    expand_factor: float,
    max_expand_rounds: int,
) -> dict[str, Any]:
    n_samples = proxy_score.shape[0]
    ranking = np.argsort(-proxy_score, kind="mergesort")
    k_current = min(n_samples, max(1, k_initial))
    n_seed_eff = min(max(1, n_seed), n_samples)
    rank_inversion_hits = 0
    expand_rounds = 0
    tail_audit_count = 0
    guard_passed = False
    fallback_triggered = False
    fallback_reason = "none"
    gamma_candidate = None
    truth_calls = 0
    audited_indices_seen: set[int] = set()
    truth_evaluated = np.zeros(n_samples, dtype=bool)

    while True:
        topk_indices = ranking[:k_current]
        if not np.all(truth_evaluated[topk_indices]):
            truth_evaluated[topk_indices] = True
        truth_calls = int(np.sum(truth_evaluated))

        topk_truth = truth_score[topk_indices]
        topk_truth_sorted = np.sort(topk_truth)[::-1]
        if topk_truth_sorted.shape[0] < n_seed_eff:
            fallback_triggered = True
            fallback_reason = "insufficient_topk_truth"
            break
        gamma_candidate = float(topk_truth_sorted[n_seed_eff - 1])

        audit_start = k_current
        audit_end = min(n_samples, audit_start + tail_audit)
        audit_indices = ranking[audit_start:audit_end]
        tail_audit_count += int(audit_indices.shape[0])
        audited_indices_seen.update(int(i) for i in audit_indices.tolist())
        if audit_indices.size > 0:
            truth_evaluated[audit_indices] = True
            truth_calls = int(np.sum(truth_evaluated))

        hits_this_round = int(np.sum(truth_score[audit_indices] >= gamma_candidate))
        rank_inversion_hits += hits_this_round

        if hits_this_round == 0:
            guard_passed = True
            break

        if expand_rounds >= max_expand_rounds or k_current >= n_samples:
            fallback_triggered = True
            fallback_reason = "rank_inversion_guard_exceeded"
            break

        expand_rounds += 1
        expanded = int(math.ceil(k_current * expand_factor))
        k_current = min(n_samples, max(k_current + 1, expanded))

    if not guard_passed:
        truth_calls = n_samples
        k_current = n_samples

    final_topk = ranking[:k_current]
    fail_recall_inside_final_k = float("nan")
    truth_fail_total = int(np.sum(risk_event_label))
    if truth_fail_total > 0:
        fail_recall_inside_final_k = float(np.sum(risk_event_label[final_topk]) / truth_fail_total)

    return {
        "simulated_K_final": int(k_current),
        "simulated_l0_truth_calls": int(truth_calls),
        "guard_passed": bool(guard_passed),
        "guard_fallback_flag": bool(fallback_triggered),
        "guard_fallback_reason": fallback_reason,
        "rank_inversion_hits": int(rank_inversion_hits),
        "tail_audit_count": int(tail_audit_count),
        "expand_rounds": int(expand_rounds),
        "gamma_candidate": gamma_candidate,
        "failure_recall_inside_final_k": fail_recall_inside_final_k,
        "audited_count": int(len(audited_indices_seen)),
    }


def guard_simulation_failure_label(
    *,
    proxy_score: np.ndarray,
    risk_event_label: np.ndarray,
    k_initial: int,
    tail_audit: int,
    expand_factor: float,
    max_expand_rounds: int,
) -> dict[str, Any]:
    n_samples = proxy_score.shape[0]
    ranking = np.argsort(-proxy_score, kind="mergesort")
    k_current = min(n_samples, max(1, k_initial))
    rank_inversion_hits = 0
    expand_rounds = 0
    tail_audit_count = 0
    guard_passed = False
    fallback_triggered = False
    fallback_reason = "none"
    truth_calls = 0
    audited_indices_seen: set[int] = set()
    truth_evaluated = np.zeros(n_samples, dtype=bool)

    while True:
        topk_indices = ranking[:k_current]
        if topk_indices.size > 0:
            truth_evaluated[topk_indices] = True
        truth_calls = int(np.sum(truth_evaluated))

        audit_start = k_current
        audit_end = min(n_samples, audit_start + tail_audit)
        audit_indices = ranking[audit_start:audit_end]
        tail_audit_count += int(audit_indices.shape[0])
        audited_indices_seen.update(int(i) for i in audit_indices.tolist())
        if audit_indices.size > 0:
            truth_evaluated[audit_indices] = True
            truth_calls = int(np.sum(truth_evaluated))

        hits_this_round = int(np.sum(risk_event_label[audit_indices]))
        rank_inversion_hits += hits_this_round

        if hits_this_round == 0:
            guard_passed = True
            break

        if expand_rounds >= max_expand_rounds or k_current >= n_samples:
            fallback_triggered = True
            fallback_reason = "rank_inversion_guard_exceeded"
            break

        expand_rounds += 1
        expanded = int(math.ceil(k_current * expand_factor))
        k_current = min(n_samples, max(k_current + 1, expanded))

    if not guard_passed:
        truth_calls = n_samples
        k_current = n_samples

    final_topk = ranking[:k_current]
    fail_recall_inside_final_k = float("nan")
    truth_fail_total = int(np.sum(risk_event_label))
    if truth_fail_total > 0:
        fail_recall_inside_final_k = float(np.sum(risk_event_label[final_topk]) / truth_fail_total)

    return {
        "simulated_K_final": int(k_current),
        "simulated_l0_truth_calls": int(truth_calls),
        "guard_passed": bool(guard_passed),
        "guard_fallback_flag": bool(fallback_triggered),
        "guard_fallback_reason": fallback_reason,
        "rank_inversion_hits": int(rank_inversion_hits),
        "tail_audit_count": int(tail_audit_count),
        "expand_rounds": int(expand_rounds),
        "gamma_candidate": None,
        "failure_recall_inside_final_k": fail_recall_inside_final_k,
        "audited_count": int(len(audited_indices_seen)),
    }


def resolve_n_seed(n_subset: int, n_seed_override: int | None, sus_p0: float) -> int:
    if n_subset <= 0:
        return 1
    if n_seed_override is not None:
        return min(n_subset, max(1, int(n_seed_override)))
    return min(n_subset, max(1, int(math.ceil(n_subset * sus_p0))))


def cohort_breakdown(
    *,
    y_true: np.ndarray,
    ranking_score: np.ndarray,
    metric_score: np.ndarray,
    line_outage_prob: np.ndarray,
    topk_values: Iterable[int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    unique_lop = sorted({float(x) for x in line_outage_prob.tolist()})
    for lop in unique_lop:
        mask = np.isclose(line_outage_prob, lop)
        y = y_true[mask]
        s_rank = ranking_score[mask]
        s_metric = metric_score[mask]
        row: dict[str, Any] = {
            "line_outage_prob": float(lop),
            "n_samples": int(mask.sum()),
            "fail_rate": float(np.mean(y)) if y.size > 0 else float("nan"),
            "auroc": roc_auc_score_binary(y, s_metric) if y.size > 0 else float("nan"),
            "auprc": average_precision_binary(y, s_metric) if y.size > 0 else float("nan"),
        }
        for k in topk_values:
            recall, precision = topk_stats(y, s_rank, k)
            row[f"top{k}_recall"] = recall
            row[f"top{k}_precision"] = precision
        rows.append(row)
    return rows


def analyze_candidate(
    *,
    score_name: str,
    score_version: str,
    score: np.ndarray,
    eval_mask: np.ndarray,
    truth_fail_label: np.ndarray,
    truth_score: np.ndarray,
    line_outage_prob: np.ndarray,
    topk_values: tuple[int, ...],
    k_initial: int,
    n_seed_override: int | None,
    sus_p0: float,
    tail_audit: int,
    expand_factor: float,
    max_expand_rounds: int,
    split_label: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    y_eval = truth_fail_label[eval_mask]
    score_eval = score[eval_mask]
    metric_score_eval = make_metric_safe_score(score_eval)
    truth_eval = truth_score[eval_mask]
    lop_eval = line_outage_prob[eval_mask]
    n_seed_effective = resolve_n_seed(
        n_subset=int(y_eval.shape[0]),
        n_seed_override=n_seed_override,
        sus_p0=sus_p0,
    )

    legacy_guard = guard_simulation(
        proxy_score=score_eval,
        truth_score=truth_eval,
        risk_event_label=y_eval,
        k_initial=k_initial,
        n_seed=n_seed_effective,
        tail_audit=tail_audit,
        expand_factor=expand_factor,
        max_expand_rounds=max_expand_rounds,
    )
    failure_guard = guard_simulation_failure_label(
        proxy_score=score_eval,
        risk_event_label=y_eval,
        k_initial=k_initial,
        tail_audit=tail_audit,
        expand_factor=expand_factor,
        max_expand_rounds=max_expand_rounds,
    )

    summary: dict[str, Any] = {
        "score_name": score_name,
        "score_version": score_version,
        "split": split_label,
        "n_samples": int(y_eval.shape[0]),
        "n_fail": int(np.sum(y_eval)),
        "fail_rate": float(np.mean(y_eval)),
        "sus_p0": float(sus_p0),
        "n_seed_effective": int(n_seed_effective),
        "auroc": roc_auc_score_binary(y_eval, metric_score_eval),
        "auprc": average_precision_binary(y_eval, metric_score_eval),
        "legacy_rank_inversion_hits": legacy_guard["rank_inversion_hits"],
        "legacy_simulated_K_final": legacy_guard["simulated_K_final"],
        "legacy_simulated_l0_truth_calls": legacy_guard["simulated_l0_truth_calls"],
        "legacy_guard_passed": legacy_guard["guard_passed"],
        "legacy_guard_fallback_flag": legacy_guard["guard_fallback_flag"],
        "legacy_guard_fallback_reason": legacy_guard["guard_fallback_reason"],
        "legacy_failure_recall_inside_final_k": legacy_guard["failure_recall_inside_final_k"],
        "failure_label_rank_inversion_hits": failure_guard["rank_inversion_hits"],
        "failure_label_simulated_K_final": failure_guard["simulated_K_final"],
        "failure_label_simulated_l0_truth_calls": failure_guard["simulated_l0_truth_calls"],
        "failure_label_guard_passed": failure_guard["guard_passed"],
        "failure_label_guard_fallback_flag": failure_guard["guard_fallback_flag"],
        "failure_label_guard_fallback_reason": failure_guard["guard_fallback_reason"],
        "failure_label_recall_inside_final_k": failure_guard["failure_recall_inside_final_k"],
        # Backward-compatible aliases default to legacy guard semantics.
        "rank_inversion_hits": legacy_guard["rank_inversion_hits"],
        "simulated_K_final": legacy_guard["simulated_K_final"],
        "simulated_l0_truth_calls": legacy_guard["simulated_l0_truth_calls"],
        "guard_passed": legacy_guard["guard_passed"],
        "guard_fallback_flag": legacy_guard["guard_fallback_flag"],
        "guard_fallback_reason": legacy_guard["guard_fallback_reason"],
        "failure_recall_inside_final_k": legacy_guard["failure_recall_inside_final_k"],
        "n_inf_score": int(np.sum(np.isinf(score_eval))),
        "n_finite_score": int(np.sum(np.isfinite(score_eval))),
    }
    for k in topk_values:
        recall, precision = topk_stats(y_eval, score_eval, k)
        summary[f"top{k}_recall"] = recall
        summary[f"top{k}_precision"] = precision

    cohorts = cohort_breakdown(
        y_true=y_eval,
        ranking_score=score_eval,
        metric_score=metric_score_eval,
        line_outage_prob=lop_eval,
        topk_values=topk_values,
    )
    for row in cohorts:
        row["score_name"] = score_name
        row["score_version"] = score_version
        row["split"] = split_label

    return summary, cohorts


def float_for_json(value: Any) -> Any:
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)):
            return None
        if math.isinf(float(value)):
            return "inf" if float(value) > 0 else "-inf"
        return float(value)
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
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--npz",
        type=Path,
        default=Path(
            "/home/lhftr/code/power-rare-events/adaptMCS-benchmarks/ac_ext/experiments/out/dcopf_flow_features_case118.npz"
        ),
    )
    parser.add_argument(
        "--truth-csv",
        type=Path,
        default=Path(
            "/home/lhftr/code/power-rare-events/adaptMCS-benchmarks/ac_ext/experiments/out/ml_training_data_case118.csv"
        ),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path(
            "/home/lhftr/code/power-rare-events/adaptMCS-benchmarks/ac_ext/experiments/out/dcopf_flow_score_analysis_case118"
        ),
    )
    parser.add_argument("--train-seeds", type=parse_int_list, default=(7, 42, 100, 200))
    parser.add_argument("--eval-seeds", type=parse_int_list, default=(300,))
    parser.add_argument("--eval-lop", type=parse_optional_float, default=None)
    parser.add_argument("--margins", type=parse_float_list, default=DEFAULT_MARGIN_GRID)
    parser.add_argument("--percentiles", type=parse_float_list, default=DEFAULT_Q_GRID)
    parser.add_argument("--epsilons", type=parse_float_list, default=DEFAULT_EPSILON_GRID)
    parser.add_argument("--topk", type=parse_int_list, default=DEFAULT_TOPK)
    parser.add_argument("--k-initial", type=int, default=200)
    parser.add_argument("--n-seed", type=int, default=None)
    parser.add_argument("--sus-p0", type=float, default=0.15)
    parser.add_argument("--tail-audit", type=int, default=50)
    parser.add_argument("--expand-factor", type=float, default=1.5)
    parser.add_argument("--max-expand-rounds", type=int, default=3)
    args = parser.parse_args()
    if not (0.0 < float(args.sus_p0) <= 1.0):
        raise ValueError("--sus-p0 must be in (0, 1]")

    out_prefix = args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    d = np.load(args.npz)
    truth = load_truth_csv(args.truth_csv)

    sample_id = np.asarray(d["sample_id"], dtype=np.int64)
    if not np.array_equal(sample_id, truth["sample_id"]):
        raise ValueError("sample_id mismatch between NPZ and truth CSV")
    if not np.array_equal(np.asarray(d["seed"], dtype=np.int64), truth["seed"]):
        raise ValueError("seed mismatch between NPZ and truth CSV")

    split = SplitConfig(
        train_seeds=tuple(args.train_seeds),
        eval_seeds=tuple(args.eval_seeds),
    )

    seed_arr = np.asarray(d["seed"], dtype=np.int64)
    train_mask = np.isin(seed_arr, np.asarray(split.train_seeds, dtype=np.int64))
    eval_mask = np.isin(seed_arr, np.asarray(split.eval_seeds, dtype=np.int64))
    line_outage_prob = np.asarray(d["line_outage_prob"], dtype=np.float64)
    if args.eval_lop is not None:
        eval_mask = eval_mask & np.isclose(line_outage_prob, float(args.eval_lop))
    if not np.any(train_mask):
        raise ValueError("train split is empty")
    if not np.any(eval_mask):
        raise ValueError("eval split is empty")

    success = np.asarray(d["dcopf_success"], dtype=bool)
    branch_status = np.asarray(d["branch_status"], dtype=bool)
    abs_flow = compute_abs_flow(
        pf=np.asarray(d["PF"], dtype=np.float64),
        pt=np.asarray(d["PT"], dtype=np.float64),
        branch_status=branch_status,
    )
    truth_success = np.asarray(truth["truth_success"], dtype=bool)
    truth_score = np.asarray(truth["truth_s_any"], dtype=np.float64)
    truth_fail_label = build_truth_fail_label(truth_success, truth_score)
    basecase_pf = np.asarray(d["basecase_PF"], dtype=np.float64)
    basecase_pt = np.asarray(d["basecase_PT"], dtype=np.float64)

    summaries: list[dict[str, Any]] = []
    cohort_rows: list[dict[str, Any]] = []
    per_lop_summaries: list[dict[str, Any]] = []

    eval_lops = sorted({float(x) for x in line_outage_prob[eval_mask].tolist()})

    def register_candidate(
        *,
        score_name: str,
        score_version: str,
        score: np.ndarray,
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        fields = dict(extra_fields or {})
        summary, cohorts = analyze_candidate(
            score_name=score_name,
            score_version=score_version,
            score=score,
            eval_mask=eval_mask,
            truth_fail_label=truth_fail_label,
            truth_score=truth_score,
            line_outage_prob=line_outage_prob,
            topk_values=tuple(args.topk),
            k_initial=args.k_initial,
            n_seed_override=args.n_seed,
            sus_p0=float(args.sus_p0),
            tail_audit=args.tail_audit,
            expand_factor=args.expand_factor,
            max_expand_rounds=args.max_expand_rounds,
            split_label="eval_global",
        )
        summary.update(fields)
        summaries.append(summary)
        for row in cohorts:
            row.update(fields)
        cohort_rows.extend(cohorts)

        for lop in eval_lops:
            lop_mask = eval_mask & np.isclose(line_outage_prob, lop)
            if not np.any(lop_mask):
                continue
            lop_summary, _ = analyze_candidate(
                score_name=score_name,
                score_version=score_version,
                score=score,
                eval_mask=lop_mask,
                truth_fail_label=truth_fail_label,
                truth_score=truth_score,
                line_outage_prob=line_outage_prob,
                topk_values=tuple(args.topk),
                k_initial=args.k_initial,
                n_seed_override=args.n_seed,
                sus_p0=float(args.sus_p0),
                tail_audit=args.tail_audit,
                expand_factor=args.expand_factor,
                max_expand_rounds=args.max_expand_rounds,
                split_label="eval_per_lop",
            )
            lop_summary["line_outage_prob"] = float(lop)
            lop_summary.update(fields)
            per_lop_summaries.append(lop_summary)

    raw_score = compute_raw_success_fail_score(success)
    register_candidate(
        score_name="raw_success_fail_score",
        score_version="dcopf_raw_success_fail",
        score=raw_score,
        extra_fields={"n_bad_success_flow_score": 0},
    )

    for epsilon in args.epsilons:
        for margin in args.margins:
            limit = compute_base_limit(
                basecase_pf=basecase_pf,
                basecase_pt=basecase_pt,
                margin=margin,
                epsilon=epsilon,
            )
            score, n_bad_success_flow_score = compute_continuous_flow_score(
                success=success,
                abs_flow=abs_flow,
                pseudo_limit=limit,
            )
            register_candidate(
                score_name="base_margin_score",
                score_version=f"dcopf_pseudo_limit_base_margin_m{margin:g}_e{epsilon:g}",
                score=score,
                extra_fields={
                    "margin": float(margin),
                    "epsilon": float(epsilon),
                    "n_bad_success_flow_score": int(n_bad_success_flow_score),
                },
            )

        for q in args.percentiles:
            limit = compute_train_percentile_limit(
                abs_flow=abs_flow,
                success=success,
                train_mask=train_mask,
                q=q,
                epsilon=epsilon,
            )
            score, n_bad_success_flow_score = compute_continuous_flow_score(
                success=success,
                abs_flow=abs_flow,
                pseudo_limit=limit,
            )
            register_candidate(
                score_name="train_percentile_score",
                score_version=f"dcopf_pseudo_limit_train_percentile_q{q:g}_e{epsilon:g}",
                score=score,
                extra_fields={
                    "q": float(q),
                    "epsilon": float(epsilon),
                    "n_bad_success_flow_score": int(n_bad_success_flow_score),
                },
            )

        for margin in args.margins:
            for q in args.percentiles:
                limit = compute_hybrid_limit(
                    basecase_pf=basecase_pf,
                    basecase_pt=basecase_pt,
                    abs_flow=abs_flow,
                    success=success,
                    train_mask=train_mask,
                    margin=margin,
                    q=q,
                    epsilon=epsilon,
                )
                score, n_bad_success_flow_score = compute_continuous_flow_score(
                    success=success,
                    abs_flow=abs_flow,
                    pseudo_limit=limit,
                )
                register_candidate(
                    score_name="hybrid_score",
                    score_version=f"dcopf_hybrid_pseudolimit_m{margin:g}_q{q:g}_e{epsilon:g}",
                    score=score,
                    extra_fields={
                        "margin": float(margin),
                        "q": float(q),
                        "epsilon": float(epsilon),
                        "n_bad_success_flow_score": int(n_bad_success_flow_score),
                    },
                )

    def ranking_key(row: dict[str, Any]) -> tuple[float, float, float]:
        return (
            -float(row.get("top200_recall", float("nan")) if row.get("top200_recall") is not None else float("-inf")),
            float(row.get("legacy_rank_inversion_hits", float("inf"))),
            float(row.get("legacy_simulated_K_final", float("inf"))),
        )

    def failure_guard_ranking_key(row: dict[str, Any]) -> tuple[float, float, float]:
        return (
            -float(row.get("top200_recall", float("nan")) if row.get("top200_recall") is not None else float("-inf")),
            float(row.get("failure_label_rank_inversion_hits", float("inf"))),
            float(row.get("failure_label_simulated_K_final", float("inf"))),
        )

    summaries_sorted = sorted(summaries, key=ranking_key)
    summaries_failure_guard_sorted = sorted(summaries, key=failure_guard_ranking_key)
    per_lop_summaries_sorted = sorted(
        per_lop_summaries,
        key=lambda r: (
            str(r.get("score_version", "")),
            float(r.get("line_outage_prob", float("nan"))),
        ),
    )

    summary_csv = out_prefix.with_name(out_prefix.name + "_summary.csv")
    per_lop_summary_csv = out_prefix.with_name(out_prefix.name + "_per_lop_summary.csv")
    cohort_csv = out_prefix.with_name(out_prefix.name + "_cohorts.csv")
    summary_json = out_prefix.with_name(out_prefix.name + "_summary.json")

    write_csv(summary_csv, summaries_sorted)
    write_csv(per_lop_summary_csv, per_lop_summaries_sorted)
    write_csv(cohort_csv, cohort_rows)

    payload = {
        "npz": str(args.npz),
        "truth_csv": str(args.truth_csv),
        "train_seeds": list(split.train_seeds),
        "eval_seeds": list(split.eval_seeds),
        "eval_lop": float(args.eval_lop) if args.eval_lop is not None else None,
        "k_initial": int(args.k_initial),
        "n_seed_override": int(args.n_seed) if args.n_seed is not None else None,
        "sus_p0": float(args.sus_p0),
        "tail_audit": int(args.tail_audit),
        "expand_factor": float(args.expand_factor),
        "max_expand_rounds": int(args.max_expand_rounds),
        "n_candidates": int(len(summaries_sorted)),
        "n_eval_lops": int(len(eval_lops)),
        "eval_lops": [float(x) for x in eval_lops],
        "best_by_top200_recall_legacy_guard": {
            key: float_for_json(value) for key, value in summaries_sorted[0].items()
        },
        "best_by_top200_recall_failure_label_guard": {
            key: float_for_json(value) for key, value in summaries_failure_guard_sorted[0].items()
        },
        "best_by_top200_recall": {
            key: float_for_json(value) for key, value in summaries_sorted[0].items()
        },
        "all_summaries": [
            {key: float_for_json(value) for key, value in row.items()}
            for row in summaries_sorted
        ],
    }
    with summary_json.open("w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)

    print(f"Candidates evaluated: {len(summaries_sorted)}")
    print(f"Summary CSV: {summary_csv}")
    print(f"Per-lop Summary CSV: {per_lop_summary_csv}")
    print(f"Cohort CSV: {cohort_csv}")
    print(f"Summary JSON: {summary_json}")
    if summaries_sorted:
        best_legacy = summaries_sorted[0]
        best_failure = summaries_failure_guard_sorted[0]
        print(
            "Best legacy-guard candidate by top200_recall / rank_inversion_hits / K_final: "
            f"{best_legacy['score_version']} "
            f"top200_recall={best_legacy.get('top200_recall')} "
            f"rank_inversion_hits={best_legacy.get('legacy_rank_inversion_hits')} "
            f"K_final={best_legacy.get('legacy_simulated_K_final')}"
        )
        print(
            "Best failure-label-guard candidate by top200_recall / rank_inversion_hits / K_final: "
            f"{best_failure['score_version']} "
            f"top200_recall={best_failure.get('top200_recall')} "
            f"rank_inversion_hits={best_failure.get('failure_label_rank_inversion_hits')} "
            f"K_final={best_failure.get('failure_label_simulated_K_final')}"
        )


if __name__ == "__main__":
    main()
