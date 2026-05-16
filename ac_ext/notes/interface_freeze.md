# Interface Freeze (Phase 4, Revised Addendum)

## Status
This document freezes `ac_ext` scenario interface semantics for follow-on controller and multifidelity work.
No final SuS or delayed-acceptance algorithm logic is frozen here, but the state schema and solver boundary are frozen.

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

Bus outage is not modeled as BUS_TYPE-only mutation.

## Truth/Proxy Boundary Freeze

### Public solver functions
- `get_engine(reuse: bool = True) -> Any`
- `close_engine() -> None`
- `run_acpf(case_data, *, debug=False, ac_fail_as_violation=True, reuse_engine=True) -> dict`
- `run_acopf(case_data, *, debug=False, ac_fail_as_violation=True, reuse_engine=True) -> dict`
- `run_dcpf(case_data, *, debug=False, ac_fail_as_violation=True, reuse_engine=True) -> dict`
- `run_fdxb(case_data, *, debug=False, ac_fail_as_violation=True, reuse_engine=True) -> dict`

`case_data` may be:
- an intact-case handle such as `'case14'`, or
- a damaged-case token routed through the existing MATLAB-side damaged-evaluation path.

### Return schema (default path)
- `success: bool`
- `s_line: float`
- `s_volt: float`
- `s_any: float` where `s_any = max(s_line, s_volt)`

Default path is scalar-only. Full bus/branch arrays remain debug-only.

## Score Semantics (Frozen)
- `s_line >= 0` => line-security violation
- `s_volt >= 0` => voltage-security violation
- `s_any = max(s_line, s_volt)`
- With `ac_fail_as_violation=True`, solver failure maps to:
  - `success = false`
  - `s_line = +Inf`
  - `s_volt = +Inf`
  - `s_any = +Inf`

MATLAB wrappers remain the default source of truth for scalar computation.

## Additional Frozen Constraints

### No MATLAB struct round-trip in the default runtime path
- Default runtime must not return a full MATPOWER struct to Python and then feed it back into MATLAB solvers.
- Damaged-case evaluation must happen on the MATLAB side (apply + solve + scalar return) in the default path.

### `sample_X` return type contract
- `sample_X(..., n=k)` must return a Python list of length `k`.
- Even for `n=1`, the canonical return type is a list with one state element.

### Controller-facing implication
- Future controller code must treat the evaluator as returning only the frozen scalar schema.
- Controller logic must not assume access to bus or branch arrays in the default runtime path.
- Controller code must remain evaluator-agnostic: truth-only, proxy-only, and future delayed-acceptance modes must all consume the same scalar schema.

## Important Case Note
- MATPOWER built-in `case14` commonly has `RATE_A = 0` on many branches; therefore `s_line = -Inf` is expected in smoke runs.
- Case14 is acceptable for interface smoke, but not for serious line-limit proxy selection.
- Phase 5 findings indicate that realistic proxy judgment should rely on larger cases such as `case30` and PGLib-style systems.
