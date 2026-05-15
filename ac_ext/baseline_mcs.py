"""Crude Monte Carlo baseline loop for AC extension (Option C)."""

from __future__ import annotations

import time
from typing import Any, Dict

from .config import DEFAULTS
from .matlab_engine import close_engine, run_acopf, run_acpf, run_dcpf
from .problem import apply_state, sample_X


def _merged_config(config_override: dict | None) -> Dict[str, Any]:
    merged = dict(DEFAULTS)
    if config_override:
        merged.update(config_override)
    return merged


def _select_truth_solver(truth: str):
    truth_key = truth.lower()
    if truth_key == "acopf":
        return truth_key, run_acopf
    if truth_key == "acpf":
        return truth_key, run_acpf
    if truth_key == "dcpf":
        return truth_key, run_dcpf
    raise ValueError("truth must be one of: acopf, acpf, dcpf")


def run_mcs(
    case_name: str,
    N: int,
    seed: int,
    truth: str,
    config_override: dict | None = None,
) -> dict:
    """Run crude MC using discrete damage-state sampling and scalar truth calls."""
    if not case_name:
        raise ValueError("case_name must be non-empty")
    if N <= 0:
        raise ValueError("N must be positive")

    merged_config = _merged_config(config_override)
    ac_fail_as_violation = bool(merged_config.get("ac_fail_as_violation", True))
    truth_key, truth_solver = _select_truth_solver(truth)

    states = sample_X(case_name, config=merged_config, n=N, seed=seed)
    if not isinstance(states, list):
        raise TypeError("sample_X must return a list of states in canonical form")

    counts = {
        "safe": 0,
        "ac_fail": 0,
        "volt_only": 0,
        "line_only": 0,
        "both": 0,
        "unknown": 0,
    }

    failures = 0
    truth_calls = 0
    t0 = time.perf_counter()

    try:
        for state in states:
            damaged_token = apply_state(case_name, state)

            if truth_key == "dcpf":
                out = truth_solver(damaged_token, debug=False, reuse_engine=True)
            else:
                out = truth_solver(
                    damaged_token,
                    debug=False,
                    ac_fail_as_violation=ac_fail_as_violation,
                    reuse_engine=True,
                )

            truth_calls += 1

            success = bool(out["success"])
            s_line = float(out["s_line"])
            s_volt = float(out["s_volt"])
            s_any = float(out["s_any"])

            if not success:
                counts["ac_fail"] += 1
                if ac_fail_as_violation:
                    failures += 1
                continue

            if s_any < 0.0:
                counts["safe"] += 1
                continue

            failures += 1
            if s_volt >= 0.0 and s_line < 0.0:
                counts["volt_only"] += 1
            elif s_line >= 0.0 and s_volt < 0.0:
                counts["line_only"] += 1
            elif s_line >= 0.0 and s_volt >= 0.0:
                counts["both"] += 1
            else:
                counts["unknown"] += 1
    finally:
        close_engine()

    elapsed_wall_s = time.perf_counter() - t0

    pf_hat = failures / float(N)
    var_hat = pf_hat * (1.0 - pf_hat) / float(N)
    cov = (var_hat ** 0.5 / pf_hat) if pf_hat > 0.0 else None

    return {
        "case": case_name,
        "truth": truth_key,
        "N": N,
        "seed": seed,
        "ac_fail_as_violation": ac_fail_as_violation,
        "pf_hat": pf_hat,
        "var_hat": var_hat,
        "cov": cov,
        "truth_calls": truth_calls,
        "elapsed_wall_s": elapsed_wall_s,
        "counts": counts,
    }
