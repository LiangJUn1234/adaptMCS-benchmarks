"""Minimal problem interfaces for the AC rare-event extension (Phase 1)."""

from typing import Any, Dict, Mapping, Sequence

from .exceptions import InterfaceNotImplementedError, InvalidInputError


def sample_X(n: int, config: Mapping[str, Any]) -> Sequence[Any]:
    """Sample candidate random inputs for the rare-event model.

    Args:
        n: Number of samples to draw.
        config: Unified AC extension config mapping.

    Returns:
        Placeholder return type for sampled states.

    Raises:
        InvalidInputError: If input arguments are invalid.
        InterfaceNotImplementedError: Always in Phase 1 skeleton.

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
        "sample_X is a Phase 1 stub and is not implemented yet."
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
        InterfaceNotImplementedError: Always in Phase 1 skeleton.

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
        "apply_state is a Phase 1 stub and is not implemented yet."
    )


def eval_proxy(case_data: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate a fast proxy metric for rare-event screening.

    Args:
        case_data: Case data after state application.
        config: Unified AC extension config mapping.

    Returns:
        Placeholder for proxy evaluation outputs.

    Raises:
        InvalidInputError: If input arguments are invalid.
        InterfaceNotImplementedError: Always in Phase 1 skeleton.

    TODO:
        - Define proxy output contract and score semantics.
        - Add adapter boundaries for future lightweight models.
        - Implement proxy execution and error normalization.
    """
    if not isinstance(case_data, Mapping):
        raise InvalidInputError("eval_proxy requires case_data to be a mapping.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("eval_proxy requires config to be a mapping.")
    raise InterfaceNotImplementedError(
        "eval_proxy is a Phase 1 stub and is not implemented yet."
    )


def eval_truth(case_data: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate truth model outputs for final rare-event decisioning.

    Args:
        case_data: Case data prepared for truth-model execution.
        config: Unified AC extension config mapping.

    Returns:
        Placeholder for truth-model evaluation outputs.

    Raises:
        InvalidInputError: If input arguments are invalid.
        InterfaceNotImplementedError: Always in Phase 1 skeleton.

    TODO:
        - Define truth output schema including failure semantics.
        - Add future adapter boundary for MATLAB/solver integration.
        - Implement robust runtime handling and result parsing.
    """
    if not isinstance(case_data, Mapping):
        raise InvalidInputError("eval_truth requires case_data to be a mapping.")
    if not isinstance(config, Mapping):
        raise InvalidInputError("eval_truth requires config to be a mapping.")
    raise InterfaceNotImplementedError(
        "eval_truth is a Phase 1 stub and is not implemented yet."
    )
