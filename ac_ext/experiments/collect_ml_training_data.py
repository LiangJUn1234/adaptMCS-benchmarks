"""Collect (damage_state -> ACOPF truth scores) training data for ML surrogate."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from ac_ext.config import ACConfig
from ac_ext.matlab_engine import get_engine
from ac_ext.problem import eval_truth, sample_X


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect ML training data: damage states -> ACOPF truth scores"
    )
    parser.add_argument("--case", default="case118")
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 42, 100, 200, 300])
    parser.add_argument("--n-per-seed", type=int, default=1000)
    parser.add_argument(
        "--line-outage-probs",
        nargs="+",
        type=float,
        default=[0.005, 0.008, 0.011, 0.014, 0.017, 0.02],
    )
    parser.add_argument("--truth-mode", default="acopf")
    parser.add_argument("--bus-outage-prob", type=float, default=0.0)
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "out" / "ml_training_data_case118.csv"),
    )
    parser.add_argument("--flush-every", type=int, default=100)
    parser.add_argument("--progress-every", type=int, default=25)
    return parser.parse_args()


FIELDNAMES = [
    "sample_id",
    "seed",
    "line_outage_prob",
    "line_out_json",
    "bus_out_json",
    "gen_derate_state_json",
    "gen_scale_json",
    "s_line",
    "s_volt",
    "s_any",
    "success",
]


def main() -> None:
    args = _parse_args()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(args.seeds) * len(args.line_outage_probs) * args.n_per_seed
    print(f"Collecting {total} samples for {args.case}")
    print(f"seeds={args.seeds}")
    print(f"line_outage_probs={args.line_outage_probs}")
    print(f"n_per_seed={args.n_per_seed}")
    print(f"output={output_path}")
    print("warming up MATLAB engine ...", flush=True)
    warm_start = time.time()
    get_engine(reuse=True)
    print(f"MATLAB engine ready in {time.time() - warm_start:.1f}s")

    sample_id = 0
    t0 = time.time()

    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        fh.flush()

        for seed in args.seeds:
            for lop in args.line_outage_probs:
                config = ACConfig(
                    line_outage_prob=float(lop),
                    bus_outage_prob=float(args.bus_outage_prob),
                ).to_dict()

                print(f"  seed={seed} line_outage_prob={lop} ... ", end="", flush=True)
                states = sample_X(args.case, config, n=args.n_per_seed, seed=seed)

                for batch_idx, state in enumerate(states, start=1):
                    result = eval_truth(
                        args.case,
                        state,
                        config,
                        truth_mode=args.truth_mode,
                    )
                    writer.writerow(
                        {
                            "sample_id": sample_id,
                            "seed": seed,
                            "line_outage_prob": lop,
                            "line_out_json": json.dumps(state["line_out"]),
                            "bus_out_json": json.dumps(state["bus_out"]),
                            "gen_derate_state_json": json.dumps(state["gen_derate_state"]),
                            "gen_scale_json": json.dumps(state["gen_scale"]),
                            "s_line": float(result["s_line"]),
                            "s_volt": float(result["s_volt"]),
                            "s_any": float(result["s_any"]),
                            "success": bool(result["success"]),
                        }
                    )
                    sample_id += 1

                    if sample_id % args.flush_every == 0:
                        fh.flush()
                    if batch_idx % args.progress_every == 0:
                        elapsed = time.time() - t0
                        rate = sample_id / elapsed if elapsed > 0 else 0
                        print(
                            f"progress {sample_id}/{total} "
                            f"(batch {batch_idx}/{args.n_per_seed}, {rate:.2f} samples/s)",
                            flush=True,
                        )

                elapsed = time.time() - t0
                rate = sample_id / elapsed if elapsed > 0 else 0
                print(f"done ({sample_id}/{total}, {rate:.1f} samples/s)")

    elapsed = time.time() - t0
    print(f"\nFinished: {sample_id} samples in {elapsed:.1f}s -> {output_path}")


if __name__ == "__main__":
    main()
