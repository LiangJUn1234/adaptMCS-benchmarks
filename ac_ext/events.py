"""Score conventions and lightweight validators for AC rare-event extension."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping

from .exceptions import InvalidInputError


# Locked convention for this project:
# - s_line >= 0 means line-security violation.
# - s_volt >= 0 means voltage-security violation.
# - s_any = max(s_line, s_volt).


def combine_scores(s_line: float, s_volt: float) -> float:
    """Return union score according to the locked convention."""
    return max(float(s_line), float(s_volt))


def validate_scalar_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and normalize MATLAB scalar-score payload.

    Default runtime uses this validator only. It does not recompute
    scalar values from solver arrays.
    """
    required = ("success", "s_line", "s_volt", "s_any")
    missing = [k for k in required if k not in payload]
    if missing:
        raise InvalidInputError(f"Missing score fields: {missing}")

    success = bool(payload["success"])
    s_line = float(payload["s_line"])
    s_volt = float(payload["s_volt"])
    s_any = float(payload["s_any"])

    expected_s_any = combine_scores(s_line, s_volt)
    if not (
        (math.isinf(s_any) and math.isinf(expected_s_any) and (s_any > 0) == (expected_s_any > 0))
        or abs(s_any - expected_s_any) <= 1e-9
    ):
        raise InvalidInputError(
            f"Invalid score payload: s_any={s_any} expected max(s_line, s_volt)={expected_s_any}."
        )

    normalized: Dict[str, Any] = {
        "success": success,
        "s_line": s_line,
        "s_volt": s_volt,
        "s_any": s_any,
    }

    # Preserve optional debug fields unchanged.
    for key in payload:
        if key not in normalized:
            normalized[key] = payload[key]

    return normalized


def debug_scores_from_arrays(
    branch_rows: Iterable[Iterable[float]],
    bus_rows: Iterable[Iterable[float]],
) -> Dict[str, float]:
    """Optional debug-only score recomputation from detailed arrays.

    This helper mirrors MATLAB-side formulas and is intended only for
    validation when wrappers explicitly return detailed arrays.
    """
    branch = [list(row) for row in branch_rows]
    bus = [list(row) for row in bus_rows]

    # MATPOWER branch columns (1-based):
    # RATE_A=6, BR_STATUS=11, PF=14, QF=15, PT=16, QT=17.
    eligible_margins = []
    for row in branch:
        if len(row) < 17:
            continue
        rate_a = float(row[5])
        status = float(row[10])
        if status != 1.0 or not math.isfinite(rate_a) or rate_a <= 0.0:
            continue
        pf, qf, pt, qt = float(row[13]), float(row[14]), float(row[15]), float(row[16])
        loading = max(math.hypot(pf, qf), math.hypot(pt, qt))
        eligible_margins.append(loading - rate_a)

    s_line = max(eligible_margins) if eligible_margins else float("-inf")

    # MATPOWER bus columns (1-based): VM=8, VMAX=12, VMIN=13.
    volt_margins = []
    for row in bus:
        if len(row) < 13:
            continue
        vm = float(row[7])
        vmax = float(row[11])
        vmin = float(row[12])
        volt_margins.append(vmin - vm)
        volt_margins.append(vm - vmax)

    s_volt = max(volt_margins) if volt_margins else float("-inf")
    s_any = combine_scores(s_line, s_volt)
    return {"s_line": s_line, "s_volt": s_volt, "s_any": s_any}
