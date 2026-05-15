"""Minimal delayed-acceptance sandbox for Hastings debug tracing."""

from __future__ import annotations

import argparse
import logging
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from ac_ext.config import ACConfig
from ac_ext.exceptions import MatlabEngineUnavailableError
from ac_ext.matlab_engine import close_engine, get_engine
from ac_ext.problem import case_sanity
from ac_ext.sus_controller import SuSController


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal DA sandbox and compare biased vs corrected Hastings behavior"
    )
    parser.add_argument("--case", dest="case_name", default="case30")
    parser.add_argument("--N", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--sus-p0", type=float, default=0.15)
    parser.add_argument("--max-levels", type=int, default=4)
    parser.add_argument("--target-violation", type=float, default=0.0)
    parser.add_argument("--truth-mode", choices=("acopf", "acpf", "dcpf"), default="acopf")
    parser.add_argument("--proxy-mode", choices=("dcpf", "fdxb", "dcopf"), default="dcopf")
    parser.add_argument("--line-outage-prob", type=float, default=0.03)
    parser.add_argument("--bus-outage-prob", type=float, default=0.0)
    parser.add_argument("--debug-max-logs", type=int, default=12)
    return parser.parse_args()


def _make_base_config(args: argparse.Namespace) -> Dict[str, Any]:
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
            "proxy_mode": str(args.proxy_mode),
            "evaluator_mode": "delayed_acceptance",
            "audit_shadow_prob": 0.0,
            "bus_outage_prob": float(args.bus_outage_prob),
            "line_outage_prob": float(args.line_outage_prob),
        }
    )
    return cfg


