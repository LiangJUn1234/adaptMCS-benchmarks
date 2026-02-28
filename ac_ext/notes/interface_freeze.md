# Interface Freeze (Phase 4)

## Status
This document freezes `ac_ext` scenario interface semantics for immediate follow-on work.
No algorithmic baseline/DA logic is defined here.

## State Schema v1
A sampled discrete state is a mapping with the following required fields:

- `line_out`: `list[int]`
  - Length: `n_branch`
  - Allowed values: `{0, 1}`
  - Meaning: `1` => branch is outaged (`BR_STATUS = 0`)

- `bus_out`: `list[int]`
  - Length: `n_bus`
  - Allowed values: `{0, 1}`
  - Meaning: `1` => bus outage (conservative isolation rule applies)

- `gen_derate_state`: `list[int]`
  - Length: `n_gen`
  - Allowed values: integer index into config `gen_derate_state_values`
  - Meaning: discrete derating state index per generator

- `gen_scale`: `list[float]`
  - Length: `n_gen`
  - Allowed values: finite `>= 0`
  - Meaning: direct multiplier for generator availability/capacity

- `meta`: `dict`
  - Required keys: `seed`, `n_bus`, `n_branch`, `n_gen`
  - Meaning: sampling metadata for reproducibility and validation

Sampling parameters are centralized in `ac_ext.config.DEFAULTS` and must not be hard-coded in sampling logic.

## `apply_state` Semantics (Frozen)
Default implementation strategy: apply damage on MATLAB side.

### Line outages
- For each branch with `line_out[i] == 1`: set `BR_STATUS = 0`.

### Generator derating
- For each generator `g` with scale `gen_scale[g]`:
  - if `gen_scale[g] <= 0`: set `GEN_STATUS = 0`, set `PMAX = 0`
  - else: scale `PMAX := max(0, PMAX * gen_scale[g])`

### Bus outages (conservative MATPOWER-consistent rule)
For each outaged bus:
- mark bus isolated (`BUS_TYPE = 4`)
- outage all incident branches (`BR_STATUS = 0`)
- make connected generators unavailable (`GEN_STATUS = 0`, `PMAX = 0`)

Bus outage is **not** modeled as BUS_TYPE-only mutation.

## Truth/Proxy Boundary Freeze

### Truth solver functions (public API preserved)
- `get_engine(reuse: bool = True) -> Any`
- `close_engine() -> None`
- `run_acpf(case_data, *, debug=False, ac_fail_as_violation=True, reuse_engine=True) -> dict`
- `run_acopf(case_data, *, debug=False, ac_fail_as_violation=True, reuse_engine=True) -> dict`
- `run_dcpf(case_data, *, debug=False, reuse_engine=True) -> dict`

`case_data` may be intact-case handle (e.g., `'case14'`) or damaged-case token routed through existing adapter path.

### Return schema (default path)
- `success: bool`
- `s_line: float`
- `s_volt: float`
- `s_any: float` where `s_any = max(s_line, s_volt)`

Default path is scalar-only. Full bus/branch arrays are debug-only and must not be required by runtime scoring logic.

## Score Semantics (Frozen)
- `s_line >= 0` => line-security violation
- `s_volt >= 0` => voltage-security violation
- `s_any = max(s_line, s_volt)`
- On AC solver failure with `ac_fail_as_violation=True`: `success=false`, `s_any=+Inf` (with conservative scalar treatment)

MATLAB wrappers remain default source of truth for scalar computation.

## Important Case Note
MATPOWER built-in `case14` commonly has `RATE_A = 0` (unconstrained lines), so `s_line = -Inf` is expected in smoke runs. Use PGLib cases for line-limit studies.
