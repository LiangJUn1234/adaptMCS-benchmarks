"""Problem interfaces for AC rare-event extension."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence
@dataclass(frozen=True)
class DamagedCaseSpec:
    """Lightweight token representing a damaged MATPOWER case.
    Prevents massive MATLAB structs from round-tripping through Python.
    """
    case_data: Any
    state: Mapping[str, Any]

from .config import DEFAULTS
from .events import validate_scalar_payload
from .exceptions import (
    InterfaceNotImplementedError,
    InvalidInputError,
    StateSamplingError,
)

from .matlab_engine import (
    apply_damage_state,
    get_case_sanity,
    get_case_sanity_after_damage,
    run_acopf,
    run_acpf,
    run_dcpf,
    run_acopf_damaged,
    run_acpf_damaged,
    run_dcpf_damaged,
)

def _merged_config(config: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged = dict(DEFAULTS)
    if config is not None:
        merged.update(dict(config))
    return merged


def _validate_sampling_config(config: Mapping[str, Any]) -> None:
    p_line = float(config["line_outage_prob"])
    p_bus = float(config["bus_outage_prob"])
    if not (0.0 <= p_line <= 1.0):
        raise InvalidInputError("line_outage_prob must be in [0, 1].")
    if not (0.0 <= p_bus <= 1.0):
        raise InvalidInputError("bus_outage_prob must be in [0, 1].")

    values = list(config["gen_derate_state_values"])
    probs = list(config["gen_derate_state_probs"])
    if not values:
        raise InvalidInputError("gen_derate_state_values must be non-empty.")
    if len(values) != len(probs):
        raise InvalidInputError(
            "gen_derate_state_values and gen_derate_state_probs must have equal length."
        )
    if any(v < 0 for v in values):
        raise InvalidInputError("gen_derate_state_values must be >= 0.")
    if any(p < 0 for p in probs):
        raise InvalidInputError("gen_derate_state_probs must be >= 0.")
    if sum(probs) <= 0:
        raise InvalidInputError("gen_derate_state_probs must have positive total weight.")


def sample_X(
    case_data: Any = "case14",
    config: Optional[Mapping[str, Any]] = None,
    *,
    n: int = 1,
    seed: Optional[int] = None,
) -> Sequence[Dict[str, Any]] | Dict[str, Any]:
    """Sample discrete component damage states for a MATPOWER case.

    Output representation for each sampled state:
    - `line_out`: list[int], length n_branch, entries in {0,1}; 1 means outage.
    - `bus_out`: list[int], length n_bus, entries in {0,1}; 1 means bus outage.
    - `gen_derate_state`: list[int], length n_gen; index into derating state values.
    - `gen_scale`: list[float], length n_gen; resolved derating multiplier.
    - `meta`: dict with `seed` and case dimensions.

    Args:
        n: Number of damage states to sample.
        config: Unified AC extension config mapping.
        case_data: MATPOWER case name or struct for dimension inference.
        seed: Optional deterministic RNG seed.

    Returns:
        Sequence of sampled discrete damage states.

    Raises:
        InvalidInputError: For invalid inputs or configuration values.
        StateSamplingError: If case dimensions cannot be resolved.

    TODO:
        - Add optional component-group correlated outage model.
        - Add schema version tag for state payload evolution.
    """
    if n <= 0:
        raise InvalidInputError("sample_X requires n > 0.")
    if config is not None and not isinstance(config, Mapping):
        raise InvalidInputError("sample_X requires config to be a mapping.")

    cfg = _merged_config(config)
    _validate_sampling_config(cfg)

    try:
        sanity = get_case_sanity(case_data)
    except Exception as exc:
        raise StateSamplingError(f"Unable to infer case dimensions: {exc}") from exc

    n_bus = int(sanity["n_bus"])
    n_branch = int(sanity["n_branch"])
    n_gen = int(sanity["n_gen"])

    p_line = float(cfg["line_outage_prob"])
    p_bus = float(cfg["bus_outage_prob"])
    derate_values = list(map(float, cfg["gen_derate_state_values"]))
    derate_probs = list(map(float, cfg["gen_derate_state_probs"]))

    rng = random.Random(seed)
    samples: List[Dict[str, Any]] = []

    for _ in range(n):
        line_out = [1 if rng.random() < p_line else 0 for _ in range(n_branch)]
        bus_out = [1 if rng.random() < p_bus else 0 for _ in range(n_bus)]

        gen_states = rng.choices(range(len(derate_values)), weights=derate_probs, k=n_gen)
        gen_scale = [derate_values[idx] for idx in gen_states]

        samples.append(
            {
                "line_out": line_out,
                "bus_out": bus_out,
                "gen_derate_state": gen_states,
                "gen_scale": gen_scale,
                "meta": {
                    "seed": seed,
                    "n_bus": n_bus,
                    "n_branch": n_branch,
                    "n_gen": n_gen,
                },
            }
        )

    return samples[0] if n == 1 else samples

def apply_state(
    case_data: Any,
    state: Mapping[str, Any],
) -> DamagedCaseSpec:
    """Return a lightweight token representing the damaged case.
    
    This avoids returning the materialized MATLAB struct to Python, 
    preventing IPC overhead and MATPOWER ext2int type-corruption crashes.
    """
    if not isinstance(state, Mapping):
        raise InvalidInputError("apply_state requires state to be a mapping.")
    required = ("line_out", "bus_out", "gen_derate_state", "gen_scale")
    missing = [name for name in required if name not in state]
    if missing:
        raise InvalidInputError(f"apply_state state is missing required fields: {missing}")

    return DamagedCaseSpec(case_data=case_data, state=state)

def apply_state_debug(
    case_data: Any,
    state: Mapping[str, Any],
) -> Any:
    """WARNING: Materializes and returns the full MATLAB struct.
    For debugging only. Do NOT pass the result back to run_acpf/opf.
    """
    return apply_damage_state(case_data, state)



def eval_proxy(case_data: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate proxy metric for scenario-based screening (out of scope)."""
    if not isinstance(case_data, Mapping):
        raise InvalidInputError("eval_proxy requires case_data to be a mapping.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("eval_proxy requires config to be a mapping.")
    raise InterfaceNotImplementedError(
        "eval_proxy for random scenarios is not implemented in this phase."
    )


def eval_truth(case_data: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate truth model for scenario-based workflow (out of scope)."""
    if not isinstance(case_data, Mapping):
        raise InvalidInputError("eval_truth requires case_data to be a mapping.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("eval_truth requires config to be a mapping.")
    raise InterfaceNotImplementedError(
        "eval_truth for random scenarios is not implemented in this phase."
    )


def eval_single_case(
    case_name: str,
    config: Mapping[str, Any],
    *,
    debug: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Run minimal single-sample AC PF/AC OPF/DC PF on one intact case."""
    if not isinstance(case_name, str) or not case_name.strip():
        raise InvalidInputError("case_name must be a non-empty MATPOWER case name.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("config must be a mapping.")

    ac_fail_as_violation = bool(config.get("ac_fail_as_violation", True))

    acpf = validate_scalar_payload(
        run_acpf(
            case_name,
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
        )
    )
    acopf = validate_scalar_payload(
        run_acopf(
            case_name,
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
        )
    )
    dcpf = validate_scalar_payload(
        run_dcpf(
            case_name,
            debug=debug,
        )
    )

    return {"acpf": acpf, "acopf": acopf, "dcpf": dcpf}


def eval_single_damaged_case(
    case_name: str,
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    debug: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Run single-sample solvers on a MATLAB-side damaged case payload."""
    if not isinstance(case_name, str) or not case_name.strip():
        raise InvalidInputError("case_name must be a non-empty MATPOWER case name.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("config must be a mapping.")

    ac_fail_as_violation = bool(config.get("ac_fail_as_violation", True))

    # 1. 获取轻量级 Token
    damaged = apply_state(case_name, state)

    # 2. 像完整 case 一样直接传入普通 wrapper
    acpf = validate_scalar_payload(
        run_acpf(damaged, debug=debug, ac_fail_as_violation=ac_fail_as_violation)
    )
    acopf = validate_scalar_payload(
        run_acopf(damaged, debug=debug, ac_fail_as_violation=ac_fail_as_violation)
    )
    dcpf = validate_scalar_payload(
        run_dcpf(damaged, debug=debug)
    )

    return {"acpf": acpf, "acopf": acopf, "dcpf": dcpf}


def case_sanity(case_data: Any) -> Dict[str, float]:
    """Return sanity metrics: branch-online count, online PMAX total, PD total."""
    return get_case_sanity(case_data)

def case_sanity_after_damage(case_data: Any, state: Mapping[str, Any]) -> Dict[str, float]:
    """Return sanity metrics for a damaged case without returning the full struct."""
    return get_case_sanity_after_damage(case_data, state)


def sanity_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, float]:
    """Return before/after deltas for key sanity metrics."""
    keys = ("n_branch_online", "pmax_online_total", "pd_total")
    return {f"{k}_delta": float(after[k]) - float(before[k]) for k in keys}
