"""MATLAB-engine boundary for single-sample AC extension evaluations."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Mapping

from .config import OSQP_NOISE_PATH, PGLIB_PATH
from .exceptions import (
    InvalidInputError,
    MatlabEngineUnavailableError,
    MatlabExecutionError,
    MatlabPathError,
    StateApplicationError,
)

_ENGINE = None
LOGGER = logging.getLogger(__name__)


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _matlab_dir() -> Path:
    return _module_dir() / "matlab"


def _get_engine_api():
    try:
        import matlab.engine  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local MATLAB install
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


def _ensure_wrapper_path(engine: Any) -> None:
    matlab_path = str(_matlab_dir())
    try:
        engine.addpath(matlab_path, nargout=0)
    except Exception as exc:
        raise MatlabPathError(f"Failed to add MATLAB wrapper path: {matlab_path}") from exc


def _sanitize_solver_path(engine: Any) -> None:
    """Best-effort removal of known noisy optional OSQP path."""
    try:
        current_path = engine.path(nargout=1)
        if isinstance(current_path, str):
            entries = current_path.split(os.pathsep)
            osqp_noise_path = str(OSQP_NOISE_PATH)
            if osqp_noise_path in entries:
                engine.rmpath(osqp_noise_path, nargout=0)
    except Exception:
        pass


def _is_damaged_case_token(case_data: Any) -> bool:
    return hasattr(case_data, "case_data") and hasattr(case_data, "state")


def _matlab_start_options() -> str:
    """Return MATLAB engine startup options tuned for non-interactive runs."""
    return os.environ.get("MATLAB_ENGINE_OPTIONS", "-nodesktop -nosplash")


def _matlab_start_timeout_sec() -> float:
    """Return MATLAB engine startup timeout in seconds."""
    return float(os.environ.get("MATLAB_ENGINE_START_TIMEOUT_SEC", "120"))


def _start_engine_with_timeout(engine_api: Any) -> Any:
    """Start MATLAB engine with bounded wait to avoid indefinite hangs."""
    result: Dict[str, Any] = {}
    options = _matlab_start_options()
    timeout_sec = _matlab_start_timeout_sec()

    def _worker() -> None:
        try:
            result["engine"] = engine_api.start_matlab(options)
        except Exception as exc:  # pragma: no cover - depends on local MATLAB install
            result["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        raise MatlabEngineUnavailableError(
            f"MATLAB engine startup exceeded timeout ({timeout_sec:.0f}s) "
            f"with options: {options!r}"
        )
    if "error" in result:
        raise MatlabEngineUnavailableError("Unable to start MATLAB engine session.") from result["error"]
    return result["engine"]


def get_engine(reuse: bool = True) -> Any:
    """Start or reuse a MATLAB engine and configure wrapper path."""
    global _ENGINE
    if reuse and _ENGINE is not None:
        return _ENGINE

    engine_api = _get_engine_api()
    try:
        engine = _start_engine_with_timeout(engine_api)
    except MatlabEngineUnavailableError:
        raise
    except Exception as exc:
        raise MatlabEngineUnavailableError("Unable to start MATLAB engine session.") from exc

    pglib_path = str(PGLIB_PATH)
    try:
        engine.addpath(pglib_path, nargout=0)
    except Exception as exc:
        print(f"Warning: Could not add PGLib path {pglib_path}: {exc}")

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
        message = f"MATLAB wrapper '{wrapper_name}' execution failed: {exc}"
        LOGGER.warning("WARNING: %s", message)
        return _failure_payload(error=message)

    converted = _struct_to_dict(result)
    if not isinstance(converted, dict):
        message = f"MATLAB wrapper '{wrapper_name}' returned a non-struct result."
        LOGGER.warning("WARNING: %s", message)
        return _failure_payload(error=message)
    return converted


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
        message = f"MATLAB damaged-case evaluation failed in mode '{mode}': {exc}"
        LOGGER.warning("WARNING: %s", message)
        return _failure_payload(error=message)

    converted = _struct_to_dict(result)
    if not isinstance(converted, dict):
        message = f"Damaged-case MATLAB evaluation in mode '{mode}' returned non-struct output."
        LOGGER.warning("WARNING: %s", message)
        return _failure_payload(error=message)
    return converted


def run_acpf(
    case_data: Any,
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    """Run minimal AC PF wrapper and return scalar score payload."""
    if _is_damaged_case_token(case_data):
        return _call_damaged_wrapper(
            case_data.case_data,
            case_data.state,
            "acpf",
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
            reuse_engine=reuse_engine,
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
    if _is_damaged_case_token(case_data):
        return _call_damaged_wrapper(
            case_data.case_data,
            case_data.state,
            "acopf",
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
            reuse_engine=reuse_engine,
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
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    """Run minimal DC PF wrapper and return scalar score payload."""
    if _is_damaged_case_token(case_data):
        return _call_damaged_wrapper(
            case_data.case_data,
            case_data.state,
            "dcpf",
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
            reuse_engine=reuse_engine,
        )

    return _call_wrapper(
        "mp_run_dcpf_minimal",
        case_data,
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
        reuse_engine=reuse_engine,
    )


def run_dcopf(
    case_data: Any,
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    """Run minimal DC OPF wrapper and return scalar score payload."""
    if _is_damaged_case_token(case_data):
        return run_dcopf_damaged(
            case_data.case_data,
            case_data.state,
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
            reuse_engine=reuse_engine,
        )

    return _call_wrapper(
        "mp_run_dcopf_minimal",
        case_data,
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
        reuse_engine=reuse_engine,
    )


def run_fdxb(
    case_data: Any,
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    """Run minimal FDXB wrapper and return scalar score payload."""
    if _is_damaged_case_token(case_data):
        return _call_damaged_wrapper(
            case_data.case_data,
            case_data.state,
            "fdxb",
            debug=debug,
            ac_fail_as_violation=ac_fail_as_violation,
            reuse_engine=reuse_engine,
        )

    return _call_wrapper(
        "mp_run_fdxb_minimal",
        case_data,
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
        reuse_engine=reuse_engine,
    )


def run_acpf_damaged(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    return _call_damaged_wrapper(
        case_data,
        state,
        "acpf",
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
        reuse_engine=reuse_engine,
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
        case_data,
        state,
        "acopf",
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
        reuse_engine=reuse_engine,
    )


def run_dcpf_damaged(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    return _call_damaged_wrapper(
        case_data,
        state,
        "dcpf",
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
        reuse_engine=reuse_engine,
    )


def run_dcopf_damaged(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    """Run DC OPF on damaged case using existing apply+wrapper surfaces."""
    if not isinstance(state, Mapping):
        raise InvalidInputError("state must be a mapping.")

    payload = json.dumps(state)
    engine = get_engine(reuse=reuse_engine)
    _sanitize_solver_path(engine)

    try:
        mpc_damaged = engine.mp_apply_damage_state_minimal(case_data, payload, nargout=1)
        result = engine.mp_run_dcopf_minimal(
            mpc_damaged,
            bool(debug),
            bool(ac_fail_as_violation),
            nargout=1,
        )
    except Exception as exc:
        message = f"MATLAB damaged-case DCOPF evaluation failed: {exc}"
        LOGGER.warning("WARNING: %s", message)
        return _failure_payload(error=message)

    converted = _struct_to_dict(result)
    if not isinstance(converted, dict):
        message = "Damaged-case MATLAB DCOPF evaluation returned non-struct output."
        LOGGER.warning("WARNING: %s", message)
        return _failure_payload(error=message)
    return converted


def run_fdxb_damaged(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    debug: bool = False,
    ac_fail_as_violation: bool = True,
    reuse_engine: bool = True,
) -> Dict[str, Any]:
    return _call_damaged_wrapper(
        case_data,
        state,
        "fdxb",
        debug=debug,
        ac_fail_as_violation=ac_fail_as_violation,
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


def get_case_sanity_after_damage(
    case_data: Any,
    state: Mapping[str, Any],
    *,
    reuse_engine: bool = True,
) -> Dict[str, float]:
    """Return sanity metrics for a damaged case without materializing the struct in Python."""
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
        raise MatlabExecutionError(
            "mp_case_sanity_after_damage_minimal returned non-struct output."
        )
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
