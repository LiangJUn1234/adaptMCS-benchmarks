#!/usr/bin/env python3
"""Analyze case118 DA trace artifacts for proposal-level delayed-acceptance behavior."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


def parse_bool(v: Any) -> bool | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"", "none", "null", "na"}:
        return None
    if s in {"1", "true", "yes", "y"}:
        return True
    if s in {"0", "false", "no", "n"}:
        return False
    return None


def parse_float(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"", "none", "null", "na"}:
        return None
    if s in {"inf", "+inf", "infinity", "+infinity"}:
        return float("inf")
    if s in {"-inf", "-infinity"}:
        return float("-inf")
    try:
        return float(s)
    except Exception:
        return None


def parse_int(v: Any) -> int | None:
    f = parse_float(v)
    if f is None:
        return None
    return int(f)


def numeric_distribution(values: list[float | None]) -> dict[str, Any]:
    missing = sum(1 for v in values if v is None)
    finite_vals = [float(v) for v in values if (v is not None and math.isfinite(float(v)))]
    pos_inf = sum(1 for v in values if v is not None and math.isinf(float(v)) and float(v) > 0)
    neg_inf = sum(1 for v in values if v is not None and math.isinf(float(v)) and float(v) < 0)
    out: dict[str, Any] = {
        "missing": int(missing),
        "finite": int(len(finite_vals)),
        "+inf": int(pos_inf),
        "-inf": int(neg_inf),
        "min": None,
        "q25": None,
        "q50": None,
        "q75": None,
        "q90": None,
        "q95": None,
        "q99": None,
        "max": None,
    }
    if finite_vals:
        arr = np.asarray(finite_vals, dtype=np.float64)
        out.update(
            {
                "min": float(np.min(arr)),
                "q25": float(np.quantile(arr, 0.25)),
                "q50": float(np.quantile(arr, 0.50)),
                "q75": float(np.quantile(arr, 0.75)),
                "q90": float(np.quantile(arr, 0.90)),
                "q95": float(np.quantile(arr, 0.95)),
                "q99": float(np.quantile(arr, 0.99)),
                "max": float(np.max(arr)),
            }
        )
    return out


def safe_rate(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return num / float(den)


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


def fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "N/A"
    if isinstance(x, str):
        return x
    v = float(x)
    if math.isnan(v):
        return "N/A"
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    return f"{v:.{nd}f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-tsv", type=Path, required=True)
    parser.add_argument("--run-csv", type=Path, required=True)
    parser.add_argument("--out-prefix", type=Path, required=True)
    args = parser.parse_args()

    out_prefix = args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_csv = out_prefix.with_suffix(".csv")
    out_json = out_prefix.with_suffix(".json")
    out_md = out_prefix.with_suffix(".md")

    if not args.trace_tsv.exists():
        raise FileNotFoundError(f"trace TSV missing: {args.trace_tsv}")
    if not args.run_csv.exists():
        raise FileNotFoundError(f"run CSV missing: {args.run_csv}")

    run_rows = list(csv.DictReader(args.run_csv.open(newline="", encoding="utf-8")))
    if not run_rows:
        raise ValueError("run CSV has no rows")
    run_row = run_rows[0]
    csv_seed = int(run_row["seed"])
    csv_l0_truth_calls = int(float(run_row.get("l0_truth_calls") or 0))
    csv_truth_calls = int(float(run_row.get("truth_calls") or 0))
    csv_da_trace_rows = parse_int(run_row.get("da_trace_rows"))
    csv_status = str(run_row.get("status"))
    level_acceptance = json.loads(run_row.get("level_acceptance_rates_json", "[]"))

    trace_rows = list(csv.DictReader(args.trace_tsv.open(newline="", encoding="utf-8"), delimiter="\t"))
    total_proposals = len(trace_rows)

    seed_values = [parse_int(r.get("seed")) for r in trace_rows]
    run_seed_values = [parse_int(r.get("run_seed")) for r in trace_rows]
    level_values = [parse_int(r.get("level")) for r in trace_rows]

    checks = {
        "trace_tsv_exists": True,
        "run_csv_exists": True,
        "tsv_rows_equals_da_trace_rows": (csv_da_trace_rows == total_proposals) if csv_da_trace_rows is not None else False,
        "seed_column_matches_csv_seed": all(v == csv_seed for v in seed_values if v is not None),
        "run_seed_column_matches_csv_seed": all(v == csv_seed for v in run_seed_values if v is not None),
        "csv_status_ok": csv_status == "ok",
    }

    level_attempts_from_tsv: dict[int, int] = defaultdict(int)
    for lv in level_values:
        if lv is not None:
            level_attempts_from_tsv[int(lv)] += 1
    level_attempts_from_csv = {int(item["level"]): int(item["attempts"]) for item in level_acceptance}
    checks["level_attempts_match_level_acceptance_rates_json"] = (
        dict(level_attempts_from_tsv) == level_attempts_from_csv
    )

    stage1_accept = [parse_bool(r.get("stage1_accept")) is True for r in trace_rows]
    truth_evaluated = [parse_bool(r.get("truth_evaluated")) is True for r in trace_rows]
    final_accept = [parse_bool(r.get("final_accept")) is True for r in trace_rows]
    reverse_proxy_reject = [parse_bool(r.get("reverse_proxy_reject")) is True for r in trace_rows]
    truth_failed_prop = [parse_bool(r.get("truth_failed_proposal")) for r in trace_rows]
    dcopf_success = [parse_bool(r.get("dcopf_success")) for r in trace_rows]
    proxy_success_prop = [parse_bool(r.get("proxy_success_proposal")) for r in trace_rows]
    n_line_out = [parse_int(r.get("n_line_out")) for r in trace_rows]

    da_truth_calls = int(sum(1 for x in truth_evaluated if x))
    checks["truth_calls_decomposition_matches"] = (csv_l0_truth_calls + da_truth_calls) == csv_truth_calls

    overall = {
        "total_proposals": total_proposals,
        "stage1_accept_count": int(sum(stage1_accept)),
        "stage1_accept_rate": safe_rate(int(sum(stage1_accept)), total_proposals),
        "truth_evaluated_count": da_truth_calls,
        "truth_evaluated_rate": safe_rate(da_truth_calls, total_proposals),
        "final_accept_count": int(sum(final_accept)),
        "final_accept_rate": safe_rate(int(sum(final_accept)), total_proposals),
        "reverse_proxy_reject_count": int(sum(reverse_proxy_reject)),
        "reverse_proxy_reject_rate": safe_rate(int(sum(reverse_proxy_reject)), total_proposals),
    }

    by_level_rows: list[dict[str, Any]] = []
    for level in sorted(level_attempts_from_tsv.keys()):
        idx = [i for i, lv in enumerate(level_values) if lv == level]
        n = len(idx)
        s1 = sum(1 for i in idx if stage1_accept[i])
        te = sum(1 for i in idx if truth_evaluated[i])
        fa = sum(1 for i in idx if final_accept[i])
        rr = sum(1 for i in idx if reverse_proxy_reject[i])
        by_level_rows.append(
            {
                "level": level,
                "proposals": n,
                "stage1_accept_count": s1,
                "stage1_accept_rate": safe_rate(s1, n),
                "truth_evaluated_count": te,
                "truth_evaluated_rate": safe_rate(te, n),
                "final_accept_count": fa,
                "final_accept_rate": safe_rate(fa, n),
                "reverse_proxy_reject_count": rr,
                "reverse_proxy_reject_rate": safe_rate(rr, n),
            }
        )

    truth_eval_idx = [i for i, t in enumerate(truth_evaluated) if t]
    truth_eval_fail = sum(1 for i in truth_eval_idx if truth_failed_prop[i] is True)
    truth_eval_safe = sum(1 for i in truth_eval_idx if truth_failed_prop[i] is False)
    truth_eval_final_accept = sum(1 for i in truth_eval_idx if final_accept[i])
    truth_eval_final_reject = len(truth_eval_idx) - truth_eval_final_accept
    truth_eval_reverse_reject = sum(1 for i in truth_eval_idx if reverse_proxy_reject[i])

    truth_subset = {
        "n": len(truth_eval_idx),
        "acopf_failed_count": truth_eval_fail,
        "acopf_safe_count": truth_eval_safe,
        "failed_fraction": safe_rate(truth_eval_fail, len(truth_eval_idx)),
        "final_accept_count": truth_eval_final_accept,
        "final_reject_count": truth_eval_final_reject,
        "reverse_proxy_reject_count": truth_eval_reverse_reject,
    }

    non_truth_idx = [i for i, t in enumerate(truth_evaluated) if not t]
    non_truth_proxy_scores = [parse_float(trace_rows[i].get("proxy_score_proposal")) for i in non_truth_idx]
    non_truth_dcopf_success = [dcopf_success[i] for i in non_truth_idx]
    non_truth_subset = {
        "n": len(non_truth_idx),
        "proxy_score_distribution": numeric_distribution(non_truth_proxy_scores),
        "dcopf_success_true_count": sum(1 for x in non_truth_dcopf_success if x is True),
        "dcopf_success_false_count": sum(1 for x in non_truth_dcopf_success if x is False),
        "dcopf_success_none_count": sum(1 for x in non_truth_dcopf_success if x is None),
    }

    distributions = {
        "proxy_score_proposal": numeric_distribution([parse_float(r.get("proxy_score_proposal")) for r in trace_rows]),
        "truth_score_proposal": numeric_distribution([parse_float(r.get("truth_score_proposal")) for r in trace_rows]),
        "reverse_proxy_score": numeric_distribution([parse_float(r.get("reverse_proxy_score")) for r in trace_rows]),
        "truth_score_current": numeric_distribution([parse_float(r.get("truth_score_current")) for r in trace_rows]),
    }

    categorical = {
        "dcopf_success": {
            "true": sum(1 for x in dcopf_success if x is True),
            "false": sum(1 for x in dcopf_success if x is False),
            "none": sum(1 for x in dcopf_success if x is None),
        },
        "proxy_success_proposal": {
            "true": sum(1 for x in proxy_success_prop if x is True),
            "false": sum(1 for x in proxy_success_prop if x is False),
            "none": sum(1 for x in proxy_success_prop if x is None),
        },
        "truth_failed_proposal": {
            "true": sum(1 for x in truth_failed_prop if x is True),
            "false": sum(1 for x in truth_failed_prop if x is False),
            "none": sum(1 for x in truth_failed_prop if x is None),
        },
        "stage1_accept": {"true": int(sum(stage1_accept)), "false": int(total_proposals - sum(stage1_accept))},
        "final_accept": {"true": int(sum(final_accept)), "false": int(total_proposals - sum(final_accept))},
        "reverse_proxy_reject": {
            "true": int(sum(reverse_proxy_reject)),
            "false": int(total_proposals - sum(reverse_proxy_reject)),
        },
        "n_line_out": {
            "min": min(v for v in n_line_out if v is not None) if any(v is not None for v in n_line_out) else None,
            "max": max(v for v in n_line_out if v is not None) if any(v is not None for v in n_line_out) else None,
            "mean": statistics.fmean([v for v in n_line_out if v is not None]) if any(v is not None for v in n_line_out) else None,
        },
    }

    # Relationship tables (2x2)
    rel_stage_truth_final = defaultdict(int)
    rel_reverse_final = defaultdict(int)
    rel_truthfailed_final = defaultdict(int)
    for i in range(total_proposals):
        rel_stage_truth_final[(bool(stage1_accept[i]), bool(truth_evaluated[i]), bool(final_accept[i]))] += 1
        rel_reverse_final[(bool(reverse_proxy_reject[i]), bool(final_accept[i]))] += 1
        tf = truth_failed_prop[i]
        rel_truthfailed_final[(tf, bool(final_accept[i]))] += 1

    summary_rows: list[dict[str, Any]] = []
    summary_rows.append({"row_type": "overall", **overall})
    for row in by_level_rows:
        summary_rows.append({"row_type": "by_level", **row})
    summary_rows.append({"row_type": "truth_evaluated_subset", **truth_subset})
    summary_rows.append({"row_type": "non_truth_subset", "n": non_truth_subset["n"]})
    for name, dist in distributions.items():
        summary_rows.append({"row_type": "distribution", "field": name, **dist})

    for (s1, te, fa), cnt in sorted(rel_stage_truth_final.items()):
        summary_rows.append(
            {
                "row_type": "rel_stage1_truth_final",
                "stage1_accept": s1,
                "truth_evaluated": te,
                "final_accept": fa,
                "count": cnt,
            }
        )
    for (rr, fa), cnt in sorted(rel_reverse_final.items()):
        summary_rows.append(
            {
                "row_type": "rel_reverse_final",
                "reverse_proxy_reject": rr,
                "final_accept": fa,
                "count": cnt,
            }
        )
    for (tf, fa), cnt in sorted(rel_truthfailed_final.items(), key=lambda x: (str(x[0][0]), x[0][1])):
        summary_rows.append(
            {
                "row_type": "rel_truthfailed_final",
                "truth_failed_proposal": tf,
                "final_accept": fa,
                "count": cnt,
            }
        )

    write_csv(out_csv, summary_rows)

    payload = {
        "stage": "da_trace_analysis_v001",
        "inputs": {
            "trace_tsv": str(args.trace_tsv),
            "run_csv": str(args.run_csv),
        },
        "run_csv_row": run_row,
        "consistency_checks": checks,
        "overall": overall,
        "by_level": by_level_rows,
        "truth_evaluated_subset": truth_subset,
        "non_truth_evaluated_subset": non_truth_subset,
        "score_distributions": distributions,
        "categorical_counts": categorical,
        "relationship_tables": {
            "stage1_accept_vs_truth_evaluated_vs_final_accept": [
                {"stage1_accept": k[0], "truth_evaluated": k[1], "final_accept": k[2], "count": v}
                for k, v in sorted(rel_stage_truth_final.items())
            ],
            "reverse_proxy_reject_vs_final_accept": [
                {"reverse_proxy_reject": k[0], "final_accept": k[1], "count": v}
                for k, v in sorted(rel_reverse_final.items())
            ],
            "truth_failed_proposal_vs_final_accept": [
                {"truth_failed_proposal": k[0], "final_accept": k[1], "count": v}
                for k, v in sorted(rel_truthfailed_final.items(), key=lambda x: (str(x[0][0]), x[0][1]))
            ],
        },
    }
    out_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    md_lines = [
        "# DA Trace Analysis case118 N1000 seed901 v001",
        "",
        f"- trace tsv: `{args.trace_tsv}`",
        f"- run csv: `{args.run_csv}`",
        "",
        "## Consistency Checks",
        "",
    ]
    for key, value in checks.items():
        md_lines.append(f"- {key}: `{value}`")

    md_lines.extend(
        [
            "",
            "## Overall",
            "",
            f"- total_proposals: `{overall['total_proposals']}`",
            f"- stage1_accept: `{overall['stage1_accept_count']}` ({fmt(overall['stage1_accept_rate'])})",
            f"- truth_evaluated: `{overall['truth_evaluated_count']}` ({fmt(overall['truth_evaluated_rate'])})",
            f"- final_accept: `{overall['final_accept_count']}` ({fmt(overall['final_accept_rate'])})",
            f"- reverse_proxy_reject: `{overall['reverse_proxy_reject_count']}` ({fmt(overall['reverse_proxy_reject_rate'])})",
            "",
            "## By Level",
            "",
            "| level | proposals | stage1_accept | truth_evaluated | final_accept | reverse_proxy_reject |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in by_level_rows:
        md_lines.append(
            f"| {row['level']} | {row['proposals']} | {row['stage1_accept_count']} ({fmt(row['stage1_accept_rate'])}) | {row['truth_evaluated_count']} ({fmt(row['truth_evaluated_rate'])}) | {row['final_accept_count']} ({fmt(row['final_accept_rate'])}) | {row['reverse_proxy_reject_count']} ({fmt(row['reverse_proxy_reject_rate'])}) |"
        )

    md_lines.extend(
        [
            "",
            "## Truth-evaluated Subset",
            "",
            f"- n: `{truth_subset['n']}`",
            f"- ACOPF failed: `{truth_subset['acopf_failed_count']}`",
            f"- ACOPF safe: `{truth_subset['acopf_safe_count']}`",
            f"- failed_fraction: `{fmt(truth_subset['failed_fraction'])}`",
            f"- final_accept: `{truth_subset['final_accept_count']}`",
            f"- final_reject: `{truth_subset['final_reject_count']}`",
            f"- reverse_proxy_reject: `{truth_subset['reverse_proxy_reject_count']}`",
            "",
            "## Interpretation",
            "",
        ]
    )
    if truth_subset["acopf_safe_count"] == 0 and truth_subset["acopf_failed_count"] > 0:
        md_lines.append(
            "- All DA truth-evaluated proposals are ACOPF failures in this trace. Remaining DA truth calls are confirmation calls for failed proposals, not checks of safe proposals."
        )
    else:
        md_lines.append(
            "- DA truth-evaluated proposals include both failures and safe cases in this trace; DA truth calls are not purely confirmation calls."
        )
    md_lines.append(
        "- Any DA shortcut must be preceded by cross-regime certificate audit before changing online DA logic."
    )

    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"wrote csv: {out_csv}")
    print(f"wrote json: {out_json}")
    print(f"wrote md: {out_md}")


if __name__ == "__main__":
    main()