def _collect_sampler_rows(level_logs: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for log in level_logs:
        stats = log.get("sampler_stats")
        if not isinstance(stats, Mapping):
            continue
        rows.append(
            {
                "level": int(log.get("level", -1)),
                "threshold": float(log.get("threshold", 0.0)),
                "attempts": int(stats.get("attempts", 0)),
                "accepted": int(stats.get("accepted", 0)),
                "acceptance_rate": float(stats.get("acceptance_rate", 0.0)),
                "stage2_gate_rejects": int(stats.get("stage2_gate_rejects", 0)),
                "reverse_proxy_rejects": int(stats.get("reverse_proxy_rejects", 0)),
                "debug_samples": len(list(stats.get("da_hastings_debug", []))),
            }
        )
    return rows


def _overall_acceptance_rate(rows: Iterable[Mapping[str, Any]]) -> float | None:
    attempts = sum(int(row["attempts"]) for row in rows)
    accepted = sum(int(row["accepted"]) for row in rows)
    if attempts <= 0:
        return None
    return accepted / float(attempts)


def _print_run_header(label: str, config: Mapping[str, Any], sanity: Mapping[str, Any]) -> None:
    print()
    print(f"=== {label} ===")
    print(
        "case={case} N={N} sus_p0={p0} truth={truth} proxy={proxy} "
        "line_outage_prob={lop} max_levels={levels}".format(
            case=config["case_name"],
            N=config["N"],
            p0=config["sus_p0"],
            truth=config["truth_mode"],
            proxy=config["proxy_mode"],
            lop=config["line_outage_prob"],
            levels=config["max_levels"],
        )
    )
    print(
        "sanity: n_bus={n_bus} n_branch={n_branch} n_gen={n_gen} "
        "n_branch_online={n_branch_online} pmax_online_total={pmax}".format(
            n_bus=int(sanity["n_bus"]),
            n_branch=int(sanity["n_branch"]),
            n_gen=int(sanity["n_gen"]),
            n_branch_online=int(sanity["n_branch_online"]),
            pmax=float(sanity["pmax_online_total"]),
        )
    )


def _print_level_table(label: str, rows: Sequence[Mapping[str, Any]]) -> None:
    print()
    print(f"{label} level summary")
    if not rows:
        print("  no sampler rows captured")
        return

    header = (
        f"{'level':>5} {'threshold':>12} {'attempts':>10} {'accepted':>10} "
        f"{'acc_rate':>10} {'stage2_rej':>10} {'rev_gate_rej':>12} {'debug_n':>8}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{int(row['level']):>5} "
            f"{float(row['threshold']):>12.5g} "
            f"{int(row['attempts']):>10} "
            f"{int(row['accepted']):>10} "
            f"{float(row['acceptance_rate']):>10.4f} "
            f"{int(row['stage2_gate_rejects']):>10} "
            f"{int(row['reverse_proxy_rejects']):>12} "
            f"{int(row['debug_samples']):>8}"
        )


def _print_debug_excerpt(result: Mapping[str, Any], max_items: int) -> None:
    print()
    print("Corrected run Hastings debug excerpt")
    shown = 0
    for log in result.get("level_logs", []):
        stats = log.get("sampler_stats")
        if not isinstance(stats, Mapping):
            continue
        for record in stats.get("da_hastings_debug", []):
            if shown >= max_items:
                return
            print(
                "  level={level} attempt={attempt} move={move} "
                "alpha_raw={alpha_raw:.6g} reverse_proxy_pass={reverse_proxy_pass} alpha={alpha:.6g}".format(
                    level=int(log.get("level", -1)),
                    attempt=int(record["attempt"]),
                    move=record["move"],
                    alpha_raw=float(record["alpha_raw"]),
                    reverse_proxy_pass=bool(record["reverse_proxy_pass"]),
                    alpha=float(record["alpha"]),
                )
            )
            shown += 1


def _run_arm(
    *,
    label: str,
    case_name: str,
    n_samples: int,
    seed: int,
    base_cfg: Mapping[str, Any],
    enable_hastings_correction: bool,
    da_debug_print: bool,
    da_debug_max_logs: int,
) -> Dict[str, Any]:
    cfg = dict(base_cfg)
    cfg.update(
        {
            "case_name": case_name,
            "N": int(n_samples),
            "enable_hastings_correction": bool(enable_hastings_correction),
            "da_debug_print": bool(da_debug_print),
            "da_debug_max_logs": int(da_debug_max_logs),
        }
    )

    result: Mapping[str, Any] | None = None
    error: str | None = None
    try:
        result = SuSController(case_name, cfg).run(n_samples, seed=seed)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    return {
        "label": label,
        "config": cfg,
        "result": result,
        "error": error,
        "rows": [] if result is None else _collect_sampler_rows(result.get("level_logs", [])),
    }


def _print_comparison(run_a: Mapping[str, Any], run_b: Mapping[str, Any]) -> None:
    rows_a = list(run_a["rows"])
    rows_b = list(run_b["rows"])
    acc_a = _overall_acceptance_rate(rows_a)
    acc_b = _overall_acceptance_rate(rows_b)

    result_a = run_a["result"]
    result_b = run_b["result"]
    pf_a = None if result_a is None else result_a.get("pf_hat")
    pf_b = None if result_b is None else result_b.get("pf_hat")

    print()
    print("=== Biased vs Corrected Comparison ===")
    print(
        f"{'metric':<32} {'biased':>14} {'corrected':>14} {'delta(c-b)':>14}"
    )
    print("-" * 78)

    def _fmt(value: Any) -> str:
        if value is None:
            return "None"
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    delta_acc = None if acc_a is None or acc_b is None else acc_b - acc_a
    delta_pf = None if pf_a is None or pf_b is None else float(pf_b) - float(pf_a)

    print(
        f"{'overall_acceptance_rate':<32} {_fmt(acc_a):>14} {_fmt(acc_b):>14} {_fmt(delta_acc):>14}"
    )
    print(f"{'pf_hat':<32} {_fmt(pf_a):>14} {_fmt(pf_b):>14} {_fmt(delta_pf):>14}")

    if delta_acc is None:
        print("acceptance trend: unavailable")
    elif delta_acc < 0.0:
        print("acceptance trend: corrected run is lower than biased run")
    elif delta_acc > 0.0:
        print("acceptance trend: corrected run is higher than biased run")
    else:
        print("acceptance trend: unchanged")

    if delta_pf is None:
        print("pf_hat trend: unavailable")
    elif delta_pf < 0.0:
        print("pf_hat trend: corrected run is lower than biased run")
    elif delta_pf > 0.0:
        print("pf_hat trend: corrected run is higher than biased run")
    else:
        print("pf_hat trend: unchanged")


def main() -> None:
    args = _parse_args()

    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")

    base_cfg = _make_base_config(args)

    try:
        get_engine(reuse=True)
        sanity = case_sanity(args.case_name)

        biased = _run_arm(
            label="Run A (Biased DA)",
            case_name=args.case_name,
            n_samples=int(args.N),
            seed=int(args.seed),
            base_cfg=base_cfg,
            enable_hastings_correction=False,
            da_debug_print=False,
            da_debug_max_logs=0,
        )
        if biased["error"] is not None:
            raise RuntimeError(f"biased run failed: {biased['error']}")

        corrected = _run_arm(
            label="Run B (Corrected DA)",
            case_name=args.case_name,
            n_samples=int(args.N),
            seed=int(args.seed),
            base_cfg=base_cfg,
            enable_hastings_correction=True,
            da_debug_print=True,
            da_debug_max_logs=int(args.debug_max_logs),
        )
        if corrected["error"] is not None:
            raise RuntimeError(f"corrected run failed: {corrected['error']}")

        _print_run_header(biased["label"], biased["config"], sanity)
        _print_level_table("Biased", biased["rows"])

        _print_run_header(corrected["label"], corrected["config"], sanity)
        _print_level_table("Corrected", corrected["rows"])
        _print_debug_excerpt(corrected["result"], max_items=int(args.debug_max_logs))

        _print_comparison(biased, corrected)
    except MatlabEngineUnavailableError as exc:
        print(f"MATLAB engine unavailable: {exc}")
    finally:
        close_engine()


if __name__ == "__main__":
    main()
