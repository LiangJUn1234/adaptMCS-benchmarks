#!/usr/bin/env python3
"""A2.2b offline failed-state severity tie-break score analysis."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
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


def parse_json_field(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return None


def safe_zscore(vec: np.ndarray) -> np.ndarray:
    v = np.asarray(vec, dtype=np.float64)
    mu = float(np.nanmean(v))
    sig = float(np.nanstd(v))
    if not np.isfinite(sig) or sig <= 1e-12:
        return np.zeros_like(v, dtype=np.float64)
    return (v - mu) / sig


def build_base_score(
    *,
    method_family: str,
    params: dict[str, Any] | None,
    success: np.ndarray,
    abs_flow: np.ndarray,
    basecase_pf: np.ndarray,
    basecase_pt: np.ndarray,
    train_mask: np.ndarray,
) -> np.ndarray:
    if method_family == "raw_success_fail":
        return compute_raw_success_fail_score(success)

    if params is None:
        raise ValueError("missing params for non-raw score")

    margin = maybe_float(params.get("margin"))
    q = maybe_float(params.get("q"))
    epsilon = maybe_float(params.get("epsilon"))
    if epsilon is None:
        epsilon = 10.0

    if method_family == "base_margin":
        if margin is None:
            margin = 1.2
        limit = compute_base_limit(
            basecase_pf=basecase_pf,
            basecase_pt=basecase_pt,
            margin=float(margin),
            epsilon=float(epsilon),
        )
    elif method_family == "train_percentile":
        if q is None:
            q = 95.0
        limit = compute_train_percentile_limit(
            abs_flow=abs_flow,
            success=success,
            train_mask=train_mask,
            q=float(q),
            epsilon=float(epsilon),
        )
    elif method_family == "hybrid":
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
        raise ValueError(f"unsupported method_family {method_family}")

    score, _ = compute_continuous_flow_score(
        success=success,
        abs_flow=abs_flow,
        pseudo_limit=np.asarray(limit, dtype=np.float64),
    )
    return score


def rank_with_failed_severity(
    *,
    base_score: np.ndarray,
    success: np.ndarray,
    severity: np.ndarray,
) -> np.ndarray:
    score = np.asarray(base_score, dtype=np.float64).copy()
    fail = ~success
    succ = success

    finite_succ = score[succ & np.isfinite(score)]
    succ_max = float(np.max(finite_succ)) if finite_succ.size > 0 else 0.0

    sev = np.asarray(severity, dtype=np.float64)
    sev_fail = sev[fail]
    if sev_fail.size == 0:
        return score

    sev_norm = safe_zscore(sev)
    sev_norm_fail = sev_norm[fail]
    sev_span = float(np.nanmax(sev_norm_fail) - np.nanmin(sev_norm_fail))
    if not np.isfinite(sev_span) or sev_span < 1e-12:
        sev_shift = np.zeros_like(sev_norm, dtype=np.float64)
    else:
        sev_shift = sev_norm

    failure_base = succ_max + 100.0
    score[fail] = failure_base + sev_shift[fail]
    return score


def compute_generator_severity(truth_csv: Path, n_rows: int) -> tuple[np.ndarray | None, str]:
    vals: list[float] = []
    with truth_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gs = parse_json_field(row.get("gen_scale_json", ""))
            gd = parse_json_field(row.get("gen_derate_state_json", ""))
            lost_scale = 0.0
            if isinstance(gs, list):
                for x in gs:
                    try:
                        fx = float(x)
                    except Exception:
                        continue
                    if math.isfinite(fx):
                        lost_scale += max(0.0, 1.0 - fx)
            derate_count = 0.0
            if isinstance(gd, list):
                for x in gd:
                    try:
                        fx = float(x)
                    except Exception:
                        continue
                    if fx > 0:
                        derate_count += 1.0
            vals.append(lost_scale + derate_count)

    arr = np.asarray(vals, dtype=np.float64)
    if arr.shape[0] != n_rows:
        return None, "generator severity unavailable: row-count mismatch"
    if not np.any(np.isfinite(arr)):
        return None, "generator severity unavailable: no finite values"
    if float(np.nanmax(arr) - np.nanmin(arr)) < 1e-12:
        return None, "generator severity unavailable: constant signal"
    return arr, "generator severity available"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--npz", type=Path, default=Path("ac_ext/experiments/out/dcopf_flow_features_case118.npz"))
    parser.add_argument("--truth-csv", type=Path, default=Path("ac_ext/experiments/out/ml_training_data_case118.csv"))
    parser.add_argument("--params", type=Path, default=Path("ac_ext/experiments/out/dcopf_score_params_case118_v001.json"))
    parser.add_argument("--train-seeds", type=parse_int_list, default=(7, 42, 100, 200))
    parser.add_argument("--eval-seeds", type=parse_int_list, default=(300,))
    parser.add_argument("--k-initial-grid", type=parse_int_list, default=(100, 125, 150, 175, 200))
    parser.add_argument("--tail-audit-grid", type=parse_int_list, default=(25, 50))
    parser.add_argument("--expand-factor-grid", type=parse_float_list, default=(1.5,))
    parser.add_argument("--max-expand-rounds", type=int, default=3)
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("ac_ext/experiments/out/dcopf_failed_state_severity_scores_case118_v001"),
    )
    args = parser.parse_args()

    out_prefix = args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_csv = out_prefix.with_suffix(".csv")
    out_per_lop_csv = out_prefix.with_name(out_prefix.name + "_per_lop.csv")
    out_md = out_prefix.with_suffix(".md")
    out_best_json = out_prefix.with_name(out_prefix.name + "_best.json")

    d = np.load(args.npz)
    truth = load_truth_csv(args.truth_csv)

    sample_id = np.asarray(d["sample_id"], dtype=np.int64)
    seed_arr = np.asarray(d["seed"], dtype=np.int64)
    lop_arr = np.asarray(d["line_outage_prob"], dtype=np.float64)
    if not np.array_equal(sample_id, truth["sample_id"]):
        raise ValueError("sample_id mismatch")
    if not np.array_equal(seed_arr, truth["seed"]):
        raise ValueError("seed mismatch")
    if not np.allclose(lop_arr, truth["line_outage_prob"]):
        raise ValueError("line_outage_prob mismatch")

    success = np.asarray(d["dcopf_success"], dtype=bool)
    branch_status = np.asarray(d["branch_status"], dtype=bool)
    abs_flow = compute_abs_flow(
        pf=np.asarray(d["PF"], dtype=np.float64),
        pt=np.asarray(d["PT"], dtype=np.float64),
        branch_status=branch_status,
    )
    truth_fail = build_truth_fail_label(
        np.asarray(truth["truth_success"], dtype=bool),
        np.asarray(truth["truth_s_any"], dtype=np.float64),
    )
    train_mask = np.isin(seed_arr, np.asarray(args.train_seeds, dtype=np.int64))
    eval_mask = np.isin(seed_arr, np.asarray(args.eval_seeds, dtype=np.int64))

    if not np.any(eval_mask):
        raise ValueError("empty eval split")

    basecase_pf = np.asarray(d["basecase_PF"], dtype=np.float64)
    basecase_pt = np.asarray(d["basecase_PT"], dtype=np.float64)
    base_mag = np.maximum(np.abs(basecase_pf), np.abs(basecase_pt))

    outaged_count = np.sum(~branch_status, axis=1).astype(np.float64)
    weighted_outage = ((~branch_status).astype(np.float64) * base_mag[None, :]).sum(axis=1)

    def topk_weighted(k: int) -> np.ndarray:
        out = np.zeros(sample_id.shape[0], dtype=np.float64)
        for i in range(sample_id.shape[0]):
            vals = base_mag[~branch_status[i]]
            if vals.size == 0:
                out[i] = 0.0
            else:
                kk = min(int(k), int(vals.size))
                out[i] = float(np.sum(np.partition(vals, -kk)[-kk:]))
        return out

    weighted_top5 = topk_weighted(5)
    weighted_top10 = topk_weighted(10)
    weighted_top20 = topk_weighted(20)

    gen_sev, gen_note = compute_generator_severity(args.truth_csv, sample_id.shape[0])

    combined = safe_zscore(outaged_count) + safe_zscore(weighted_outage)
    if gen_sev is not None:
        combined = combined + safe_zscore(gen_sev)

    severity_defs: list[tuple[str, np.ndarray]] = [
        ("n_outaged_lines", outaged_count),
        ("weighted_baseflow_outage", weighted_outage),
        ("weighted_baseflow_outage_topk5", weighted_top5),
        ("weighted_baseflow_outage_topk10", weighted_top10),
        ("weighted_baseflow_outage_topk20", weighted_top20),
        ("combined_damage_severity", combined),
    ]
    if gen_sev is not None:
        severity_defs.append(("generator_derate_severity", gen_sev))

    params_payload = json.loads(args.params.read_text(encoding="utf-8"))
    best_trained = params_payload["best_trained_physics"]

    raw_base = build_base_score(
        method_family="raw_success_fail",
        params=None,
        success=success,
        abs_flow=abs_flow,
        basecase_pf=basecase_pf,
        basecase_pt=basecase_pt,
        train_mask=train_mask,
    )
    trained_base = build_base_score(
        method_family=str(best_trained["method_family"]),
        params=best_trained.get("parameters"),
        success=success,
        abs_flow=abs_flow,
        basecase_pf=basecase_pf,
        basecase_pt=basecase_pt,
        train_mask=train_mask,
    )

    score_defs: list[tuple[str, np.ndarray, int]] = [
        ("raw_success_fail", raw_base, 0),
    ]

    for sev_name, sev in severity_defs:
        score_defs.append((f"raw_plus_{sev_name}", rank_with_failed_severity(base_score=raw_base, success=success, severity=sev), 1))
        score_defs.append(
            (
                f"best_trained_plus_{sev_name}",
                rank_with_failed_severity(base_score=trained_base, success=success, severity=sev),
                2,
            )
        )

    eval_lops = sorted({float(x) for x in lop_arr[eval_mask].tolist()})
    agg_rows: list[dict[str, Any]] = []
    per_lop_rows: list[dict[str, Any]] = []

    for score_name, score_all, score_priority in score_defs:
        score_eval = score_all[eval_mask]
        fail_eval = truth_fail[eval_mask]
        lop_eval = lop_arr[eval_mask]

        for k0 in args.k_initial_grid:
            for tail in args.tail_audit_grid:
                for expand in args.expand_factor_grid:
                    lop_rows_local: list[dict[str, Any]] = []
                    for lop in eval_lops:
                        m = np.isclose(lop_eval, lop)
                        s = score_eval[m]
                        y = fail_eval[m]
                        g = simulate_failure_label_guard(
                            score=s,
                            fail_label=y,
                            k_initial=int(k0),
                            tail_audit=int(tail),
                            expand_factor=float(expand),
                            max_expand_rounds=int(args.max_expand_rounds),
                        )
                        r100, p100 = topk_stats(y, s, 100)
                        r200, p200 = topk_stats(y, s, 200)
                        row = {
                            "score_name": score_name,
                            "score_priority": int(score_priority),
                            "K_initial": int(k0),
                            "tail_audit": int(tail),
                            "expand_factor": float(expand),
                            "max_expand_rounds": int(args.max_expand_rounds),
                            "line_outage_prob": float(lop),
                            "n_samples": int(y.shape[0]),
                            "n_fail": int(np.sum(y)),
                            "fail_rate": float(np.mean(y)),
                            "K_final": int(g["K_final"]),
                            "l0_truth_calls": int(g["l0_truth_calls"]),
                            "tail_audit_count": int(g["tail_audit_count"]),
                            "tail_audit_failure_hits": int(g["tail_audit_failure_hits"]),
                            "guard_passed": bool(g["failure_label_guard_passed"]),
                            "fallback_reason": str(g["failure_label_fallback_reason"]),
                            "top100_recall": float(r100),
                            "top100_precision": float(p100),
                            "top200_recall": float(r200),
                            "top200_precision": float(p200),
                        }
                        per_lop_rows.append(row)
                        lop_rows_local.append(row)

                    pass_all = all(
                        int(r["tail_audit_failure_hits"]) == 0 and str(r["fallback_reason"]) == "none"
                        for r in lop_rows_local
                    )
                    agg_rows.append(
                        {
                            "score_name": score_name,
                            "score_priority": int(score_priority),
                            "K_initial": int(k0),
                            "tail_audit": int(tail),
                            "expand_factor": float(expand),
                            "max_expand_rounds": int(args.max_expand_rounds),
                            "pass_all_lops": bool(pass_all),
                            "mean_l0_truth_calls": float(statistics.mean(float(r["l0_truth_calls"]) for r in lop_rows_local)),
                            "max_K_final": int(max(int(r["K_final"]) for r in lop_rows_local)),
                            "max_tail_audit_failure_hits": int(max(int(r["tail_audit_failure_hits"]) for r in lop_rows_local)),
                            "mean_top100_recall": float(statistics.mean(float(r["top100_recall"]) for r in lop_rows_local)),
                            "mean_top200_recall": float(statistics.mean(float(r["top200_recall"]) for r in lop_rows_local)),
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
        )

    agg_sorted = sorted(agg_rows, key=key)
    best = agg_sorted[0] if agg_sorted else None

    write_csv(out_csv, agg_sorted)
    write_csv(out_per_lop_csv, per_lop_rows)

    best_payload = {
        "stage": "A2.2b",
        "eval_seeds": [int(x) for x in args.eval_seeds],
        "generator_severity_note": gen_note,
        "best": best,
    }
    out_best_json.write_text(json.dumps(best_payload, indent=2), encoding="utf-8")

    pass_count = sum(1 for r in agg_sorted if bool(r["pass_all_lops"]))
    lines = [
        "# A2.2b Failed-State Severity Tie-Break",
        "",
        f"- eval seeds: `{','.join(str(x) for x in args.eval_seeds)}`",
        f"- generator severity status: `{gen_note}`",
        f"- tested score variants: `{len(score_defs)}`",
        f"- tested guard rows: `{len(agg_sorted)}`",
        f"- pass_all_lops rows: `{pass_count}`",
        "",
        "## Limitation",
        "",
        "- This v001 only adds tie-breaking among DCOPF-failed states from damage severity proxies.",
        "- It does not reconstruct failed DCOPF flow solutions and does not claim physics severity fidelity for failed solves.",
        "",
    ]
    if best is not None:
        lines.extend(
            [
                "## Best Configuration",
                "",
                f"- score: `{best['score_name']}`",
                f"- K_initial: `{best['K_initial']}`",
                f"- tail_audit: `{best['tail_audit']}`",
                f"- expand_factor: `{best['expand_factor']}`",
                f"- pass_all_lops: `{best['pass_all_lops']}`",
                f"- mean_l0_truth_calls: `{best['mean_l0_truth_calls']}`",
                f"- max_K_final: `{best['max_K_final']}`",
                f"- max_tail_audit_failure_hits: `{best['max_tail_audit_failure_hits']}`",
                "",
            ]
        )
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote aggregate: {out_csv}")
    print(f"wrote per_lop: {out_per_lop_csv}")
    print(f"wrote report: {out_md}")
    print(f"wrote best: {out_best_json}")


if __name__ == "__main__":
    main()
