"""Paired repeated-run bias/stability check for Phase 6B.2."""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from ac_ext.config import DEFAULTS
from ac_ext.sus_controller import SuSController


def _parse_seeds(raw: str) -> List[int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("--seeds must contain at least one integer")
    return [int(p) for p in parts]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paired truth-vs-DA bias check")
    parser.add_argument("--case", dest="case_name", required=True)
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--sus-p0", type=float, required=True)
    parser.add_argument("--max-levels", type=int, required=True)
    parser.add_argument("--target-violation", type=float, required=True)
    parser.add_argument("--line-outage-prob", type=float, required=True)
    parser.add_argument("--bus-outage-prob", type=float, required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--outdir", required=True)
    return parser.parse_args()


def _mean_or_none(values: Iterable[float | int | None]) -> float | None:
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return None
    return sum(xs) / float(len(xs))


def _std_or_none(values: Iterable[float | int | None]) -> float | None:
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return None
    if len(xs) == 1:
        return 0.0
    return statistics.pstdev(xs)


def _bootstrap_mean_ci95(
    values: Sequence[float | int | None],
    *,
    n_boot: int = 1000,
    seed: int = 0,
) -> List[float] | None:
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return None

    rng = random.Random(seed)
    n = len(xs)
    boots: List[float] = []
    for _ in range(n_boot):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(sample) / float(n))

    boots.sort()
    lo_idx = int(0.025 * (n_boot - 1))
    hi_idx = int(0.975 * (n_boot - 1))
    return [boots[lo_idx], boots[hi_idx]]


def _run_arm(
    *,
    case_name: str,
    n_samples: int,
    seed: int,
    base_config: Mapping[str, Any],
    evaluator_mode: str,
    truth_mode: str,
    proxy_mode: str | None,
) -> Dict[str, Any]:
    cfg = dict(base_config)
    cfg["evaluator_mode"] = evaluator_mode
    cfg["truth_mode"] = truth_mode
    if proxy_mode is not None:
        cfg["proxy_mode"] = proxy_mode

    result: Mapping[str, Any] | None = None
    error: str | None = None

    try:
        result = SuSController(case_name, cfg).run(n_samples, seed=seed)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    if result is None:
        return {
            "seed": seed,
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

    logs = list(result.get("level_logs", []))
    n_proxy_calls_total = int(sum(int(log.get("n_proxy_calls", 0)) for log in logs))
    n_truth_calls_total = int(sum(int(log.get("n_truth_calls", 0)) for log in logs))

    return {
        "seed": seed,
        "evaluator_mode": evaluator_mode,
        "proxy_mode": proxy_mode,
        "truth_mode": truth_mode,
        "termination_reason": result.get("termination_reason"),
        "n_levels": result.get("n_levels"),
        "pf_hat": result.get("pf_hat"),
        "n_proxy_calls_total": n_proxy_calls_total,
        "n_truth_calls_total": n_truth_calls_total,
        "stage1_reject_ratio_mean": _mean_or_none(log.get("stage1_reject_ratio") for log in logs),
        "stage2_accept_ratio_mean": _mean_or_none(log.get("stage2_accept_ratio") for log in logs),
    }


def _pair_rows(arm_runs: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_seed: Dict[int, Dict[str, Mapping[str, Any]]] = {}

    for rec in arm_runs:
        seed = int(rec["seed"])
        by_seed.setdefault(seed, {})
        key = f"{rec['evaluator_mode']}|{rec.get('proxy_mode')}|{rec['truth_mode']}"
        by_seed[seed][key] = rec

    rows: List[Dict[str, Any]] = []
    for seed in sorted(by_seed.keys()):
        mapping = by_seed[seed]
        truth = mapping.get("truth_only|None|acopf")
        da = mapping.get("delayed_acceptance|dcopf|acopf")

        pf_truth = None if truth is None else truth.get("pf_hat")
        pf_da = None if da is None else da.get("pf_hat")

        if pf_truth is not None and pf_da is not None:
            delta_pf = float(pf_da) - float(pf_truth)
            rel_pf_ratio = (float(pf_da) / float(pf_truth)) if float(pf_truth) != 0.0 else None
        else:
            delta_pf = None
            rel_pf_ratio = None

        truth_calls_truth = None if truth is None else truth.get("n_truth_calls_total")
        truth_calls_da = None if da is None else da.get("n_truth_calls_total")

        if truth_calls_truth is not None and truth_calls_da is not None:
            saving = int(truth_calls_truth) - int(truth_calls_da)
            saving_frac = (saving / float(truth_calls_truth)) if int(truth_calls_truth) > 0 else None
        else:
            saving = None
            saving_frac = None

        rows.append(
            {
                "seed": seed,
                "pf_truth": pf_truth,
                "pf_da": pf_da,
                "delta_pf": delta_pf,
                "rel_pf_ratio": rel_pf_ratio,
                "truth_calls_truth": truth_calls_truth,
                "truth_calls_da": truth_calls_da,
                "truth_call_saving": saving,
                "truth_call_saving_frac": saving_frac,
            }
        )

    return rows


def _build_summary(
    *,
    case_name: str,
    seeds: Sequence[int],
    paired_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    pf_truth_vals = [row.get("pf_truth") for row in paired_rows]
    pf_da_vals = [row.get("pf_da") for row in paired_rows]
    delta_vals = [row.get("delta_pf") for row in paired_rows]
    tc_truth_vals = [row.get("truth_calls_truth") for row in paired_rows]
    tc_da_vals = [row.get("truth_calls_da") for row in paired_rows]
    saving_vals = [row.get("truth_call_saving") for row in paired_rows]
    saving_frac_vals = [row.get("truth_call_saving_frac") for row in paired_rows]

    return {
        "case": case_name,
        "n_seeds": len(seeds),
        "seeds": list(seeds),
        "mean_pf_truth": _mean_or_none(pf_truth_vals),
        "mean_pf_da": _mean_or_none(pf_da_vals),
        "mean_delta_pf": _mean_or_none(delta_vals),
        "std_delta_pf": _std_or_none(delta_vals),
        "mean_truth_calls_truth": _mean_or_none(tc_truth_vals),
        "mean_truth_calls_da": _mean_or_none(tc_da_vals),
        "mean_truth_call_saving": _mean_or_none(saving_vals),
        "mean_truth_call_saving_frac": _mean_or_none(saving_frac_vals),
        "std_truth_call_saving_frac": _std_or_none(saving_frac_vals),
        "delta_pf_ci95_bootstrap": _bootstrap_mean_ci95(delta_vals, n_boot=1000, seed=17),
        "truth_call_saving_frac_ci95_bootstrap": _bootstrap_mean_ci95(
            saving_frac_vals,
            n_boot=1000,
            seed=29,
        ),
    }


def _write_outputs(
    *,
    outdir: Path,
    arm_runs: Sequence[Mapping[str, Any]],
    paired_rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    arm_json = outdir / "arm_runs.json"
    paired_csv = outdir / "paired_comparison.csv"
    summary_json = outdir / "bias_check_summary.json"

    with arm_json.open("w", encoding="utf-8") as fh:
        json.dump(list(arm_runs), fh, indent=2, sort_keys=True)

    paired_fieldnames = [
        "seed",
        "pf_truth",
        "pf_da",
        "delta_pf",
        "rel_pf_ratio",
        "truth_calls_truth",
        "truth_calls_da",
        "truth_call_saving",
        "truth_call_saving_frac",
    ]
    with paired_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=paired_fieldnames)
        writer.writeheader()
        writer.writerows(paired_rows)

    with summary_json.open("w", encoding="utf-8") as fh:
        json.dump(dict(summary), fh, indent=2, sort_keys=True)


def main() -> None:
    args = _parse_args()
    seeds = _parse_seeds(args.seeds)

    base_config = dict(DEFAULTS)
    base_config.update(
        {
            "sus_p0": float(args.sus_p0),
            "max_levels": int(args.max_levels),
            "target_violation": float(args.target_violation),
            "line_outage_prob": float(args.line_outage_prob),
            "bus_outage_prob": float(args.bus_outage_prob),
        }
    )

    arm_runs: List[Dict[str, Any]] = []

    for seed in seeds:
        arm_runs.append(
            _run_arm(
                case_name=args.case_name,
                n_samples=int(args.N),
                seed=seed,
                base_config=base_config,
                evaluator_mode="truth_only",
                proxy_mode=None,
                truth_mode="acopf",
            )
        )
        arm_runs.append(
            _run_arm(
                case_name=args.case_name,
                n_samples=int(args.N),
                seed=seed,
                base_config=base_config,
                evaluator_mode="delayed_acceptance",
                proxy_mode="dcopf",
                truth_mode="acopf",
            )
        )

    paired_rows = _pair_rows(arm_runs)
    summary = _build_summary(case_name=args.case_name, seeds=seeds, paired_rows=paired_rows)

    outdir = Path(args.outdir)
    _write_outputs(outdir=outdir, arm_runs=arm_runs, paired_rows=paired_rows, summary=summary)

    print(
        json.dumps(
            {
                "case": args.case_name,
                "outdir": str(outdir),
                "seeds": seeds,
                "records_written": len(arm_runs),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
