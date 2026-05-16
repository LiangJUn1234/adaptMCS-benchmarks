#!/usr/bin/env python3
"""A2.2c DA-stage diagnostic readiness audit (run-level outputs only)."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            return [x for x in payload["rows"] if isinstance(x, dict)]
        return [payload]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--failure-label-csv",
        type=Path,
        default=Path("ac_ext/experiments/out/final_guard_failure_label_case118_N1000_lop0008_seeds901_903.csv"),
    )
    parser.add_argument(
        "--failure-label-json",
        type=Path,
        default=Path("ac_ext/experiments/out/final_guard_failure_label_case118_N1000_lop0008_seeds901_903.json"),
    )
    parser.add_argument(
        "--legacy-csv",
        type=Path,
        default=Path("ac_ext/experiments/out/final_guard_legacy_case118_N1000_lop0008_seeds901_903.csv"),
    )
    parser.add_argument(
        "--legacy-json",
        type=Path,
        default=Path("ac_ext/experiments/out/final_guard_legacy_case118_N1000_lop0008_seeds901_903.json"),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("ac_ext/experiments/out/dcopf_da_stage_score_potential_case118_v001"),
    )
    args = parser.parse_args()

    out_prefix = args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_md = out_prefix.with_suffix(".md")
    out_json = out_prefix.with_suffix(".json")

    fl_csv_rows = load_csv_rows(args.failure_label_csv)
    lg_csv_rows = load_csv_rows(args.legacy_csv)
    fl_json_rows = load_json_rows(args.failure_label_json)
    lg_json_rows = load_json_rows(args.legacy_json)

    if not fl_csv_rows:
        raise ValueError("empty failure-label CSV")
    if not lg_csv_rows:
        raise ValueError("empty legacy CSV")

    csv_fields = sorted(set(fl_csv_rows[0].keys()) | set(lg_csv_rows[0].keys()))
    json_fields = sorted(set(fl_json_rows[0].keys()) | set(lg_json_rows[0].keys())) if (fl_json_rows and lg_json_rows) else []

    available_summary_fields = [
        "pf_hat",
        "truth_calls",
        "proxy_calls",
        "acceptance_rate",
        "reverse_proxy_rejects",
        "l0_guard_mode",
        "l0_truth_calls",
        "l0_prescreen_K_initial",
        "l0_prescreen_K_final",
        "l0_tail_audit_count",
        "l0_tail_audit_failure_hits",
        "level_acceptance_rates_json",
    ]

    required_proposal_fields = [
        "run_id",
        "arm_name",
        "seed",
        "level",
        "proposal_index",
        "current_sample_id",
        "proposal_sample_id",
        "proxy_mode",
        "l0_guard_mode",
        "proxy_score_current",
        "proxy_score_proposal",
        "truth_score_current",
        "truth_score_proposal",
        "truth_success_current",
        "truth_success_proposal",
        "truth_failed_current",
        "truth_failed_proposal",
        "stage1_accept",
        "final_accept",
        "reverse_proxy_reject",
        "truth_evaluated",
        "proxy_evaluated",
        "wall_time_proxy",
        "wall_time_truth",
    ]

    optional_fields = [
        "damage_state_hash",
        "n_line_out",
        "dcopf_success",
        "l0_score",
        "da_score",
        "flow_score",
    ]

    fields_union = set(csv_fields) | set(json_fields)
    missing_required = [f for f in required_proposal_fields if f not in fields_union]

    readiness = {
        "stage": "A2.2c",
        "title": "DA-stage diagnostic readiness audit",
        "conclusion": {
            "current_final_guard_outputs_sufficient_for_da_stage_analysis": False,
            "reason": "run-level summary only; no per-proposal DA trajectory",
            "da_side_score_training_ready": False,
            "da_gate_redesign_ready": False,
        },
        "input_files": {
            "failure_label_csv": str(args.failure_label_csv),
            "failure_label_json": str(args.failure_label_json),
            "legacy_csv": str(args.legacy_csv),
            "legacy_json": str(args.legacy_json),
        },
        "current_da_data_availability": {
            "csv_fields": csv_fields,
            "json_fields": json_fields,
            "available_run_level_summary_fields": [f for f in available_summary_fields if f in fields_union],
            "missing_proposal_level_required_fields": missing_required,
        },
        "consequence": [
            "cannot estimate whether pseudo-limit score would improve DA-stage rejection",
            "cannot train da_score",
            "cannot compare DA score scales",
            "cannot diagnose why upper-level truth calls remain after L0 reduction",
            "cannot safely modify DA yet",
        ],
        "recommended_minimal_instrumentation": {
            "enable_flag": {
                "cli": "--da-trace-enabled",
                "config": "da_trace_enabled: false",
            },
            "required_fields": required_proposal_fields,
            "optional_fields": optional_fields,
            "output_format_options": ["TSV", "Parquet", "NPZ"],
        },
        "safety_requirements": [
            "disabled by default",
            "must not change DA decisions",
            "must not change random seeds",
            "must not change acceptance/rejection logic",
            "must not change truth/proxy calls except logging overhead",
            "write output only when enabled",
            "small enough for N=1000 debug runs first",
        ],
        "recommended_next_step_after_a2_2": {
            "if_a2_2a_improves": "prioritize A3 wrapper-level proxy / tuned L0 guard",
            "if_a2_2a_saturated_and_a2_2b_no_gain": "implement DA trace instrumentation before touching DA",
        },
    }

    out_json.write_text(json.dumps(readiness, indent=2), encoding="utf-8")

    md = [
        "# A2.2c DA-stage Diagnostic Readiness Audit",
        "",
        "## Current DA Data Availability",
        "",
        "Current `final_guard_*` CSV/JSON provides run-level summaries only:",
        "- arm-level `pf_hat`",
        "- `truth_calls`",
        "- `proxy_calls`",
        "- `acceptance_rate`",
        "- `reverse_proxy_rejects`",
        "- L0 metadata",
        "- level acceptance summary",
        "",
        "Missing proposal-level trajectory fields:",
    ]
    for f in required_proposal_fields:
        md.append(f"- `{f}`")
    md.extend(
        [
            "",
            "## Consequence",
            "",
            "Because proposal-level records are absent:",
            "- cannot estimate whether pseudo-limit score would improve DA-stage rejection",
            "- cannot train `da_score`",
            "- cannot compare DA score scales",
            "- cannot diagnose why upper-level truth calls remain after L0 reduction",
            "- cannot safely modify DA yet",
            "",
            "## Recommended Minimal Instrumentation",
            "",
            "Introduce disabled-by-default tracing:",
            "- CLI flag: `--da-trace-enabled`",
            "- config field: `da_trace_enabled: false`",
            "",
            "When enabled, write one row per DA proposal with required fields:",
        ]
    )
    for f in required_proposal_fields:
        md.append(f"- `{f}`")
    md.extend(
        [
            "",
            "Optional fields:",
        ]
    )
    for f in optional_fields:
        md.append(f"- `{f}`")
    md.extend(
        [
            "",
            "## Safety Requirements",
            "",
            "- disabled by default",
            "- no DA decision change",
            "- no random seed change",
            "- no acceptance logic change",
            "- no truth/proxy call behavior change except logging overhead",
            "- write only when enabled",
            "- start with N=1000 debug-size runs",
            "",
            "## Conclusion",
            "",
            "- current final_guard outputs are insufficient for DA-stage score analysis",
            "- no per-proposal proxy/truth trajectory is available",
            "- DA-side score training or DA gate redesign cannot be evaluated yet",
            "- next step requires disabled-by-default instrumentation",
            "",
            "Do not implement instrumentation in this task.",
        ]
    )
    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"wrote report: {out_md}")
    print(f"wrote json: {out_json}")


if __name__ == "__main__":
    main()
