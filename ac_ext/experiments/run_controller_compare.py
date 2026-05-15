"""Run controller-mode comparison arms for Phase 6B.1."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from ac_ext.config import DEFAULTS
from ac_ext.sus_controller import SuSController


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SuS controller comparison arms")
    parser.add_argument("--case", dest="case_name", required=True)
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--sus-p0", type=float, required=True)
    parser.add_argument("--max-levels", type=int, required=True)
    parser.add_argument("--target-violation", type=float, required=True)
    parser.add_argument("--line-outage-prob", type=float, required=True)
    parser.add_argument("--bus-outage-prob", type=float, required=True)
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def _mean_or_none(values: Iterable[float | None]) -> float | None:
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return None
    return sum(xs) / float(len(xs))


def _summarize_arm(
    result: Mapping[str, Any] | None,
    *,
    case_name: str,
    seed: int,
    n_samples: int,
    evaluator_mode: str,
    proxy_mode: str | None,
    truth_mode: str,
    error: str | None,
) -> Dict[str, Any]:
    if result is None:
        return {
            "case": case_name,
            "seed": seed,
            "N": n_samples,
            "evaluator_mode": evaluator_mode,
            "proxy_mode": proxy_mode,
            "truth_mode": truth_mode,
            "termination_reason": f"error:{error}",
            "n_levels": None,
            "pf_hat": None,
            "n_proxy_calls_total": 0,
            "n_truth_calls_total": 0,
            "stage1_reject_ratio_mean": None,
            "stage2_accept_ratio_mean": None,
        }

    level_logs = list(result.get("level_logs", []))
    n_proxy_calls_total = int(sum(int(log.get("n_proxy_calls", 0)) for log in level_logs))
    n_truth_calls_total = int(sum(int(log.get("n_truth_calls", 0)) for log in level_logs))

    stage1_mean = _mean_or_none(log.get("stage1_reject_ratio") for log in level_logs)
    stage2_mean = _mean_or_none(log.get("stage2_accept_ratio") for log in level_logs)

    return {
        "case": case_name,
        "seed": seed,
        "N": n_samples,
        "evaluator_mode": evaluator_mode,
        "proxy_mode": proxy_mode,
        "truth_mode": truth_mode,
        "termination_reason": result.get("termination_reason"),
        "n_levels": result.get("n_levels"),
        "pf_hat": result.get("pf_hat"),
        "n_proxy_calls_total": n_proxy_calls_total,
        "n_truth_calls_total": n_truth_calls_total,
        "stage1_reject_ratio_mean": stage1_mean,
        "stage2_accept_ratio_mean": stage2_mean,
    }


def _write_outputs(outdir: Path, records: List[Dict[str, Any]]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / "controller_compare_summary.json"
    csv_path = outdir / "controller_compare_summary.csv"

    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, sort_keys=True)

    fieldnames = [
        "case",
        "seed",
        "N",
        "evaluator_mode",
        "proxy_mode",
        "truth_mode",
        "termination_reason",
        "n_levels",
        "pf_hat",
        "n_proxy_calls_total",
        "n_truth_calls_total",
        "stage1_reject_ratio_mean",
        "stage2_accept_ratio_mean",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    args = _parse_args()

    base_cfg: Dict[str, Any] = dict(DEFAULTS)
    base_cfg.update(
        {
            "sus_p0": float(args.sus_p0),
            "max_levels": int(args.max_levels),
            "target_violation": float(args.target_violation),
            "line_outage_prob": float(args.line_outage_prob),
            "bus_outage_prob": float(args.bus_outage_prob),
            "truth_mode": "acopf",
        }
    )

    arms = [
        {"evaluator_mode": "truth_only", "truth_mode": "acopf", "proxy_mode": None},
        {"evaluator_mode": "proxy_only", "truth_mode": "acopf", "proxy_mode": "fdxb"},
        {"evaluator_mode": "proxy_only", "truth_mode": "acopf", "proxy_mode": "dcopf"},
        {"evaluator_mode": "delayed_acceptance", "truth_mode": "acopf", "proxy_mode": "fdxb"},
        {"evaluator_mode": "delayed_acceptance", "truth_mode": "acopf", "proxy_mode": "dcopf"},
    ]

    records: List[Dict[str, Any]] = []

    for arm in arms:
        cfg = dict(base_cfg)
        cfg["evaluator_mode"] = arm["evaluator_mode"]
        cfg["truth_mode"] = arm["truth_mode"]
        if arm["proxy_mode"] is not None:
            cfg["proxy_mode"] = arm["proxy_mode"]

        result = None
        error = None
        try:
            controller = SuSController(args.case_name, cfg)
            result = controller.run(args.N, seed=args.seed)
        except Exception as exc:  # keep runner robust across unavailable local solvers
            error = f"{type(exc).__name__}: {exc}"

        rec = _summarize_arm(
            result,
            case_name=args.case_name,
            seed=args.seed,
            n_samples=args.N,
            evaluator_mode=arm["evaluator_mode"],
            proxy_mode=arm["proxy_mode"],
            truth_mode=arm["truth_mode"],
            error=error,
        )
        records.append(rec)

    outdir = Path(args.outdir)
    _write_outputs(outdir, records)

    print(
        json.dumps(
            {
                "case": args.case_name,
                "outdir": str(outdir),
                "records_written": len(records),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
