# AGENTS.md

## Project rules
- Add all new AC rare-event extension code under `ac_ext/`.
- Do not place new implementation files under `PIMs/python code/`.
- Do not modify legacy algorithm logic under `aESuS+BiCE/` or `DC-opf model/` unless explicitly requested.
- Legacy directories may only be imported lightly or bridged through thin adapters.
- Keep old baseline behavior unchanged unless the task explicitly asks for interface adaptation.

## Phase-1 scope
- Build engineering skeleton only.
- Define minimal interfaces and config.
- Do not implement full algorithms.
- No bulk experiments.
- No DA-MCMC in this phase.
- Do not connect to legacy algorithm implementations yet; only define future adapter boundaries.

## Required interfaces
Implement stubs only for:
- `sample_X`
- `apply_state`
- `eval_proxy`
- `eval_truth`

Each function must include:
- signature
- docstring
- TODO notes
- explicit exception types

## Config defaults
Use one unified config with:
- `N=2000`
- `p0=0.1`
- `tol=0.8`
- `sigma0=0.05`
- `sigma_decay=0.5`
- `ac_fail_as_violation=True`

## Validation
Phase 1 is complete only if:
- `import ac_ext` works
- there are no broken imports
- config is centralized
- minimal interfaces are defined
