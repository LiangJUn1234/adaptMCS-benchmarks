"""MATLAB-engine boundary for single-sample AC extension evaluations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from .exceptions import (
    InvalidInputError,
    MatlabEngineUnavailableError,
    MatlabExecutionError,
    MatlabPathError,
    StateApplicationError,
)

_ENGINE = None
_OSQP_NOISE_PATH = "/home/lhftr/code/power-rare-events/matpower/mp-opt-model/.github/osqp"


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _matlab_dir() -> Path:
    return _module_dir() / "matlab"


def _get_engine_api():
    try:
        import matlab.engine  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on system MATLAB install
        raise MatlabEngineUnavailableError(
            "matlab.engine could not be imported. Install MATLAB Engine for Python."
        ) from exc
    return matlab.engine


def _struct_to_dict(value: Any) -> Any:
    """Recursively convert MATLAB engine return values to Python primitives/dicts."""
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value

    fieldnames = getattr(value, "_fieldnames", None)
    if fieldnames is not None:
        return {name: _struct_to_dict(getattr(value, name)) for name in fieldnames}

    if isinstance(value, (list, tuple)):
        return [_struct_to_dict(item) for item in value]

    return value


def _ensure_wrapper_path(engine: Any) -> None:
    matlab_path = str(_matlab_dir())
    try:
        engine.addpath(matlab_path, nargout=0)
    except Exception as exc:
        raise MatlabPathError(f"Failed to add MATLAB wrapper path: {matlab_path}") from exc


def _sanitize_solver_path(engine: Any) -> None:
    """Remove known noisy optional OSQP path only if it is on MATLAB path."""
    escaped = _OSQP_NOISE_PATH.replace("'", "''")
    cmd = (
        "p = strsplit(path, pathsep); "
        f"if any(strcmp(p, '{escaped}')), "
        f"try, rmpath('{escaped}'); catch, end; "
        "end"
    )
    try:
        engine.eval(cmd, nargout=0)
    except Exception:
        pass


def get_engine(reuse: bool = True) -> Any:
    """Start or reuse a MATLAB engine and configure wrapper path."""
    global _ENGINE
    if reuse and _ENGINE is not None:
        return _ENGINE

    engine_api = _get_engine_api()
    try:
        engine = engine_api.start_matlab()
    except Exception as exc:
        raise MatlabEngineUnavailableError("Unable to start MATLAB engine session.") from exc

    _ensure_wrapper_path(engine)
    _sanitize_solver_path(engine)

    if reuse:
        _ENGINE = engine
    return engine


def close_engine() -> None:
    """Close cached MATLAB engine session if present."""
    global _ENGINE
    if _ENGINE is None:
        return
    try:
        _ENGINE.quit()
    finally:
        _ENGINE = None


def _call_wrapper(
    wrapper_name: str,
    case_data: Any,
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    if not isinstance(wrapper_name, str) or not wrapper_name:
        raise InvalidInputError("wrapper_name must be a non-empty string.")

    engine = get_engine(reuse=reuse_engine)
    _sanitize_solver_path(engine)

    try:
        wrapper = getattr(engine, wrapper_name)
    except AttributeError as exc:
        raise MatlabExecutionError(
            f"MATLAB wrapper '{wrapper_name}' is not available on MATLAB path."
        ) from exc

    try:
        result = wrapper(case_data, bool(debug), bool(ac_fail_as_violation), nargout=1)
    except Exception as exc:
        raise MatlabExecutionError(
            f"MATLAB wrapper '{wrapper_name}' execution failed: {exc}"
        ) from exc

    converted = _struct_to_dict(result)
    if not isinstance(converted, dict):
        raise MatlabExecutionError(
            f"MATLAB wrapper '{wrapper_name}' returned a non-struct result."
        )
    return converted


def run_acpf(
    case_data: Any,
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    """Run minimal AC PF wrapper and return scalar score payload."""
    if hasattr(case_data, "case_data") and hasattr(case_data, "state"):
        return _call_damaged_wrapper(
            case_data.case_data, case_data.state, "acpf",
            debug=debug, ac_fail_as_violation=ac_fail_as_violation, reuse_engine=reuse_engine
        )

    return _call_wrapper(
        "mp_run_acpf_minimal",
        case_data,
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
        reuse_engine=reuse_engine,
    )


def run_acopf(
    case_data: Any,
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    """Run minimal AC OPF wrapper and return scalar score payload."""
    if hasattr(case_data, "case_data") and hasattr(case_data, "state"):
        return _call_damaged_wrapper(
            case_data.case_data, case_data.state, "acopf",
            debug=debug, ac_fail_as_violation=ac_fail_as_violation, reuse_engine=reuse_engine
        )

    return _call_wrapper(
        "mp_run_acopf_minimal",
        case_data,
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
        reuse_engine=reuse_engine,
    )


def run_dcpf(
    case_data: Any,
    *,
    debug: bool = False,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    """Run minimal DC PF wrapper and return scalar score payload."""
    if hasattr(case_data, "case_data") and hasattr(case_data, "state"):
        return _call_damaged_wrapper(
            case_data.case_data, case_data.state, "dcpf",
            debug=debug, ac_fail_as_violation=False, reuse_engine=reuse_engine
        )

    return _call_wrapper(
        "mp_run_dcpf_minimal",
        case_data,
        debug=debug,
        ac_fail_as_violation=False,
        reuse_engine=reuse_engine,
    )


def get_case_sanity(case_data: Any, *, reuse_engine: bool = True) -> Dict[str, float]:
    """Return basic case sanity counts/totals via MATLAB helper."""
    engine = get_engine(reuse=reuse_engine)
    _sanitize_solver_path(engine)
    try:
        result = engine.mp_case_sanity_minimal(case_data, nargout=1)
    except Exception as exc:
        raise MatlabExecutionError(f"mp_case_sanity_minimal failed: {exc}") from exc

    converted = _struct_to_dict(result)
    if not isinstance(converted, dict):
        raise MatlabExecutionError("mp_case_sanity_minimal returned non-struct output.")
    return converted


def apply_damage_state(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    reuse_engine: bool = True,
) -> Any:
    """Apply discrete damage state on MATLAB side and return transformed case struct."""
    if not isinstance(state, Mapping):
        raise InvalidInputError("state must be a mapping.")

    payload = json.dumps(state)
    engine = get_engine(reuse=reuse_engine)
    _sanitize_solver_path(engine)

    try:
        return engine.mp_apply_damage_state_minimal(case_data, payload, nargout=1)
    except Exception as exc:
        raise StateApplicationError(f"mp_apply_damage_state_minimal failed: {exc}") from exc
    
def _call_damaged_wrapper(
    case_data: Any,
    state: Mapping[str, Any],
    mode: str,
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    if not isinstance(state, Mapping):
        raise InvalidInputError("state must be a mapping.")

    payload = json.dumps(state)
    engine = get_engine(reuse=reuse_engine)
    _sanitize_solver_path(engine)

    try:
        result = engine.mp_eval_damaged_case_minimal(
            case_data,
            payload,
            mode,
            bool(debug),
            bool(ac_fail_as_violation),
            nargout=1,
        )
    except Exception as exc:
        raise MatlabExecutionError(
            f"MATLAB damaged-case evaluation failed in mode '{mode}': {exc}"
        ) from exc

    converted = _struct_to_dict(result)
    if not isinstance(converted, dict):
        raise MatlabExecutionError(
            f"Damaged-case MATLAB evaluation in mode '{mode}' returned non-struct output."
        )
    return converted

def run_acpf_damaged(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    return _call_damaged_wrapper(
        case_data, state, "acpf", debug=debug, 
        ac_fail_as_violation=ac_fail_as_violation, reuse_engine=reuse_engine
    )

def run_acopf_damaged(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    return _call_damaged_wrapper(
        case_data, state, "acopf", debug=debug, 
        ac_fail_as_violation=ac_fail_as_violation, reuse_engine=reuse_engine
    )

def run_dcpf_damaged(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    debug: bool = False,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    return _call_damaged_wrapper(
        case_data, state, "dcpf", debug=debug, 
        ac_fail_as_violation=False, reuse_engine=reuse_engine
    )

def get_case_sanity_after_damage(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    reuse_engine: bool = True,
) -> Dict[str, float]:
    if not isinstance(state, Mapping):
        raise InvalidInputError("state must be a mapping.")

    payload = json.dumps(state)
    engine = get_engine(reuse=reuse_engine)
    _sanitize_solver_path(engine)

    try:
        result = engine.mp_case_sanity_after_damage_minimal(case_data, payload, nargout=1)
    except Exception as exc:
        raise MatlabExecutionError(f"mp_case_sanity_after_damage_minimal failed: {exc}") from exc

    converted = _struct_to_dict(result)
    if not isinstance(converted, dict):
        raise MatlabExecutionError("mp_case_sanity_after_damage_minimal returned non-struct output.")
    return converted