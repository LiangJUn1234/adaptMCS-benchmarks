"""Problem interfaces for AC rare-event extension."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from .events import validate_scalar_payload
from .exceptions import InterfaceNotImplementedError, InvalidInputError
from .matlab_engine import run_acopf, run_acpf, run_dcpf


def sample_X(n: int, config: Mapping[str, Any]) -> Sequence[Any]:
    """Sample candidate random inputs for the rare-event model.

    Args:
        n: Number of samples to draw.
        config: Unified AC extension config mapping.

    Returns:
        Placeholder return type for sampled states.

    Raises:
        InvalidInputError: If input arguments are invalid.
        InterfaceNotImplementedError: Always in current phase.

    TODO:
        - Define concrete sample representation and dtype.
        - Validate required distribution parameters from config.
        - Implement sampling strategy and RNG plumbing.
    """
    if n <= 0:
        raise InvalidInputError("sample_X requires n > 0.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("sample_X requires config to be a mapping.")
    raise InterfaceNotImplementedError(
        "sample_X is not implemented in this phase."
    )


def apply_state(case_data: Dict[str, Any], state: Mapping[str, Any]) -> Dict[str, Any]:
    """Apply a sampled state to network case data.

    Args:
        case_data: Base case dictionary to adapt.
        state: State perturbation information to apply.

    Returns:
        Placeholder for transformed case data.

    Raises:
        InvalidInputError: If inputs are missing or malformed.
        InterfaceNotImplementedError: Always in current phase.

    TODO:
        - Define canonical schema for state-to-case transformations.
        - Specify immutable vs mutable case handling policy.
        - Implement state application and consistency checks.
    """
    if not isinstance(case_data, dict):
        raise InvalidInputError("apply_state requires case_data to be a dict.")
    if not isinstance(state, Mapping):
        raise InvalidInputError("apply_state requires state to be a mapping.")
    raise InterfaceNotImplementedError(
        "apply_state is not implemented in this phase."
    )


def eval_proxy(case_data: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate a proxy metric for scenario-based screening.

    Raises InterfaceNotImplementedError in this phase because random
    scenario workflow is out of scope.
    """
    if not isinstance(case_data, Mapping):
        raise InvalidInputError("eval_proxy requires case_data to be a mapping.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("eval_proxy requires config to be a mapping.")
    raise InterfaceNotImplementedError(
        "eval_proxy for random scenarios is not implemented in this phase."
    )


def eval_truth(case_data: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate truth model for scenario-based workflow.

    Raises InterfaceNotImplementedError in this phase because random
    scenario workflow is out of scope.
    """
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
    """Run minimal single-sample AC PF/AC OPF/DC PF on one intact case.

    This helper is intentionally narrow and does not implement random
    scenario generation/state application.
    """
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
