"""Tiny smoke runner for intact and damaged single-sample case14 evaluations."""
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ac_ext.config import DEFAULTS
from ac_ext.matlab_engine import get_engine, close_engine, run_acopf, run_acpf, run_dcpf
from ac_ext.problem import (
    case_sanity,
    case_sanity_after_damage,
    apply_state,
    sample_X,
    sanity_delta,
)

if __name__ == "__main__":
    case_name = "case14"
    seed = 1

    cfg = dict(DEFAULTS)
    cfg["line_outage_prob"] = 0.05
    cfg["bus_outage_prob"] = 0.0

    get_engine()
    try:
        print("== Intact case ==")
        print("ACOPF:", run_acopf(case_name, reuse_engine=True))

        print("\n== Damaged case ==")
        sampled = sample_X(case_name, config=cfg, n=1, seed=seed)[0]
        token = apply_state(case_name, sampled)

        print("state keys:", sorted(sampled.keys()))
        print("line_out_idx:", [i for i, v in enumerate(sampled["line_out"]) if v == 1])
        print("bus_out_idx :", [i for i, v in enumerate(sampled["bus_out"]) if v == 1])
        print("gen_states  :", sampled["gen_derate_state"])
        print("gen_scales  :", sampled["gen_scale"])

        before = case_sanity(case_name)
        after = case_sanity_after_damage(case_name, sampled)
        print("sanity_before:", before)
        print("sanity_after :", after)
        print("sanity_delta :", sanity_delta(before, after))

        print("\n== Scores ==")
        print("DCPF :", run_dcpf(token, ac_fail_as_violation=True, reuse_engine=True))
        print("ACPF :", run_acpf(token, ac_fail_as_violation=True, reuse_engine=True))
        print("ACOPF:", run_acopf(token, ac_fail_as_violation=True, reuse_engine=True))
    finally:
        close_engine()
