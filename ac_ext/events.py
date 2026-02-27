"""Event semantics placeholders for AC rare-event extension (Phase 1)."""


def is_failure_event(result):
    """Determine whether an evaluation result indicates failure (placeholder).

    TODO:
        - Define failure-event schema and thresholds.
        - Align with `ac_fail_as_violation` config behavior.
    """
    raise NotImplementedError("Event logic is not implemented in Phase 1.")
