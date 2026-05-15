"""CLI for crude AC-extension Monte Carlo baseline."""

from __future__ import annotations

import argparse
import json

from ac_ext.baseline_mcs import run_mcs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run crude MCS baseline on one MATPOWER case")
    parser.add_argument("--case", dest="case_name", required=True)
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--truth", choices=("acopf", "acpf", "dcpf"), default="acopf")
    parser.add_argument("--line-outage-prob", type=float, default=None)
    parser.add_argument("--bus-outage-prob", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    override: dict = {}
    if args.line_outage_prob is not None:
        override["line_outage_prob"] = args.line_outage_prob
    if args.bus_outage_prob is not None:
        override["bus_outage_prob"] = args.bus_outage_prob

    try:
        summary = run_mcs(
            case_name=args.case_name,
            N=args.N,
            seed=args.seed,
            truth=args.truth,
            config_override=override or None,
        )
    except Exception as exc:
        summary = {
            "case": args.case_name,
            "truth": args.truth,
            "N": args.N,
            "seed": args.seed,
            "pf_hat": None,
            "var_hat": None,
            "cov": None,
            "truth_calls": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
