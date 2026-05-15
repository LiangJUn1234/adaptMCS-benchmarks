"""Scan case118 outage intensity against delayed-acceptance acceptance behavior."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from ac_ext.config import ACConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan case118 line outage probability and record DA stability metrics"
    )
    parser.add_argument("--case", dest="case_name", default="case118")
    parser.add_argument("--N", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--sus-p0", type=float, default=0.25)
    parser.add_argument("--max-levels", type=int, default=4)
    parser.add_argument("--target-violation", type=float, default=0.0)
    parser.add_argument("--truth-mode", choices=("acopf", "acpf", "dcpf"), default="acopf")
    parser.add_argument(
        "--proxy-mode",
        choices=("dcpf", "fdxb", "dcopf", "ml_surrogate", "ml_failure"),
        default="dcopf",
    )
    parser.add_argument("--bus-outage-prob", type=float, default=0.0)
    parser.add_argument("--line-outage-start", type=float, default=0.01)
    parser.add_argument("--line-outage-stop", type=float, default=0.05)
    parser.add_argument("--line-outage-step", type=float, default=0.01)
    parser.add_argument("--arm-timeout-sec", type=int, default=3600)
    parser.add_argument(
        "--disable-hastings-correction",
        action="store_true",
        help="Run the scan with biased DA instead of corrected DA",
    )
    parser.add_argument(
        "--output",
        default="stability_scan_case118.csv",
        help="Path to stability scan CSV output",
    )
    parser.add_argument("--worker-spec", default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


def _frange(start: float, stop: float, step: float) -> List[float]:
    values: List[float] = []
    x = float(start)
    while x <= float(stop) + 1e-12:
        values.append(round(x, 10))
        x += float(step)
    return values


def _build_config(args: argparse.Namespace, *, line_outage_prob: float) -> Dict[str, Any]:
    cfg = ACConfig(
        N=int(args.N),
        p0=float(args.sus_p0),
        line_outage_prob=float(line_outage_prob),
        bus_outage_prob=float(args.bus_outage_prob),
    ).to_dict()
    cfg.update(
        {
            "N": int(args.N),
            "sus_p0": float(args.sus_p0),
            "max_levels": int(args.max_levels),
            "target_violation": float(args.target_violation),
            "truth_mode": str(args.truth_mode),
            "proxy_mode": str(args.proxy_mode),
            "evaluator_mode": "delayed_acceptance",
            "enable_hastings_correction": not bool(args.disable_hastings_correction),
            "line_outage_prob": float(line_outage_prob),
            "bus_outage_prob": float(args.bus_outage_prob),
            "da_debug_print": False,
            "da_debug_max_logs": 0,
        }
    )
    return cfg


def _summarize_level_acceptance(level_logs: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], float | None]:
    rows: List[Dict[str, Any]] = []
    attempts = 0
    accepted = 0
    for log in level_logs:
        stats = log.get("sampler_stats")
        if not isinstance(stats, Mapping):
            continue
        row = {
            "level": int(log.get("level", -1)),
            "attempts": int(stats.get("attempts", 0)),
            "accepted": int(stats.get("accepted", 0)),
            "acceptance_rate": float(stats.get("acceptance_rate", 0.0)),
        }
        rows.append(row)
        attempts += row["attempts"]
        accepted += row["accepted"]

    if attempts <= 0:
        return rows, None
    return rows, accepted / float(attempts)


def _sum_reverse_proxy_rejects(level_logs: Iterable[Mapping[str, Any]]) -> int:
    total = 0
    for log in level_logs:
        stats = log.get("sampler_stats")
        if isinstance(stats, Mapping):
            total += int(stats.get("reverse_proxy_rejects", 0))
    return total


def _success_row(
    *,
    case_name: str,
    seed: int,
    n_samples: int,
    line_outage_prob: float,
    config: Mapping[str, Any],
    result: Mapping[str, Any],
    controller_stats: Mapping[str, Any],
) -> Dict[str, Any]:
    level_logs = list(result.get("level_logs", []))
    level_acceptance_rows, overall_acceptance_rate = _summarize_level_acceptance(level_logs)
    return {
        "case": case_name,
        "seed": int(seed),
        "N": int(n_samples),
        "line_outage_prob": float(line_outage_prob),
        "enable_hastings_correction": bool(config.get("enable_hastings_correction", True)),
        "status": "ok",
        "error": None,
        "termination_reason": result.get("termination_reason"),
        "n_levels": result.get("n_levels"),
        "pf_hat": result.get("pf_hat"),
        "acceptance_rate": overall_acceptance_rate,
        "level_acceptance_rates_json": json.dumps(level_acceptance_rows, sort_keys=True),
        "reverse_proxy_rejects": _sum_reverse_proxy_rejects(level_logs),
        "truth_calls": int(result.get("n_truth_calls", 0)),
        "proxy_calls": int(result.get("n_proxy_calls", 0)),
        "total_wall_clock_time": float(controller_stats.get("total_wall_clock_time", 0.0)),
        "truth_engine_time": float(controller_stats.get("truth_engine_time", 0.0)),
        "l0_truth_calls": controller_stats.get("l0_truth_calls"),
        "l0_proxy_calls": controller_stats.get("l0_proxy_calls"),
        "l0_guard_passed": controller_stats.get("l0_guard_passed"),
        "l0_fallback_triggered": controller_stats.get("l0_fallback_triggered"),
        "l0_fallback_reason": controller_stats.get("l0_fallback_reason"),
        "l0_rank_inversion_hits": controller_stats.get("l0_rank_inversion_hits"),
        "l0_tail_audit_truth_fail_count": controller_stats.get("l0_tail_audit_truth_fail_count"),
        "l0_tail_audit_hit_fail_count": controller_stats.get("l0_tail_audit_hit_fail_count"),
        "l0_tail_audit_hit_line_count": controller_stats.get("l0_tail_audit_hit_line_count"),
        "l0_tail_audit_hit_volt_count": controller_stats.get("l0_tail_audit_hit_volt_count"),
        "l0_proxy_fail_count": controller_stats.get("l0_proxy_fail_count"),
        "l0_proxy_inf_count": controller_stats.get("l0_proxy_inf_count"),
        "l0_proxy_fail_in_topk_count": controller_stats.get("l0_proxy_fail_in_topk_count"),
        "l0_proxy_inf_in_topk_count": controller_stats.get("l0_proxy_inf_in_topk_count"),
        "l0_proxy_fail_in_audit_count": controller_stats.get("l0_proxy_fail_in_audit_count"),
        "l0_proxy_inf_in_audit_count": controller_stats.get("l0_proxy_inf_in_audit_count"),
    }


def _error_row(
    *,
    case_name: str,
    seed: int,
    n_samples: int,
    line_outage_prob: float,
    config: Mapping[str, Any],
    status: str,
    error: str,
) -> Dict[str, Any]:
    return {
        "case": case_name,
        "seed": int(seed),
        "N": int(n_samples),
        "line_outage_prob": float(line_outage_prob),
        "enable_hastings_correction": bool(config.get("enable_hastings_correction", True)),
        "status": status,
        "error": error,
        "termination_reason": status,
        "n_levels": None,
        "pf_hat": None,
        "acceptance_rate": None,
        "level_acceptance_rates_json": "[]",
        "reverse_proxy_rejects": 0,
        "truth_calls": 0,
        "proxy_calls": 0,
        "total_wall_clock_time": None,
        "truth_engine_time": None,
        "l0_truth_calls": None,
        "l0_proxy_calls": None,
        "l0_guard_passed": None,
        "l0_fallback_triggered": None,
        "l0_fallback_reason": None,
        "l0_rank_inversion_hits": None,
        "l0_tail_audit_truth_fail_count": None,
        "l0_tail_audit_hit_fail_count": None,
        "l0_tail_audit_hit_line_count": None,
        "l0_tail_audit_hit_volt_count": None,
        "l0_proxy_fail_count": None,
        "l0_proxy_inf_count": None,
        "l0_proxy_fail_in_topk_count": None,
        "l0_proxy_inf_in_topk_count": None,
        "l0_proxy_fail_in_audit_count": None,
        "l0_proxy_inf_in_audit_count": None,
    }


def _worker_run(
    *,
    case_name: str,
    seed: int,
    n_samples: int,
    line_outage_prob: float,
    config: Mapping[str, Any],
) -> None:
    from ac_ext.matlab_engine import close_engine
    from ac_ext.sus_controller import SuSController

    try:
        controller = SuSController(case_name, config)
        result = controller.run(n_samples, seed=seed)
        row = _success_row(
            case_name=case_name,
            seed=seed,
            n_samples=n_samples,
            line_outage_prob=line_outage_prob,
            config=config,
            result=result,
            controller_stats=controller.stats,
        )
        return row
    except Exception as exc:
        return _error_row(
            case_name=case_name,
            seed=seed,
            n_samples=n_samples,
            line_outage_prob=line_outage_prob,
            config=config,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        try:
            close_engine()
        except Exception:
            pass


def _run_with_timeout(
    *,
    case_name: str,
    seed: int,
    n_samples: int,
    line_outage_prob: float,
    config: Mapping[str, Any],
    timeout_sec: int,
) -> Dict[str, Any]:
    spec = {
        "case_name": case_name,
        "seed": int(seed),
        "n_samples": int(n_samples),
        "line_outage_prob": float(line_outage_prob),
        "config": dict(config),
    }
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker-spec", json.dumps(spec)]
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return _error_row(
            case_name=case_name,
            seed=seed,
            n_samples=n_samples,
            line_outage_prob=line_outage_prob,
            config=config,
            status="timeout",
            error=f"run exceeded timeout of {timeout_sec} seconds",
        )

    stdout = completed.stdout.strip()
    if stdout:
        try:
            return dict(json.loads(stdout.splitlines()[-1]))
        except json.JSONDecodeError:
            pass

    if completed.returncode != 0:
        return _error_row(
            case_name=case_name,
            seed=seed,
            n_samples=n_samples,
            line_outage_prob=line_outage_prob,
            config=config,
            status="error",
            error=(completed.stderr.strip() or completed.stdout.strip() or "worker failed"),
        )

    return _error_row(
        case_name=case_name,
        seed=seed,
        n_samples=n_samples,
        line_outage_prob=line_outage_prob,
        config=config,
        status="error",
        error="worker exited without returning a payload",
    )


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    fieldnames = [
        "case",
        "seed",
        "N",
        "line_outage_prob",
        "enable_hastings_correction",
        "status",
        "error",
        "termination_reason",
        "n_levels",
        "pf_hat",
        "acceptance_rate",
        "level_acceptance_rates_json",
        "reverse_proxy_rejects",
        "truth_calls",
        "proxy_calls",
        "total_wall_clock_time",
        "truth_engine_time",
        "l0_truth_calls",
        "l0_proxy_calls",
        "l0_guard_passed",
        "l0_fallback_triggered",
        "l0_fallback_reason",
        "l0_rank_inversion_hits",
        "l0_tail_audit_truth_fail_count",
        "l0_tail_audit_hit_fail_count",
        "l0_tail_audit_hit_line_count",
        "l0_tail_audit_hit_volt_count",
        "l0_proxy_fail_count",
        "l0_proxy_inf_count",
        "l0_proxy_fail_in_topk_count",
        "l0_proxy_inf_in_topk_count",
        "l0_proxy_fail_in_audit_count",
        "l0_proxy_inf_in_audit_count",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = _parse_args()

    if args.worker_spec is not None:
        spec = json.loads(args.worker_spec)
        row = _worker_run(
            case_name=str(spec["case_name"]),
            seed=int(spec["seed"]),
            n_samples=int(spec["n_samples"]),
            line_outage_prob=float(spec["line_outage_prob"]),
            config=dict(spec["config"]),
        )
        sys.stdout.write(json.dumps(row, sort_keys=True) + "\n")
        sys.stdout.flush()
        os._exit(0)

    output_path = Path(args.output).resolve()
    rows: List[Dict[str, Any]] = []

    print(
        "Running stability scan case={case} correction={corr}".format(
            case=args.case_name,
            corr=not bool(args.disable_hastings_correction),
        )
    )

    for line_outage_prob in _frange(
        args.line_outage_start,
        args.line_outage_stop,
        args.line_outage_step,
    ):
        cfg = _build_config(args, line_outage_prob=line_outage_prob)
        print(f"  [scan] line_outage_prob={line_outage_prob}")
        row = _run_with_timeout(
            case_name=str(args.case_name),
            seed=int(args.seed),
            n_samples=int(args.N),
            line_outage_prob=float(line_outage_prob),
            config=cfg,
            timeout_sec=int(args.arm_timeout_sec),
        )
        rows.append(row)
        print(
            "    status={status} acceptance={acc} reverse_proxy_rejects={rev} pf_hat={pf_hat}".format(
                status=row["status"],
                acc=row["acceptance_rate"],
                rev=row["reverse_proxy_rejects"],
                pf_hat=row["pf_hat"],
            )
        )

    _write_csv(output_path, rows)
    print()
    print(f"scan_written={output_path}")


if __name__ == "__main__":
    main()
