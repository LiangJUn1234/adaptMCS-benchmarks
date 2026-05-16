#!/usr/bin/env python3
"""Build combined A2.2 offline comparison artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_float(v: Any, default: float = float("nan")) -> float:
    try:
        return float(v)
    except Exception:
        return default


def to_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y"}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    cols: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                cols.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a2-2a-csv", type=Path, default=Path("ac_ext/experiments/out/dcopf_l0_guard_tuning_case118_v001.csv"))
    parser.add_argument("--a2-2b-csv", type=Path, default=Path("ac_ext/experiments/out/dcopf_failed_state_severity_scores_case118_v001.csv"))
    parser.add_argument("--a2-2c-json", type=Path, default=Path("ac_ext/experiments/out/dcopf_da_stage_score_potential_case118_v001.json"))
    parser.add_argument("--out-prefix", type=Path, default=Path("ac_ext/experiments/out/a2_2_offline_comparison_case118_v001"))
    args = parser.parse_args()

    out_prefix = args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_md = out_prefix.with_suffix(".md")
    out_csv = out_prefix.with_suffix(".csv")
    out_json = out_prefix.with_suffix(".json")

    rows_a = read_csv(args.a2_2a_csv)
    rows_b = read_csv(args.a2_2b_csv)
    audit_c = json.loads(args.a2_2c_json.read_text(encoding="utf-8"))

    if not rows_a:
        raise ValueError("A2.2a CSV is empty")
    if not rows_b:
        raise ValueError("A2.2b CSV is empty")

    def k(row: dict[str, str]) -> tuple[Any, ...]:
        return (
            0 if to_bool(row.get("pass_all_lops")) else 1,
            to_float(row.get("mean_l0_truth_calls")),
            to_int(row.get("max_K_final")),
            to_int(row.get("K_initial")),
            to_int(row.get("score_priority"), 9),
            row.get("score_name", ""),
        )

    best_a = sorted(rows_a, key=k)[0]
    best_b = sorted(rows_b, key=k)[0]

    summary_rows = [
        {
            "section": "A2.2a",
            "best_score": best_a.get("score_name"),
            "K_initial": to_int(best_a.get("K_initial")),
            "tail_audit": to_int(best_a.get("tail_audit")),
            "expand_factor": to_float(best_a.get("expand_factor")),
            "pass_all_lops": to_bool(best_a.get("pass_all_lops")),
            "mean_l0_truth_calls": to_float(best_a.get("mean_l0_truth_calls")),
            "max_K_final": to_int(best_a.get("max_K_final")),
            "max_tail_audit_failure_hits": to_int(best_a.get("max_tail_audit_failure_hits")),
            "mean_top100_recall": to_float(best_a.get("mean_top100_recall")),
            "mean_top200_recall": to_float(best_a.get("mean_top200_recall")),
        },
        {
            "section": "A2.2b",
            "best_score": best_b.get("score_name"),
            "K_initial": to_int(best_b.get("K_initial")),
            "tail_audit": to_int(best_b.get("tail_audit")),
            "expand_factor": to_float(best_b.get("expand_factor")),
            "pass_all_lops": to_bool(best_b.get("pass_all_lops")),
            "mean_l0_truth_calls": to_float(best_b.get("mean_l0_truth_calls")),
            "max_K_final": to_int(best_b.get("max_K_final")),
            "max_tail_audit_failure_hits": to_int(best_b.get("max_tail_audit_failure_hits")),
            "mean_top100_recall": to_float(best_b.get("mean_top100_recall")),
            "mean_top200_recall": to_float(best_b.get("mean_top200_recall")),
        },
    ]

    # Decision logic
    a_pass = to_bool(best_a.get("pass_all_lops"))
    b_pass = to_bool(best_b.get("pass_all_lops"))
    a_l0 = to_float(best_a.get("mean_l0_truth_calls"))
    b_l0 = to_float(best_b.get("mean_l0_truth_calls"))
    a_k0 = to_int(best_a.get("K_initial"))
    b_name = str(best_b.get("score_name", ""))

    if a_pass and a_k0 < 200:
        recommendation = "proceed_to_A3_wrapper_level_proxy_with_tuned_guard"
        recommendation_reason = "A2.2a found safe K_initial below 200 with pass_all_lops=True"
    elif (not a_pass) and (not b_pass):
        recommendation = "proceed_to_DA_instrumentation"
        recommendation_reason = "A2.2a and A2.2b both fail pass_all_lops; DA trace is required before DA-side redesign"
    elif a_pass and (b_l0 + 1e-9) < a_l0 and b_name != "raw_success_fail":
        recommendation = "proceed_to_A2.2b_score_variant_then_A3"
        recommendation_reason = "A2.2b improves mean_l0_truth_calls while retaining pass_all_lops"
    elif a_pass:
        recommendation = "hold_A2_and_keep_raw_failure_label_guard"
        recommendation_reason = "A2.2a is already saturated and A2.2b does not provide practical gain"
    else:
        recommendation = "proceed_to_A4_formulation_level_optimization"
        recommendation_reason = "A2 score/guard tuning could not produce robust safe gains"

    da_availability = audit_c.get("current_da_data_availability", {})
    da_required_missing = da_availability.get("missing_proposal_level_required_fields", [])

    combined = {
        "stage": "A2.2",
        "purpose": "A2.1 reached a ceiling at K=200/tail=50; compare A2.2a/A2.2b/A2.2c offline directions.",
        "a2_2a_best": best_a,
        "a2_2b_best": best_b,
        "a2_2c": {
            "current_final_guard_outputs_sufficient_for_da_stage_analysis": audit_c["conclusion"]["current_final_guard_outputs_sufficient_for_da_stage_analysis"],
            "da_side_score_training_ready": audit_c["conclusion"]["da_side_score_training_ready"],
            "da_gate_redesign_ready": audit_c["conclusion"]["da_gate_redesign_ready"],
            "reason": audit_c["conclusion"]["reason"],
            "current_da_data_availability": {
                "available_run_level_summary_fields": da_availability.get("available_run_level_summary_fields", []),
                "missing_proposal_level_required_fields": da_required_missing,
            },
        },
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "literature_relation": {
            "note": "Taheri & Molzahn optimize DC approximation parameters with AC/ACOPF teacher data. A2.2 here remains score/guard parameter training; A4 is the later formulation-level stage closer to that literature.",
        },
    }

    out_json.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    write_csv(out_csv, summary_rows)

    md = [
        "# A2.2 Offline Comparison v001",
        "",
        "## 1. Purpose",
        "",
        "- A2.1 reached ceiling behavior at `K_initial=200, tail_audit=50` on validation per-lop view.",
        "- A2.2 compares three next directions: A2.2a guard tuning, A2.2b failed-state severity tie-break, A2.2c DA-stage readiness audit.",
        "",
        "## 2. A2.2a Result",
        "",
        f"- best score/config: `{best_a.get('score_name')}`, `K_initial={best_a.get('K_initial')}`, `tail_audit={best_a.get('tail_audit')}`, `expand_factor={best_a.get('expand_factor')}`",
        f"- pass_all_lops: `{best_a.get('pass_all_lops')}`",
        f"- mean_l0_truth_calls: `{best_a.get('mean_l0_truth_calls')}`",
        f"- max_K_final: `{best_a.get('max_K_final')}`",
        "",
        "## 3. A2.2b Result",
        "",
        f"- best score/config: `{best_b.get('score_name')}`, `K_initial={best_b.get('K_initial')}`, `tail_audit={best_b.get('tail_audit')}`, `expand_factor={best_b.get('expand_factor')}`",
        f"- pass_all_lops: `{best_b.get('pass_all_lops')}`",
        f"- mean_l0_truth_calls: `{best_b.get('mean_l0_truth_calls')}`",
        f"- max_K_final: `{best_b.get('max_K_final')}`",
        "",
        "## 4. A2.2c Result",
        "",
        "### Current DA Data Availability",
        "",
        "- current final_guard CSV/JSON is run-level summary only",
        "- available: pf_hat / truth_calls / proxy_calls / acceptance_rate / reverse_proxy_rejects / l0 metadata / level acceptance summary",
        f"- missing proposal-level required fields: `{len(da_required_missing)}`",
        "",
        "### Consequence",
        "",
        "- current final_guard outputs are insufficient for DA-stage score analysis",
        "- no per-proposal proxy/truth trajectory is available",
        "- DA-side score training or DA gate redesign cannot be evaluated yet",
        "- disabled-by-default instrumentation is required before DA-side changes",
        "",
        "### Recommended Minimal Instrumentation",
        "",
        "- disabled-by-default flag: `--da-trace-enabled` or `da_trace_enabled: false`",
        "- required fields include proposal_id/level/current-vs-proposal proxy+truth scores/stage1+final accepts/reverse_proxy_reject/timing",
        "- instrumentation must be logging-only and must not alter DA decisions or RNG state",
        "",
        "## 5. Recommended Next Step",
        "",
        f"- `{recommendation}`",
        f"- rationale: {recommendation_reason}",
        "",
        "## 6. Relation to Literature",
        "",
        "- Taheri & Molzahn optimize DC approximation parameters using AC/ACOPF teacher data.",
        "- This A2.2 comparison remains score/guard parameter training.",
        "- A4 is the later stage closer to formulation-level coefficient/bias optimization.",
    ]
    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"wrote combined md: {out_md}")
    print(f"wrote combined csv: {out_csv}")
    print(f"wrote combined json: {out_json}")


if __name__ == "__main__":
    main()
