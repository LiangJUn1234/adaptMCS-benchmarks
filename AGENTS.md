# AGENTS.md

## Project rules
- Add all new AC rare-event extension code under `ac_ext/`.
- Do not place new implementation files under `PIMs/python code/`.
- Do not modify legacy algorithm logic under `aESuS+BiCE/` or `DC-opf model/` unless explicitly requested.
- Legacy directories may only be imported lightly or bridged through thin adapters.
- Keep old baseline behavior unchanged unless the task explicitly asks for interface adaptation.

## Phase-2 scope
- Build only the single-sample solver boundary.
- Do not implement random scenarios.
- Do not implement full baselines.
- Do not implement DA-MCMC.
- Do not run bulk experiments.
- Do not connect to legacy algorithm implementations yet unless only for a thin compatibility boundary.
- Use MATPOWER built-in case names (for example `case14`) for smoke testing in this phase.

## Core boundary rule
- In Phase 2, scalar security scores must be computed inside MATLAB wrappers by default.
- Python must not recompute scalar scores from full solver arrays in the default runtime path.
- Full bus/branch arrays may only be exposed behind an explicit debug flag.

## Score conventions
- `s_line >= 0` means line-security violation.
- `s_volt >= 0` means voltage-security violation.
- `s_any = max(s_line, s_volt)`.
- If `ac_fail_as_violation=True` and the AC solver fails, return `success=false` and `s_any=+Inf`.
- Later algorithm layers may map this to `h = -s_any`, but Phase 2 returns only scalar scores.

## Line-limit rule
- Only branches with:
  - `BR_STATUS == 1`
  - finite `RATE_A`
  - `RATE_A > 0`
  may be used for line-limit scoring.
- Branches with `RATE_A <= 0` or invalid `RATE_A` must be treated as unconstrained and excluded from the maximum.
- If no eligible constrained branches exist, set `s_line = -Inf`.

## Validation
Phase 2 is complete only if:
- `python3 -c "import ac_ext"` works
- a smoke test on a MATPOWER built-in case (for example `case14`) works
- return values are minimal scalars by default
- no legacy algorithm files are modified
- no random-scenario logic is implemented
