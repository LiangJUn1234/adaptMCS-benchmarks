# AGENTS.md

## Project rules
- Add all new AC rare-event extension code under `ac_ext/`.
- Do not place new implementation files under `PIMs/python code/`.
- Do not modify legacy algorithm logic under `aESuS+BiCE/` or `DC-opf model/` unless explicitly requested.
- Legacy directories may only be imported lightly or bridged through thin adapters.
- Keep old baseline behavior unchanged unless the task explicitly asks for interface adaptation.

## Current phase status
- Phase 1–5 foundations are complete enough to support Phase 6 scaffolding.
- Current active work is **Phase 6A**.
- Phase 6A focuses on:
  - truth-only SuS controller scaffolding
  - line-only discrete MCMC kernel
  - exact top-p0 seed-count control
  - per-level logging and termination semantics
- Phase 6B will add:
  - proxy-assisted / delayed-acceptance controller paths
  - DCOPF proxy candidate
- Phase 6C will cover:
  - mixed state space (line + bus + generator)
  - larger PGLib cases
  - stronger DA / adaptive enhancements

## Phase 6A scope
- Implement only:
  - `ac_ext/sus_controller.py`
  - `ac_ext/mcmc_sampler.py`
  - small import-safe updates under `ac_ext/problem.py` or `ac_ext/__init__.py` if strictly needed
  - notes under `ac_ext/notes/`
- Do NOT implement final delayed-acceptance logic in Phase 6A.
- Do NOT implement bus-outage or generator-derating proposal moves in Phase 6A.
- Do NOT add bulk experiment matrices or large runners in Phase 6A.
- Delayed-acceptance mode may exist as an explicit stub that raises `NotImplementedError`.

## Core boundary rules (carry over)
- MATLAB wrappers remain the single source of truth for scalar score computation by default.
- Python must not recompute scalar scores from full solver arrays in the default runtime path.
- Full bus/branch arrays may only be exposed behind an explicit debug flag.
- Default runtime path must avoid MATPOWER struct round-trip through Python.
- Existing scalar schema remains frozen:
  - `success`
  - `s_line`
  - `s_volt`
  - `s_any`

## State-space and controller rules for Phase 6A
- Internal state representation must remain compatible with the current canonical schema:
  - `line_out`
  - `bus_out`
  - `gen_derate_state`
  - `gen_scale`
- Phase 6A MCMC is restricted to the **line-only subspace**:
  - mutate only `line_out`
  - assume `bus_outage_prob = 0`
  - do not mutate generator derating
- Seed selection must use exact rank-based top-p0 control:
  - `n_seed = ceil(p0 * N)`
  - do not use naive `score >= threshold` filtering
- Default `target_violation` is `0.0`
- If a level threshold becomes `+Inf`, terminate explicitly with a clear termination reason.

## MCMC kernel rules for Phase 6A
- Allowed proposal moves:
  - Add
  - Remove
  - Swap
- For line-only homogeneous Bernoulli outage prior with probability `p`:
  - Add prior ratio = `p / (1 - p)`
  - Remove prior ratio = `(1 - p) / p`
  - Swap prior ratio = `1`
- Proposal must enforce current-level threshold constraint:
  - if proposed score is below threshold, reject immediately
- Sampler logs must include:
  - attempts
  - accepted
  - acceptance_rate
  - constraint_rejects
  - mh_rejects
  - move_counts
  - accepted_move_counts
  - n_returned
  - unique_state_count (if practical)

## Validation
Phase 6A is acceptable only if:
- `python3 -c "import ac_ext"` succeeds
- `from ac_ext.sus_controller import SuSController` succeeds
- `from ac_ext.mcmc_sampler import *` succeeds
- controller run output includes:
  - exact `n_seed`
  - `termination_reason`
  - `n_infinite_score`
  - `mean_finite_score`
  - `finite_fraction`
- no legacy logic is modified
