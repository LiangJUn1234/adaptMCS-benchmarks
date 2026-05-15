"""Problem interfaces for AC rare-event extension."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .config import DEFAULTS
from .events import validate_scalar_payload
from .exceptions import (
    InvalidInputError,
    StateSamplingError,
)
from .matlab_engine import (
    apply_damage_state,
    get_case_sanity,
    get_case_sanity_after_damage,
    run_acopf,
    run_acpf,
    run_dcopf,
    run_dcpf,
    run_fdxb,
)

LOGGER = logging.getLogger(__name__)

_ML_MODEL_CACHE: dict = {}


def _load_ml_model(case_name: str):
    """Lazy-load ML surrogate model, cached by case_name."""
    if case_name in _ML_MODEL_CACHE:
        return _ML_MODEL_CACHE[case_name]
    import joblib as _joblib
    from pathlib import Path as _Path

    model_path = _Path(__file__).parent / "experiments" / "out" / f"ml_surrogate_{case_name}.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"ML surrogate model not found: {model_path}")
    model = _joblib.load(model_path)
    _ML_MODEL_CACHE[case_name] = model
    return model


def _eval_ml_surrogate(case_name: str, state: Mapping[str, Any]) -> Dict[str, Any]:
    """Predict s_any using ML surrogate. No MATLAB needed."""
    import numpy as _np

    model = _load_ml_model(case_name)
    features = (
        [float(v) for v in state["line_out"]]
        + [float(v) for v in state["bus_out"]]
        + [float(v) for v in state["gen_scale"]]
    )
    x = _np.array([features], dtype=_np.float32)
    s_any_pred = float(model.predict(x)[0])
    return {
        "success": True,
        "s_line": s_any_pred,
        "s_volt": s_any_pred,
        "s_any": s_any_pred,
    }


_ML_CLASSIFIER_CACHE: dict = {}


def _load_ml_failure_classifier(case_name: str):
    """Lazy-load ML failure classifier, cached by case_name."""
    if case_name in _ML_CLASSIFIER_CACHE:
        return _ML_CLASSIFIER_CACHE[case_name]
    import joblib as _joblib
    from pathlib import Path as _Path

    model_path = _Path(__file__).parent / "experiments" / "out" / f"ml_failure_classifier_{case_name}.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"ML failure classifier not found: {model_path}")
    model = _joblib.load(model_path)
    _ML_CLASSIFIER_CACHE[case_name] = model
    return model


def _eval_ml_failure_classifier(case_name: str, state: Mapping[str, Any]) -> Dict[str, Any]:
    # s_any here is p(ACOPF failure), not a physical violation score.
    # Used only for ranking/prescreening in Level 0.
    import numpy as _np

    model = _load_ml_failure_classifier(case_name)
    features = (
        [float(v) for v in state["line_out"]]
        + [float(v) for v in state["bus_out"]]
        + [float(v) for v in state["gen_scale"]]
    )
    x = _np.array([features], dtype=_np.float32)
    p_fail = float(model.predict_proba(x)[0, 1])
    return {
        "success": True,
        "s_line": p_fail,
        "s_volt": p_fail,
        "s_any": p_fail,
    }


@dataclass(frozen=True)
class DamagedCaseSpec:
    """Lightweight token representing a damaged MATPOWER case.

    Prevents massive MATLAB structs from round-tripping through Python.
    """
    case_data: Any
    state: Mapping[str, Any]


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


def _validate_state_payload(state: Mapping[str, Any]) -> None:
    required = ("line_out", "bus_out", "gen_derate_state", "gen_scale")
    missing = [name for name in required if name not in state]
    if missing:
        raise InvalidInputError(f"state is missing required fields: {missing}")

    line_out = list(state["line_out"])
    bus_out = list(state["bus_out"])
    gen_derate_state = list(state["gen_derate_state"])
    gen_scale = list(state["gen_scale"])

    if any(v not in (0, 1) for v in line_out):
        raise InvalidInputError("line_out entries must be in {0, 1}.")
    if any(v not in (0, 1) for v in bus_out):
        raise InvalidInputError("bus_out entries must be in {0, 1}.")
    if any(int(v) != v or v < 0 for v in gen_derate_state):
        raise InvalidInputError("gen_derate_state entries must be non-negative integers.")
    if len(gen_derate_state) != len(gen_scale):
        raise InvalidInputError("gen_derate_state and gen_scale must have equal length.")

    meta = state.get("meta")
    if isinstance(meta, Mapping):
        if "n_branch" in meta and len(line_out) != int(meta["n_branch"]):
            raise InvalidInputError("line_out length does not match meta['n_branch'].")
        if "n_bus" in meta and len(bus_out) != int(meta["n_bus"]):
            raise InvalidInputError("bus_out length does not match meta['n_bus'].")
        if "n_gen" in meta and len(gen_scale) != int(meta["n_gen"]):
            raise InvalidInputError("gen_scale length does not match meta['n_gen'].")


def _failure_payload(*, error: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": False,
        "s_line": float("inf"),
        "s_volt": float("inf"),
        "s_any": float("inf"),
    }
    if error is not None:
        payload["error"] = error
    return payload


def _warn_and_failure(context: str, exc: Exception) -> Dict[str, Any]:
    message = f"{type(exc).__name__}: {exc}"
    LOGGER.warning("WARNING: %s failed: %s", context, message)
    return _failure_payload(error=message)


def sample_X(
    case_data: Any = "case14",
    config: Optional[Mapping[str, Any]] = None,
    *,
    n: int = 1,
    seed: Optional[int] = None,
) -> Sequence[Dict[str, Any]]:
    """Sample discrete component damage states for a MATPOWER case.

    Output representation for each sampled state:
    - `line_out`: list[int], length n_branch, entries in {0,1}; 1 means outage.
    - `bus_out`: list[int], length n_bus, entries in {0,1}; 1 means bus outage.
    - `gen_derate_state`: list[int], length n_gen; index into derating state values.
    - `gen_scale`: list[float], length n_gen; resolved derating multiplier.
    - `meta`: dict with `seed` and case dimensions.

    Returns:
        Canonical Python list of sampled states for all n >= 1, including n=1.
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

        state = {
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
        _validate_state_payload(state)
        samples.append(state)

    return samples


def apply_state(
    case_data: Any,
    state: Mapping[str, Any],
) -> DamagedCaseSpec:
    """Return a lightweight token representing the damaged case.

    This avoids returning the materialized MATLAB struct to Python,
    preventing IPC overhead and MATPOWER struct round-trip issues.
    """
    if not isinstance(state, Mapping):
        raise InvalidInputError("apply_state requires state to be a mapping.")
    _validate_state_payload(state)
    return DamagedCaseSpec(case_data=case_data, state=state)


def apply_state_debug(
    case_data: Any,
    state: Mapping[str, Any],
) -> Any:
    """Materialize and return the full MATLAB struct for debugging only."""
    _validate_state_payload(state)
    return apply_damage_state(case_data, state)


def eval_proxy(
    case_name: str,
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    proxy_mode: str = "dcpf",
    debug: bool = False,
) -> Dict[str, Any]:
    """Evaluate a single damaged case using the selected proxy solver.

    Supported proxy modes:
    - 'dcpf'
    - 'fdxb'
    - 'dcopf'
    - 'ml_surrogate'
    - 'ml_failure'
    """
    if not isinstance(case_name, str) or not case_name.strip():
        raise InvalidInputError("case_name must be a non-empty MATPOWER case name.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("config must be a mapping.")
    if proxy_mode not in {"dcpf", "fdxb", "dcopf", "ml_surrogate", "ml_failure"}:
        raise InvalidInputError("proxy_mode must be one of {'dcpf', 'fdxb', 'dcopf', 'ml_surrogate', 'ml_failure'}.")

    if proxy_mode == "ml_surrogate":
        try:
            return validate_scalar_payload(_eval_ml_surrogate(case_name, state))
        except Exception as exc:
            return _warn_and_failure(f"eval_proxy[ml_surrogate]({case_name})", exc)

    if proxy_mode == "ml_failure":
        try:
            return validate_scalar_payload(_eval_ml_failure_classifier(case_name, state))
        except Exception as exc:
            return _warn_and_failure(f"eval_proxy[ml_failure]({case_name})", exc)

    try:
        ac_fail_as_violation = bool(config.get("ac_fail_as_violation", True))
        damaged = apply_state(case_name, state)

        if proxy_mode == "dcpf":
            return validate_scalar_payload(
                run_dcpf(
                    damaged,
                    debug=debug,
                    ac_fail_as_violation=ac_fail_as_violation,
                )
            )
        if proxy_mode == "dcopf":
            return validate_scalar_payload(
                run_dcopf(
                    damaged,
                    debug=debug,
                    ac_fail_as_violation=ac_fail_as_violation,
                )
            )

        return validate_scalar_payload(
            run_fdxb(
                damaged,
                debug=debug,
                ac_fail_as_violation=ac_fail_as_violation,
            )
        )
    except Exception as exc:
        return _warn_and_failure(f"eval_proxy[{proxy_mode}]({case_name})", exc)


def eval_truth(
    case_name: str,
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    truth_mode: str = "acopf",
    debug: bool = False,
) -> Dict[str, Any]:
    """Evaluate a single damaged case using the selected truth solver."""
    if not isinstance(case_name, str) or not case_name.strip():
        raise InvalidInputError("case_name must be a non-empty MATPOWER case name.")
    if not isinstance(state, Mapping):
        raise InvalidInputError("state must be a mapping.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("config must be a mapping.")
    if truth_mode not in {"acopf", "acpf", "dcpf"}:
        raise InvalidInputError("truth_mode must be one of {'acopf', 'acpf', 'dcpf'}.")

    ac_fail_as_violation = bool(config.get("ac_fail_as_violation", True))
    damaged = apply_state(case_name, state)

    solver = {
        "acopf": run_acopf,
        "acpf": run_acpf,
        "dcpf": run_dcpf,
    }[truth_mode]

    try:
        return validate_scalar_payload(
            solver(
                damaged,
                debug=debug,
                ac_fail_as_violation=ac_fail_as_violation,
            )
        )
    except Exception as exc:
        return _warn_and_failure(f"eval_truth[{truth_mode}]({case_name})", exc)


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
            ac_fail_as_violation=ac_fail_as_violation,
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
    """Run single-sample solvers on a MATLAB-side damaged case token."""
    if not isinstance(case_name, str) or not case_name.strip():
        raise InvalidInputError("case_name must be a non-empty MATPOWER case name.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("config must be a mapping.")

    ac_fail_as_violation = bool(config.get("ac_fail_as_violation", True))
    damaged = apply_state(case_name, state)

    acpf = validate_scalar_payload(
        run_acpf(
            damaged,
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
        )
    )
    acopf = validate_scalar_payload(
        run_acopf(
            damaged,
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
        )
    )
    dcpf = validate_scalar_payload(
        run_dcpf(
            damaged,
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
        )
    )

    return {"acpf": acpf, "acopf": acopf, "dcpf": dcpf}


def case_sanity(case_data: Any) -> Dict[str, float]:
    """Return sanity metrics: branch-online count, online PMAX total, PD total."""
    return get_case_sanity(case_data)


def case_sanity_after_damage(case_data: Any, state: Mapping[str, Any]) -> Dict[str, float]:
    """Return sanity metrics for a damaged case without materializing full struct in Python."""
    _validate_state_payload(state)
    return get_case_sanity_after_damage(case_data, state)


def sanity_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, float]:
    """Return before/after deltas for key sanity metrics."""
    keys = ("n_branch_online", "pmax_online_total", "pd_total")
    return {f"{k}_delta": float(after[k]) - float(before[k]) for k in keys}
