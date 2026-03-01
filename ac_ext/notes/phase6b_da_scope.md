# Phase 6B Delayed-Acceptance Scope

Phase 6B adds controller-side engineering proxy assistance in `ac_ext` only:

- evaluator modes in `SuSController`:
  - `truth_only`
  - `proxy_only`
  - `delayed_acceptance`
- proxy candidate extension includes `dcopf` in addition to existing `dcpf` and `fdxb`.

## What is implemented in this phase

- Engineering delayed-acceptance gate (two-stage screening):
  1. Stage 1 proxy screening against current level threshold.
  2. Stage 2 truth check for stage-1 passes.
  3. MH accept/reject on stage-2 passes using the existing truth-side MH criterion already used in truth-only mode.
- Phase 6B delayed-acceptance explicitly applies only to conditional evolution levels (Level 1+). Level 0 remains strictly truth-evaluated to ensure statistically unbiased threshold initialization.
- Per-level and controller call accounting for proxy/truth usage and DA gate ratios.

## Intentionally deferred (not implemented in Phase 6B)

- Exact delayed-acceptance MH correction theory.
- Bus-outage proposal moves.
- Generator-derating proposal moves.
- Mixed state-space proposal kernel (line+bus+gen).

## Rationale for adding DCOPF proxy

DCOPF is introduced as a dispatch-aware proxy candidate to better align proxy ranking with ACOPF truth behavior than pure PF-only proxy choices in operating-point-sensitive cases.
