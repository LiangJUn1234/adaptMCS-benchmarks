"""Collect DCOPF diagnostic features for existing ACOPF-labeled ML training data.

This script does NOT re-run ACOPF. It reads existing damage states and ACOPF
labels, evaluates DCOPF proxy, and writes an augmented CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from ac_ext.config import ACConfig
from ac_ext.problem import eval_proxy


INPUT_DEFAULT = Path(__file__).resolve().parent / "out" / "ml_training_data_case118.csv"
OUTPUT_DEFAULT = Path(__file__).resolve().parent / "out" / "ml_training_data_with_dcopf_case118.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append DCOPF features to existing ACOPF-labeled data.")
    p.add_argument("--case", default="case118")
    p.add_argument("--input", default=str(INPUT_DEFAULT))
    p.add_argument("--output", default=str(OUTPUT_DEFAULT))
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--flush-every", type=int, default=50)
    p.add_argument("--bus-outage-prob", type=float, default=0.0)
    p.add_argument("--resume", action="store_true", default=True)
    return p.parse_args()


def _bool_from_any(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    return s in {"1", "true", "yes", "y"}


def _is_inf_string(x: Any) -> bool:
    s = str(x).strip().lower()
    return s in {"inf", "+inf", "infinity", "+infinity"}


def _float_or_inf(x: Any) -> float:
    if _is_inf_string(x):
        return float("inf")
    return float(x)


def _json_list(row: Dict[str, str], key: str) -> List[Any]:
    return json.loads(row[key])


def _build_state(row: Dict[str, str]) -> Dict[str, Any]:
    line_out = _json_list(row, "line_out_json")
    bus_out = _json_list(row, "bus_out_json")
    gen_derate_state = _json_list(row, "gen_derate_state_json")
    gen_scale = _json_list(row, "gen_scale_json")

    return {
        "line_out": line_out,
        "bus_out": bus_out,
        "gen_derate_state": gen_derate_state,
        "gen_scale": gen_scale,
        "meta": {
            "n_branch": len(line_out),
            "n_bus": len(bus_out),
            "n_gen": len(gen_scale),
        },
    }


def _load_done_sample_ids(output_path: Path) -> set[str]:
    if not output_path.exists() or output_path.stat().st_size == 0:
        return set()
    try:
        with output_path.open(newline="", encoding="utf-8") as fh:
            return {r["sample_id"] for r in csv.DictReader(fh) if "sample_id" in r}
    except Exception:
        return set()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with input_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    if args.limit is not None:
        rows = rows[: args.limit]

    done_ids = _load_done_sample_ids(output_path) if args.resume else set()

    fieldnames = [
        "sample_id",
        "seed",
        "line_outage_prob",
        "line_out_json",
        "bus_out_json",
        "gen_derate_state_json",
        "gen_scale_json",
        "acopf_s_line",
        "acopf_s_volt",
        "acopf_s_any",
        "acopf_success",
        "acopf_fail_label",
        "dcopf_s_line",
        "dcopf_s_volt",
        "dcopf_s_any",
        "dcopf_success",
        "dcopf_fail_indicator",
    ]

    write_header = not output_path.exists() or output_path.stat().st_size == 0
    mode = "a" if args.resume else "w"

    t0 = time.time()
    n_written = 0
    n_skipped = 0
    n_total = len(rows)

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print(f"Rows requested: {n_total}")
    print(f"Already done sample_ids: {len(done_ids)}")
    print(f"case={args.case}")
    print("Starting DCOPF feature collection...")

    with output_path.open(mode, newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
            out_fh.flush()

        for i, row in enumerate(rows, start=1):
            sid = str(row["sample_id"])
            if sid in done_ids:
                n_skipped += 1
                continue

            lop = float(row["line_outage_prob"])
            cfg = ACConfig(
                line_outage_prob=lop,
                bus_outage_prob=float(args.bus_outage_prob),
            ).to_dict()
            cfg["ac_fail_as_violation"] = True

            state = _build_state(row)

            ac_s_line = row.get("s_line", row.get("acopf_s_line", "nan"))
            ac_s_volt = row.get("s_volt", row.get("acopf_s_volt", "nan"))
            ac_s_any = row.get("s_any", row.get("acopf_s_any", "nan"))
            ac_success = row.get("success", row.get("acopf_success", "False"))

            ac_fail = (not _bool_from_any(ac_success)) or _is_inf_string(ac_s_any)

            dc = eval_proxy(args.case, state, cfg, proxy_mode="dcopf")
            dc_success = bool(dc.get("success", False))
            dc_s_line = float(dc.get("s_line", float("inf")))
            dc_s_volt = float(dc.get("s_volt", float("inf")))
            dc_s_any = float(dc.get("s_any", float("inf")))
            dc_fail = (not dc_success) or math.isinf(dc_s_any)

            writer.writerow({
                "sample_id": sid,
                "seed": row["seed"],
                "line_outage_prob": row["line_outage_prob"],
                "line_out_json": row["line_out_json"],
                "bus_out_json": row["bus_out_json"],
                "gen_derate_state_json": row["gen_derate_state_json"],
                "gen_scale_json": row["gen_scale_json"],
                "acopf_s_line": ac_s_line,
                "acopf_s_volt": ac_s_volt,
                "acopf_s_any": ac_s_any,
                "acopf_success": ac_success,
                "acopf_fail_label": int(ac_fail),
                "dcopf_s_line": dc_s_line,
                "dcopf_s_volt": dc_s_volt,
                "dcopf_s_any": dc_s_any,
                "dcopf_success": dc_success,
                "dcopf_fail_indicator": int(dc_fail),
            })

            n_written += 1

            if n_written % args.flush_every == 0:
                out_fh.flush()
                elapsed = time.time() - t0
                rate = n_written / elapsed if elapsed > 0 else 0.0
                print(
                    f"written={n_written} skipped={n_skipped} "
                    f"processed={i}/{n_total} rate={rate:.2f}/s elapsed={elapsed:.1f}s",
                    flush=True,
                )

        out_fh.flush()

    elapsed = time.time() - t0
    rate = n_written / elapsed if elapsed > 0 else 0.0
    print(f"Finished. written={n_written} skipped={n_skipped} elapsed={elapsed:.1f}s rate={rate:.2f}/s")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
