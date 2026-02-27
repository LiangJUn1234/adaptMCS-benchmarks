# AGENTS.md

## Project rules
- Add all new AC rare-event extension code under `ac_ext/`.
- Do not place new implementation files under `PIMs/python code/`.
- Do not modify legacy algorithm logic under `aESuS+BiCE/` or `DC-opf model/` unless explicitly requested.
- Legacy directories may only be imported lightly or bridged through thin adapters.
- Keep old baseline behavior unchanged unless the task explicitly asks for interface adaptation.

## Phase-3 scope
- Build only the discrete damage-state scenario layer on top of the single-sample solver boundary.
- Do not implement MCS, aE-SuS, DA-MCMC, or bulk experiments.
- Do not connect to legacy algorithm implementations yet.
- Use MATPOWER built-in case names (for example `case14`) for smoke testing in this phase.

## Core boundary rules
- MATLAB wrappers remain the single source of truth for scalar score computation by default.
- Python must not recompute scalar scores from full solver arrays in the default runtime path.
- Full bus/branch arrays may only be exposed behind an explicit debug flag.
- The MATLAB engine layer should defensively remove the path:
  `/home/lhftr/code/power-rare-events/matpower/mp-opt-model/.github/osqp`
  before solver calls, to avoid optional OSQP path noise.

## Random model rules
- Implement only discrete component damage states in this phase.
- Support:
  - generator multi-state derating
  - line binary outage
  - bus binary outage
- Keep the representation explicit, documented, and deterministic under a fixed random seed.

## Scenario rules
- `sample_X` must generate structured discrete states only.
- `apply_state` must modify a MATPOWER case conservatively and explicitly.
- Do not implement continuous load uncertainty in this phase.
- Do not implement batch sampling APIs beyond what is needed for local smoke tests.

## Score conventions
- `s_line >= 0` means line-security violation.
- `s_volt >= 0` means voltage-security violation.
- `s_any = max(s_line, s_volt)`.
- If `ac_fail_as_violation=True` and the AC solver fails, return `success=false` and `s_any=+Inf`.
- Later algorithm layers may map this to `h = -s_any`, but Phase 3 still works with scalar scores.

## Line-limit rule
- Only branches with:
  - `BR_STATUS == 1`
  - finite `RATE_A`
  - `RATE_A > 0`
  may be used for line-limit scoring.
- Branches with `RATE_A <= 0` or invalid `RATE_A` must be treated as unconstrained and excluded from the maximum.
- If no eligible constrained branches exist, set `s_line = -Inf`.

## Validation
Phase 3 is complete only if:
- `python3 -c "import ac_ext"` works
- one intact-case smoke test still works
- one damaged-state smoke test on a built-in case works
- `sample_X` and `apply_state` are implemented and documented
- no legacy algorithm files are modified
- no baseline or DA logic is implemented
