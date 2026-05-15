"""Collect branch-level DCOPF flow features for existing ACOPF-labeled data.

This script does not re-run ACOPF. It replays existing damage states through
the current DCOPF proxy with debug payloads enabled, then stores branch-level
flow matrices in an NPZ artifact for fully offline pseudo-limit experiments.
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

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from ac_ext.config import ACConfig
from ac_ext.problem import eval_proxy


INPUT_DEFAULT = Path(__file__).resolve().parent / "out" / "ml_training_data_case118.csv"
OUTPUT_DEFAULT = Path(__file__).resolve().parent / "out" / "dcopf_flow_features_case118.npz"

PF_COL = 13
PT_COL = 15
STATUS_COL = 10
RATE_A_COL = 5
FBUS_COL = 0
TBUS_COL = 1
BUS_ID_COL = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect branch-level DCOPF flow features into NPZ.")
    parser.add_argument("--case", default="case118")
    parser.add_argument("--input", default=str(INPUT_DEFAULT))
    parser.add_argument("--output", default=str(OUTPUT_DEFAULT))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--flush-every", type=int, default=50)
    parser.add_argument("--checkpoint-every", type=int, default=1000)
    parser.add_argument("--bus-outage-prob", type=float, default=0.0)
    parser.add_argument("--resume", action="store_true", default=False)
    return parser.parse_args()


def _json_list(row: Dict[str, str], key: str) -> List[Any]:
    return json.loads(row[key])


def _bool_from_any(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    return str(x).strip().lower() in {"1", "true", "yes", "y"}


def _is_inf_string(x: Any) -> bool:
    return str(x).strip().lower() in {"inf", "+inf", "infinity", "+infinity"}


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


def _build_zero_state(template_row: Dict[str, str]) -> Dict[str, Any]:
    line_out = _json_list(template_row, "line_out_json")
    bus_out = _json_list(template_row, "bus_out_json")
    gen_scale = _json_list(template_row, "gen_scale_json")
    return {
        "line_out": [0 for _ in line_out],
        "bus_out": [0 for _ in bus_out],
        "gen_derate_state": [0 for _ in gen_scale],
        "gen_scale": [1.0 for _ in gen_scale],
        "meta": {
            "n_branch": len(line_out),
            "n_bus": len(bus_out),
            "n_gen": len(gen_scale),
        },
    }


def _extract_branch_array(payload: Dict[str, Any]) -> np.ndarray | None:
    branch = payload.get("branch")
    if branch is None:
        return None
    try:
        arr = np.asarray(branch, dtype=np.float64)
    except Exception:
        return None
    if arr.ndim != 2 or arr.shape[1] <= PT_COL:
        return None
    return arr


def _extract_bus_array(payload: Dict[str, Any]) -> np.ndarray | None:
    bus = payload.get("bus")
    if bus is None:
        return None
    try:
        arr = np.asarray(bus, dtype=np.float64)
    except Exception:
        return None
    if arr.ndim != 2 or arr.shape[1] <= BUS_ID_COL:
        return None
    return arr


def _reconstruct_branch_status(
    *,
    base_status: np.ndarray,
    base_fbus: np.ndarray,
    base_tbus: np.ndarray,
    base_bus_ids: np.ndarray,
    state: Dict[str, Any],
) -> np.ndarray:
    status = base_status.astype(np.int8, copy=True)
    line_out = np.asarray(state["line_out"], dtype=np.int8)
    bus_out = np.asarray(state["bus_out"], dtype=np.int8)
    status[line_out > 0] = 0
    if np.any(bus_out > 0):
        outaged_bus_nums = set(base_bus_ids[bus_out > 0].astype(int).tolist())
        if outaged_bus_nums:
            incident = np.isin(base_fbus.astype(int), list(outaged_bus_nums)) | np.isin(
                base_tbus.astype(int), list(outaged_bus_nums)
            )
            status[incident] = 0
    return status


def _save_checkpoint(checkpoint_path: Path, arrays: Dict[str, np.ndarray]) -> None:
    np.savez_compressed(checkpoint_path, **arrays)


def _load_checkpoint(checkpoint_path: Path) -> Dict[str, np.ndarray] | None:
    if not checkpoint_path.exists():
        return None
    with np.load(checkpoint_path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def _base_config(line_outage_prob: float, bus_outage_prob: float) -> Dict[str, Any]:
    cfg = ACConfig(line_outage_prob=float(line_outage_prob), bus_outage_prob=float(bus_outage_prob)).to_dict()
    cfg["ac_fail_as_violation"] = True
    return cfg


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    checkpoint_path = output_path.with_suffix(".checkpoint.npz")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with input_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        raise ValueError("No rows available for collection.")

    template_state = _build_zero_state(rows[0])
    n_rows = len(rows)
    n_branch = len(template_state["line_out"])

    base_payload = eval_proxy(
        args.case,
        template_state,
        _base_config(float(rows[0]["line_outage_prob"]), float(args.bus_outage_prob)),
        proxy_mode="dcopf",
        debug=True,
    )
    base_branch = _extract_branch_array(base_payload)
    base_bus = _extract_bus_array(base_payload)
    if base_branch is None or base_bus is None:
        raise RuntimeError("Base-case DCOPF debug payload did not return bus/branch arrays.")

    rate_a = base_branch[:, RATE_A_COL].astype(np.float32)
    basecase_pf = base_branch[:, PF_COL].astype(np.float32)
    basecase_pt = base_branch[:, PT_COL].astype(np.float32)
    base_status = base_branch[:, STATUS_COL].astype(np.int8)
    base_fbus = base_branch[:, FBUS_COL].astype(np.int32)
    base_tbus = base_branch[:, TBUS_COL].astype(np.int32)
    base_bus_ids = base_bus[:, BUS_ID_COL].astype(np.int32)

    arrays: Dict[str, np.ndarray]
    if args.resume:
        arrays = _load_checkpoint(checkpoint_path) or {}
    else:
        arrays = {}

    if arrays:
        if arrays["completed"].shape[0] != n_rows:
            raise RuntimeError("Checkpoint row count does not match requested input rows.")
    else:
        arrays = {
            "sample_id": np.full(n_rows, -1, dtype=np.int64),
            "seed": np.full(n_rows, -1, dtype=np.int64),
            "line_outage_prob": np.full(n_rows, np.nan, dtype=np.float32),
            "acopf_fail_label": np.full(n_rows, 0, dtype=np.uint8),
            "dcopf_success": np.full(n_rows, 0, dtype=np.uint8),
            "flow_valid": np.full(n_rows, 0, dtype=np.uint8),
            "PF": np.full((n_rows, n_branch), np.nan, dtype=np.float32),
            "PT": np.full((n_rows, n_branch), np.nan, dtype=np.float32),
            "branch_status": np.full((n_rows, n_branch), -1, dtype=np.int8),
            "RATE_A": rate_a,
            "basecase_PF": basecase_pf,
            "basecase_PT": basecase_pt,
            "completed": np.full(n_rows, 0, dtype=np.uint8),
        }

    t0 = time.time()
    n_done_before = int(np.sum(arrays["completed"]))
    n_written = 0

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"Rows requested: {n_rows}")
    print(f"Already completed: {n_done_before}")
    print(f"case={args.case}")
    print("Starting DCOPF flow feature collection...")

    for idx, row in enumerate(rows):
        if bool(arrays["completed"][idx]):
            continue

        state = _build_state(row)
        lop = float(row["line_outage_prob"])
        cfg = _base_config(lop, float(args.bus_outage_prob))
        ac_success = row.get("success", row.get("acopf_success", "False"))
        ac_s_any = row.get("s_any", row.get("acopf_s_any", "nan"))
        ac_fail = (not _bool_from_any(ac_success)) or _is_inf_string(ac_s_any)

        payload = eval_proxy(args.case, state, cfg, proxy_mode="dcopf", debug=True)
        success = bool(payload.get("success", False))
        branch = _extract_branch_array(payload)
        flow_valid = branch is not None

        arrays["sample_id"][idx] = int(row["sample_id"])
        arrays["seed"][idx] = int(row["seed"])
        arrays["line_outage_prob"][idx] = np.float32(lop)
        arrays["acopf_fail_label"][idx] = np.uint8(int(ac_fail))
        arrays["dcopf_success"][idx] = np.uint8(int(success))
        arrays["flow_valid"][idx] = np.uint8(int(flow_valid))

        if branch is not None:
            arrays["PF"][idx, :] = branch[:, PF_COL].astype(np.float32)
            arrays["PT"][idx, :] = branch[:, PT_COL].astype(np.float32)
            arrays["branch_status"][idx, :] = branch[:, STATUS_COL].astype(np.int8)
        else:
            arrays["branch_status"][idx, :] = _reconstruct_branch_status(
                base_status=base_status,
                base_fbus=base_fbus,
                base_tbus=base_tbus,
                base_bus_ids=base_bus_ids,
                state=state,
            )

        arrays["completed"][idx] = np.uint8(1)
        n_written += 1

        if n_written % args.flush_every == 0:
            elapsed = time.time() - t0
            rate = n_written / elapsed if elapsed > 0 else 0.0
            print(
                f"written={n_written} completed_total={int(np.sum(arrays['completed']))}/{n_rows} "
                f"rate={rate:.2f}/s elapsed={elapsed:.1f}s",
                flush=True,
            )

        if n_written % args.checkpoint_every == 0:
            _save_checkpoint(checkpoint_path, arrays)

    final_arrays = {k: v for k, v in arrays.items() if k != "completed"}
    np.savez_compressed(output_path, **final_arrays)
    if checkpoint_path.exists():
        checkpoint_path.unlink()

    elapsed = time.time() - t0
    rate = n_written / elapsed if elapsed > 0 else 0.0
    print(
        f"Finished. new_rows={n_written} total_rows={n_rows} "
        f"elapsed={elapsed:.1f}s rate={rate:.2f}/s"
    )
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
