"""Run Stage-1 false-reject shadow audit for delayed-acceptance controller."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

from ac_ext.config import DEFAULTS
from ac_ext.sus_controller import SuSController


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage-1 false-reject shadow audit runner")
    parser.add_argument("--case", dest="case_name", required=True)
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--sus-p0", type=float, required=True)
    parser.add_argument("--max-levels", type=int, required=True)
    parser.add_argument("--target-violation", type=float, required=True)
    parser.add_argument("--line-outage-prob", type=float, required=True)
    parser.add_argument("--bus-outage-prob", type=float, required=True)
    parser.add_argument("--audit-shadow-prob", type=float, required=True)
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def _write_level_csv(path: Path, level_logs: List[Mapping[str, Any]]) -> None:
    fieldnames = [
        "level",
        "threshold",
        "n_samples",
        "n_seed",
        "n_proxy_calls",
        "n_truth_calls",
        "stage1_reject_total",
        "stage1_reject_shadow_eval_count",
        "stage1_reject_shadow_truth_pass_count",
        "stage1_reject_shadow_truth_fail_count",
        "stage1_reject_shadow_truth_accept_rate",
    ]

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for log in level_logs:
            writer.writerow(
                {
                    "level": log.get("level"),
                    "threshold": log.get("threshold"),
                    "n_samples": log.get("n_samples"),
                    "n_seed": log.get("n_seed"),
                    "n_proxy_calls": log.get("n_proxy_calls"),
                    "n_truth_calls": log.get("n_truth_calls"),
                    "stage1_reject_total": log.get("stage1_reject_total"),
                    "stage1_reject_shadow_eval_count": log.get("stage1_reject_shadow_eval_count"),
                    "stage1_reject_shadow_truth_pass_count": log.get("stage1_reject_shadow_truth_pass_count"),
                    "stage1_reject_shadow_truth_fail_count": log.get("stage1_reject_shadow_truth_fail_count"),
                    "stage1_reject_shadow_truth_accept_rate": log.get("stage1_reject_shadow_truth_accept_rate"),
                }
            )


def main() -> None:
    args = _parse_args()

    cfg = dict(DEFAULTS)
    cfg.update(
        {
            "sus_p0": float(args.sus_p0),
            "max_levels": int(args.max_levels),
            "target_violation": float(args.target_violation),
            "line_outage_prob": float(args.line_outage_prob),
            "bus_outage_prob": float(args.bus_outage_prob),
            "evaluator_mode": "delayed_acceptance",
            "proxy_mode": "dcopf",
            "truth_mode": "acopf",
            "audit_shadow_prob": float(args.audit_shadow_prob),
        }
    )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    run_result: Dict[str, Any] | None = None
    run_error: str | None = None
    try:
        run_result = SuSController(args.case_name, cfg).run(int(args.N), seed=int(args.seed))
    except Exception as exc:
        run_error = f"{type(exc).__name__}: {exc}"

    if run_result is None:
        level_logs: List[Mapping[str, Any]] = []
        summary = {
            "case": args.case_name,
            "seed": int(args.seed),
            "evaluator_mode": "delayed_acceptance",
            "proxy_mode": "dcopf",
            "truth_mode": "acopf",
            "audit_shadow_prob": float(args.audit_shadow_prob),
            "error": run_error,
            "stage1_reject_total": 0,
            "stage1_reject_shadow_eval_count": 0,
            "stage1_reject_shadow_truth_pass_count": 0,
            "stage1_reject_shadow_truth_fail_count": 0,
            "stage1_reject_shadow_truth_accept_rate": None,
        }
    else:
        level_logs = list(run_result.get("level_logs", []))
        reject_total = int(run_result.get("stage1_reject_total", 0))
        shadow_eval_count = int(run_result.get("stage1_reject_shadow_eval_count", 0))
        shadow_pass = int(run_result.get("stage1_reject_shadow_truth_pass_count", 0))
        shadow_fail = int(run_result.get("stage1_reject_shadow_truth_fail_count", 0))
        shadow_rate = (
            shadow_pass / float(shadow_eval_count) if shadow_eval_count > 0 else None
        )

        summary = {
            "case": args.case_name,
            "seed": int(args.seed),
            "evaluator_mode": run_result.get("evaluator_mode", "delayed_acceptance"),
            "proxy_mode": run_result.get("proxy_mode", "dcopf"),
            "truth_mode": run_result.get("truth_mode", "acopf"),
            "termination_reason": run_result.get("termination_reason"),
            "n_levels": run_result.get("n_levels"),
            "pf_hat": run_result.get("pf_hat"),
            "audit_shadow_prob": float(args.audit_shadow_prob),
            "n_proxy_calls": run_result.get("n_proxy_calls"),
            "n_truth_calls": run_result.get("n_truth_calls"),
            "stage1_reject_total": reject_total,
            "stage1_reject_shadow_eval_count": shadow_eval_count,
            "stage1_reject_shadow_truth_pass_count": shadow_pass,
            "stage1_reject_shadow_truth_fail_count": shadow_fail,
            "stage1_reject_shadow_truth_accept_rate": shadow_rate,
        }

    summary_path = outdir / "false_reject_audit_summary.json"
    levels_path = outdir / "false_reject_audit_levels.csv"

    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)

    _write_level_csv(levels_path, level_logs)

    print(
        json.dumps(
            {
                "case": args.case_name,
                "outdir": str(outdir),
                "audit_shadow_prob": float(args.audit_shadow_prob),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
