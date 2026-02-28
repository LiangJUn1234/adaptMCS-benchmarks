# AGENTS.md

## Project rules
- Add all new AC rare-event extension code under `ac_ext/`.
- Do not place new implementation files under `PIMs/python code/`.
- Do not modify legacy algorithm logic under `aESuS+BiCE/` or `DC-opf model/` unless explicitly requested.
- Legacy directories may only be imported lightly or bridged through thin adapters.
- Keep old baseline behavior unchanged unless the task explicitly asks for interface adaptation.

## Phase-4 scope
- Integration feasibility review and decision freeze only.
- Do NOT implement MCS, aE-SuS, DA-MCMC, or bulk experiments.
- Prefer adding documents under `ac_ext/notes/`.
- Optional: add thin adapter skeletons under `ac_ext/adapters/` (no algorithm logic).

## Core boundary rules (carry over)
- MATLAB wrappers remain the single source of truth for scalar score computation by default.
- Python must not recompute scalar scores from full solver arrays in the default runtime path.
- Full bus/branch arrays may only be exposed behind an explicit debug flag.

## Validation
Phase 4 is complete only if:
- Only docs (and optional adapter skeleton) are added
- No legacy logic is modified
- A concrete Phase-5 host decision is recorded
