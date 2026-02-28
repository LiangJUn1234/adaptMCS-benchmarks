"""Tiny smoke runner for intact and damaged single-sample case14 evaluations."""

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ac_ext.config import DEFAULTS

from ac_ext.problem import (
    case_sanity,
    case_sanity_after_damage,
    eval_single_case,
    eval_single_damaged_case,
    sample_X,
    sanity_delta,
)


def _summarize_state(state):
    return {
        "n_line_out": int(sum(state["line_out"])),
        "n_bus_out": int(sum(state["bus_out"])),
        "n_gen_off": int(sum(1 for x in state["gen_scale"] if x <= 0.0)),
        "gen_state_counts": {
            str(i): int(state["gen_derate_state"].count(i))
            for i in sorted(set(state["gen_derate_state"]))
        },
    }


if __name__ == "__main__":
    case_name = "case14"
    seed = 7

    print("== Intact case ==")
    intact_scores = eval_single_case(case_name, DEFAULTS)
    print(intact_scores)

    print("== Damaged case ==")
    # 1. 正常采样（大概率是个无损伤的安全状态）
    sampled = sample_X(case_name, config=DEFAULTS, seed=seed)

   
    print("state_summary:", _summarize_state(sampled))

    before = case_sanity(case_name)
    after = case_sanity_after_damage(case_name, sampled)

    print("sanity_before:", before)
    print("sanity_after:", after)
    print("sanity_delta:", sanity_delta(before, after))

    damaged_scores = eval_single_damaged_case(case_name, sampled, DEFAULTS)
    print("scores:", damaged_scores)
