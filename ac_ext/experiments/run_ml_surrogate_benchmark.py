"""Four-arm benchmark: truth_only vs corrected_da (fdxb/dcopf/ml_surrogate)."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from ac_ext.config import ACConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Four-arm ML surrogate benchmark")
    parser.add_argument("--case", default="case118")
    parser.add_argument("--N", type=int, default=1000)
    parser.add_argument("--seeds", nargs="+", default=["400", "500", "600"])
    parser.add_argument("--sus-p0", type=float, default=0.15)
    parser.add_argument("--max-levels", type=int, default=4)
    parser.add_argument("--target-violation", type=float, default=0.0)
    parser.add_argument("--truth-mode", default="acopf")
    parser.add_argument("--line-outage-prob", type=float, default=0.008)
    parser.add_argument("--bus-outage-prob", type=float, default=0.0)
    parser.add_argument("--level0-K", type=int, default=200)
    parser.add_argument("--level0-tail-audit", type=int, default=50)
    parser.add_argument(
        "--level0-guard-mode",
        choices=["legacy_truth_score", "failure_label"],
        default="legacy_truth_score",
    )
    parser.add_argument("--arms", nargs="+", default=None)
    parser.add_argument("--arm-timeout-sec", type=int, default=3600)
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "out" / "ml_surrogate_benchmark_case118.csv"),
    )
    return parser.parse_args()


def _split_csv_tokens(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_tokens = [values]
    else:
        raw_tokens = list(values)

    tokens: List[str] = []
    for raw in raw_tokens:
        for part in str(raw).split(","):
            item = part.strip()
            if item:
                tokens.append(item)
    return tokens


def _resolve_seed_values(raw_values: Any) -> List[int]:
    tokens = _split_csv_tokens(raw_values)
    try:
        return [int(token) for token in tokens]
    except ValueError as exc:
        raise ValueError(
            f"Invalid --seeds value {raw_values!r}; expected integers such as "
            "--seeds 901 902 903 or --seeds 901,902,903"
        ) from exc


def _resolve_arm_names(raw_values: Any) -> List[str] | None:
    tokens = _split_csv_tokens(raw_values)
    return tokens or None


ARM_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "arm_name": "truth_only",
        "evaluator_mode": "truth_only",
        "enable_hastings_correction": True,
        "enable_level0_prescreen": False,
        "proxy_mode": "fdxb",
        "level0_prescreen_proxy_mode": "fdxb",
    },
    {
        "arm_name": "corrected_da_fdxb",
        "evaluator_mode": "delayed_acceptance",
        "enable_hastings_correction": True,
        "enable_level0_prescreen": True,
        "proxy_mode": "fdxb",
        "level0_prescreen_proxy_mode": "fdxb",
    },
    {
        "arm_name": "corrected_da_dcopf",
        "evaluator_mode": "delayed_acceptance",
        "enable_hastings_correction": True,
        "enable_level0_prescreen": True,
        "proxy_mode": "dcopf",
        "level0_prescreen_proxy_mode": "dcopf",
    },
    {
        "arm_name": "corrected_da_ml",
        "evaluator_mode": "delayed_acceptance",
        "enable_hastings_correction": True,
        "enable_level0_prescreen": True,
        "proxy_mode": "ml_surrogate",
        "level0_prescreen_proxy_mode": "ml_surrogate",
    },
    {
        "arm_name": "corrected_da_hybrid_ml_failure_l0_dcopf_da",
        "evaluator_mode": "delayed_acceptance",
        "enable_hastings_correction": True,
        "enable_level0_prescreen": True,
        "proxy_mode": "dcopf",
        "level0_prescreen_proxy_mode": "ml_failure",
    },
]


FIELDNAMES = [
    "arm_name",
    "seed",
    "N",
    "line_outage_prob",
    "evaluator_mode",
    "truth_mode",
    "proxy_mode",
    "l0_proxy_mode",
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
    "l0_prescreen_enabled",
    "l0_truth_calls",
    "l0_proxy_calls",
    "l0_guard_active",
    "l0_guard_mode",
    "l0_guard_passed",
    "l0_fallback_triggered",
    "l0_fallback_reason",
    "l0_tail_audit_count",
    "l0_tail_audit_failure_hits",
    "l0_rank_inversion_hits",
    "l0_failure_recall_inside_final_k",
    "l0_failure_recall_inside_final_k_observed",
    "l0_failure_label_rank_inversion_hits",
    "l0_failure_label_guard_passed",
    "l0_failure_label_fallback_reason",
    "l0_prescreen_K_initial",
    "l0_prescreen_K_final",
]


def _build_config(args: argparse.Namespace, arm: Dict[str, Any]) -> Dict[str, Any]:
    cfg = ACConfig(
        N=int(args.N),
        p0=float(args.sus_p0),
        line_outage_prob=float(args.line_outage_prob),
        bus_outage_prob=float(args.bus_outage_prob),
    ).to_dict()
    cfg.update(
        {
            "N": int(args.N),
            "sus_p0": float(args.sus_p0),
            "max_levels": int(args.max_levels),
            "target_violation": float(args.target_violation),
            "truth_mode": str(args.truth_mode),
            "proxy_mode": str(arm.get("proxy_mode", arm["level0_prescreen_proxy_mode"])),
            "evaluator_mode": str(arm["evaluator_mode"]),
            "enable_hastings_correction": bool(arm["enable_hastings_correction"]),
            "enable_level0_prescreen": bool(arm["enable_level0_prescreen"]),
            "level0_prescreen_proxy_mode": str(arm["level0_prescreen_proxy_mode"]),
            "level0_guard_mode": str(args.level0_guard_mode),
            "level0_prescreen_K": int(args.level0_K),
            "level0_prescreen_tail_audit": int(args.level0_tail_audit),
            "line_outage_prob": float(args.line_outage_prob),
            "bus_outage_prob": float(args.bus_outage_prob),
            "da_debug_print": False,
            "da_debug_max_logs": 0,
        }
    )
    return cfg


def _summarize_level_acceptance(level_logs):
    rows = []
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


def _sum_reverse_proxy_rejects(level_logs):
    total = 0
    for log in level_logs:
        stats = log.get("sampler_stats")
        if isinstance(stats, Mapping):
            total += int(stats.get("reverse_proxy_rejects", 0))
    return total


def _success_row(*, arm_name, seed, n_samples, line_outage_prob, config, result, controller_stats):
    level_logs = list(result.get("level_logs", []))
    level_rows, overall_acc = _summarize_level_acceptance(level_logs)
    l0_enabled = bool(controller_stats.get("l0_prescreen_enabled"))
    l0_guard_mode = controller_stats.get("l0_guard_mode")
    l0_guard_active = controller_stats.get("l0_guard_active")
    if not l0_enabled:
        l0_guard_mode = "not_applicable"
        l0_guard_active = False

    l0_failure_recall = controller_stats.get("l0_failure_recall_inside_final_k")
    if l0_enabled and l0_failure_recall is None:
        l0_failure_recall = "not_available"
    if not l0_enabled:
        l0_failure_recall = "not_applicable"

    l0_failure_recall_observed = controller_stats.get("l0_failure_recall_inside_final_k_observed")
    if l0_enabled and l0_failure_recall_observed is None:
        l0_failure_recall_observed = "not_available"
    if not l0_enabled:
        l0_failure_recall_observed = "not_applicable"

    l0_failure_label_rank_hits = controller_stats.get("l0_failure_label_rank_inversion_hits")
    l0_failure_label_guard_passed = controller_stats.get("l0_failure_label_guard_passed")
    l0_failure_label_fallback_reason = controller_stats.get("l0_failure_label_fallback_reason")
    if not l0_enabled:
        l0_failure_label_rank_hits = "not_applicable"
        l0_failure_label_guard_passed = "not_applicable"
        l0_failure_label_fallback_reason = "not_applicable"

    return {
        "arm_name": arm_name,
        "seed": int(seed),
        "N": int(n_samples),
        "line_outage_prob": float(line_outage_prob),
        "evaluator_mode": str(config.get("evaluator_mode")),
        "truth_mode": str(config.get("truth_mode")),
        "proxy_mode": str(config.get("proxy_mode")),
        "l0_proxy_mode": str(config.get("level0_prescreen_proxy_mode")),
        "enable_hastings_correction": bool(config.get("enable_hastings_correction")),
        "status": "ok",
        "error": None,
        "termination_reason": result.get("termination_reason"),
        "n_levels": result.get("n_levels"),
        "pf_hat": result.get("pf_hat"),
        "acceptance_rate": overall_acc,
        "level_acceptance_rates_json": json.dumps(level_rows, sort_keys=True),
        "reverse_proxy_rejects": _sum_reverse_proxy_rejects(level_logs),
        "truth_calls": int(result.get("n_truth_calls", 0)),
        "proxy_calls": int(result.get("n_proxy_calls", 0)),
        "total_wall_clock_time": float(controller_stats.get("total_wall_clock_time", 0.0)),
        "truth_engine_time": float(controller_stats.get("truth_engine_time", 0.0)),
        "l0_prescreen_enabled": controller_stats.get("l0_prescreen_enabled"),
        "l0_truth_calls": controller_stats.get("l0_truth_calls"),
        "l0_proxy_calls": controller_stats.get("l0_proxy_calls"),
        "l0_guard_active": l0_guard_active,
        "l0_guard_mode": l0_guard_mode,
        "l0_guard_passed": controller_stats.get("l0_guard_passed"),
        "l0_fallback_triggered": controller_stats.get("l0_fallback_triggered"),
        "l0_fallback_reason": controller_stats.get("l0_fallback_reason"),
        "l0_tail_audit_count": controller_stats.get("l0_tail_audit_count"),
        "l0_tail_audit_failure_hits": controller_stats.get("l0_tail_audit_failure_hits"),
        "l0_rank_inversion_hits": controller_stats.get("l0_rank_inversion_hits"),
        "l0_failure_recall_inside_final_k": l0_failure_recall,
        "l0_failure_recall_inside_final_k_observed": l0_failure_recall_observed,
        "l0_failure_label_rank_inversion_hits": l0_failure_label_rank_hits,
        "l0_failure_label_guard_passed": l0_failure_label_guard_passed,
        "l0_failure_label_fallback_reason": l0_failure_label_fallback_reason,
        "l0_prescreen_K_initial": controller_stats.get("l0_prescreen_K_initial"),
        "l0_prescreen_K_final": controller_stats.get("l0_prescreen_K_final"),
    }


def _error_row(*, arm_name, seed, n_samples, line_outage_prob, config, status, error):
    return {
        "arm_name": arm_name,
        "seed": int(seed),
        "N": int(n_samples),
        "line_outage_prob": float(line_outage_prob),
        "evaluator_mode": str(config.get("evaluator_mode")),
        "truth_mode": str(config.get("truth_mode")),
        "proxy_mode": str(config.get("proxy_mode")),
        "l0_proxy_mode": str(config.get("level0_prescreen_proxy_mode")),
        "enable_hastings_correction": bool(config.get("enable_hastings_correction")),
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
        "l0_prescreen_enabled": None,
        "l0_truth_calls": None,
        "l0_proxy_calls": None,
        "l0_guard_active": False,
        "l0_guard_mode": "not_applicable",
        "l0_guard_passed": None,
        "l0_fallback_triggered": None,
        "l0_fallback_reason": "not_applicable",
        "l0_tail_audit_count": None,
        "l0_tail_audit_failure_hits": "not_applicable",
        "l0_rank_inversion_hits": None,
        "l0_failure_recall_inside_final_k": "not_applicable",
        "l0_failure_recall_inside_final_k_observed": "not_applicable",
        "l0_failure_label_rank_inversion_hits": "not_applicable",
        "l0_failure_label_guard_passed": "not_applicable",
        "l0_failure_label_fallback_reason": "not_applicable",
        "l0_prescreen_K_initial": None,
        "l0_prescreen_K_final": None,
    }


def _display_pf_hat(value: Any) -> str:
    """Render pf_hat without treating 0.0 as missing."""
    return "N/A" if value is None else str(value)


def _worker_run(*, case_name, arm_name, seed, n_samples, line_outage_prob, config):
    from ac_ext.matlab_engine import close_engine
    from ac_ext.sus_controller import SuSController

    try:
        controller = SuSController(case_name, config)
        result = controller.run(n_samples, seed=seed)
        return _success_row(
            arm_name=arm_name,
            seed=seed,
            n_samples=n_samples,
            line_outage_prob=line_outage_prob,
            config=config,
            result=result,
            controller_stats=controller.stats,
        )
    except Exception as exc:
        return _error_row(
            arm_name=arm_name,
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


def _run_with_timeout(*, case_name, arm_name, seed, n_samples, line_outage_prob, config, timeout_sec):
    spec = {
        "case_name": case_name,
        "arm_name": arm_name,
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
            arm_name=arm_name,
            seed=seed,
            n_samples=n_samples,
            line_outage_prob=line_outage_prob,
            config=config,
            status="timeout",
            error=f"exceeded {timeout_sec}s",
        )

    stdout = completed.stdout.strip()
    if stdout:
        try:
            return dict(json.loads(stdout.splitlines()[-1]))
        except json.JSONDecodeError:
            pass

    return _error_row(
        arm_name=arm_name,
        seed=seed,
        n_samples=n_samples,
        line_outage_prob=line_outage_prob,
        config=config,
        status="error",
        error=(completed.stderr.strip() or completed.stdout.strip() or "worker failed"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker-spec", default=None)
    worker_args, _ = parser.parse_known_args()

    if worker_args.worker_spec is not None:
        spec = json.loads(worker_args.worker_spec)
        row = _worker_run(
            case_name=str(spec["case_name"]),
            arm_name=str(spec["arm_name"]),
            seed=int(spec["seed"]),
            n_samples=int(spec["n_samples"]),
            line_outage_prob=float(spec["line_outage_prob"]),
            config=dict(spec["config"]),
        )
        sys.stdout.write(json.dumps(row, sort_keys=True) + "\n")
        sys.stdout.flush()
        os._exit(0)

    args = _parse_args()
    args.seeds = _resolve_seed_values(args.seeds)
    args.arms = _resolve_arm_names(args.arms)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected_arms = list(ARM_DEFINITIONS)
    if args.arms:
        requested = set(args.arms)
        selected_arms = [arm for arm in ARM_DEFINITIONS if arm["arm_name"] in requested]
        if not selected_arms:
            raise ValueError(f"No matching arms for --arms={args.arms}")
        matched = {arm["arm_name"] for arm in selected_arms}
        missing = sorted(requested - matched)
        if missing:
            valid = ", ".join(arm["arm_name"] for arm in ARM_DEFINITIONS)
            raise ValueError(
                f"Unknown arm(s) in --arms: {missing}. Valid arm names: {valid}"
            )

    print(f"ML Surrogate Benchmark: {args.case}")
    print(f"  N={args.N} seeds={args.seeds} line_outage_prob={args.line_outage_prob}")
    print(f"  level0_guard_mode={args.level0_guard_mode}")
    print(f"  arms: {[a['arm_name'] for a in selected_arms]}")
    print(f"  output: {output_path}")

    rows: List[Dict[str, Any]] = []
    for arm in selected_arms:
        for seed in args.seeds:
            cfg = _build_config(args, arm)
            arm_name = arm["arm_name"]
            print(f"\n  [{arm_name}] seed={seed} ...", flush=True)
            t0 = time.time()
            row = _run_with_timeout(
                case_name=args.case,
                arm_name=arm_name,
                seed=seed,
                n_samples=args.N,
                line_outage_prob=args.line_outage_prob,
                config=cfg,
                timeout_sec=args.arm_timeout_sec,
            )
            elapsed = time.time() - t0
            rows.append(row)
            print(
                f"    status={row['status']} pf_hat={row['pf_hat']} "
                f"truth_calls={row['truth_calls']} proxy_calls={row['proxy_calls']} "
                f"l0_guard={row.get('l0_guard_passed')} ({elapsed:.1f}s)"
            )

    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    json_path = output_path.with_suffix(".json")
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, default=str)

    print(f"\n  CSV: {output_path}")
    print(f"  JSON: {json_path}")

    print("\n=== Summary ===")
    print(f"{'arm':<25} {'seed':>4} {'pf_hat':>8} {'truth':>6} {'proxy':>6} {'l0_guard':>8} {'l0_truth':>8}")
    for row in rows:
        print(
            f"{row['arm_name']:<25} {row['seed']:>4} "
            f"{_display_pf_hat(row['pf_hat']):>8} "
            f"{row['truth_calls']:>6} {row['proxy_calls']:>6} "
            f"{str(row.get('l0_guard_passed', 'N/A')):>8} "
            f"{str(row.get('l0_truth_calls', 'N/A')):>8}"
        )


if __name__ == "__main__":
    main()
