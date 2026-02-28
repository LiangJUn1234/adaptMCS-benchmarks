# Phase 4 Integration Memo: Phase-5 Baseline Host Decision

## Scope and Constraints
- Phase 4 is review/freeze only. No baseline, MCS, aE-SuS, DA-MCMC, or bulk experiment implementation.
- Legacy algorithm logic must not be modified.
- MATLAB wrappers remain default source of truth for scalar scores (`success`, `s_line`, `s_volt`, `s_any`).
- Important test caveat: MATPOWER built-in `case14` frequently has `RATE_A = 0` on many branches; therefore `s_line = -Inf` is expected and not a bug. Phase 5+ line-limit studies must use PGLib cases.

## Decision
**Recommended Phase-5 host: (C) thin new baseline loop inside `ac_ext`.**

Rationale:
- Matches current architecture: Python-side discrete state sampling/application and MATLAB-side scalar truth computation are already established in `ac_ext`.
- Minimizes IPC payload and integration risk by passing small state payloads + scalar returns rather than large trajectories.
- Preserves optional future adapter paths to A/B without forcing either legacy framework into early ownership.
- Cleanest insertion point for later MF-DA components as explicit extension points.

## Option Comparison

### (A) MATLAB aE-SuS host (`aE_SuS_EC.m`)
Pros:
- Native MATLAB execution loop can reduce Python↔MATLAB crossing if everything is ported into MATLAB.
- Existing adaptive-chain machinery already available.

Required changes for use as Phase-5 host:
- New MATLAB adapter layer to map discrete damage states into aE-SuS expected latent-space samples.
- MATLAB-side random model and state bookkeeping reimplementation (line/gen/bus damage schema).
- MATLAB wrapper glue to preserve scalar-score contract and failure semantics used by `ac_ext`.

IPC/performance implications:
- If Python orchestrates while MATLAB hosts loop: many cross-language callbacks for per-sample evaluation unless loop fully migrated.
- If loop fully migrated to MATLAB: lower IPC count, but larger one-time porting burden and less Python-side observability.

Discrete-state compatibility:
- Possible but unnatural in current `aE_SuS_EC` shape (designed around continuous normal-space proposals and LSF callbacks).
- Requires substantial semantic adaptation for discrete outages/derating.

MF-DA compatibility:
- Feasible but would require additional MATLAB-side surrogate layers and calibration interfaces.

Why not selected now:
- Highest adaptation risk and migration cost for discrete-state semantics.
- Would force early commitment to MATLAB-centric orchestration before interfaces stabilize.

### (B) Python rips host (`PIMs/python code/rips/rare_events/*`)
Pros:
- Python-native orchestration aligns with current `ac_ext` control layer.
- Existing rare-event infrastructure and particle abstractions.

Required changes for use as Phase-5 host:
- Thin adapter from `ac_ext` state schema to rips particle/FK abstractions.
- Custom kernels/transition logic for discrete line/gen/bus state moves.
- Bridging layer for MATLAB scalar calls with strict payload minimization.

IPC/performance implications:
- Potentially very high MATLAB call count (per particle per level/transition).
- Payload size can stay small if only state payload in / scalar out, but call overhead remains dominant.

Discrete-state compatibility:
- Framework supports generic particles, but existing defaults/kernels are not discrete damage-state aware.
- Non-trivial adapter + kernel work required before trustworthy baseline behavior.

MF-DA compatibility:
- Good long-term fit, but only after stable discrete kernel and truth/proxy bridge are in place.

Why not selected now:
- Medium-to-high integration effort before first reliable baseline.
- Risk of conflating framework adaptation with algorithm validation in Phase 5.

### (C) Thin new baseline loop inside `ac_ext`
Pros:
- Lowest integration risk and fastest path to a controlled baseline.
- Uses existing `sample_X`/`apply_state` boundaries and MATLAB scalar wrappers directly.
- Keeps payload minimal and contracts explicit.

Required changes for use as Phase-5 host:
- Add a small `ac_ext` baseline runner that iterates discrete states and aggregates scalar outcomes.
- Keep loop intentionally narrow (single-host baseline only), no DA-MCMC or advanced samplers.
- Add logging/telemetry around call counts and failure outcomes.

IPC/performance implications:
- MATLAB call count is explicit and easy to model: approximately one solver call per case-mode evaluation per state.
- Payload size remains minimal: JSON-like damage state + 4 scalar outputs.
- No large bus/branch arrays in default path.

Discrete-state compatibility:
- Native fit with current schema (`line_out`, `bus_out`, `gen_derate_state`, `gen_scale`).
- Conservative bus-outage semantics already frozen in MATLAB apply-state helper.

MF-DA compatibility:
- Strong: straightforward to add optional proxy path and delayed truth calls later.
- Clear insertion points for multifidelity gating and acceptance logic.

Why selected:
- Best balance of delivery speed, correctness, and future extensibility with minimal architectural churn.

## Rejection Summary
- Reject (A) now: excessive adaptation of continuous-space MATLAB aE-SuS to discrete outage states.
- Reject (B) now: framework adaptation + discrete kernel design overhead too high for immediate baseline freeze.
- Select (C): narrow controlled baseline loop in `ac_ext`, preserving existing contracts and enabling phased growth.

## Phase-5 Plan (Concrete)
1. Implement one thin baseline loop in `ac_ext` only (no legacy edits).
2. Consume frozen `state schema v1` and `apply_state` semantics from `interface_freeze.md`.
3. Keep default evaluation path scalar-only via MATLAB wrappers.
4. Record solver call counts and basic timing to quantify IPC overhead.
5. Validate on built-in `case14` for smoke only; use PGLib for any line-limit conclusions.
