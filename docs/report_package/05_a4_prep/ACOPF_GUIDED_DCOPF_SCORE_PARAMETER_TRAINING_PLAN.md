# ACOPF-Guided DCOPF Score Parameter Training Plan

## 0. Purpose

This document defines the A2 plan: move from A1-Guard objective alignment to ACOPF-guided DCOPF score-parameter training.

The immediate goal is not to change MATPOWER physics or DA logic. The goal is to train a DCOPF-derived `l0_score` that better ranks ACOPF failure risk while keeping the Level-0 guard objective fixed on ACOPF failure membership.

## 1. Relationship to Prior DC Parameter Optimization Literature

- Taheri & Molzahn’s DCOPF parameter optimization tunes coefficient and bias parameters using ACOPF teacher solutions.
- The paper’s target is improving DCOPF generator setpoint accuracy relative to ACOPF.
- Their related DCPF work optimizes coefficient and bias parameters so DC power-flow outputs better match AC power-flow results.
- Our target differs: we train DCOPF-derived parameters for ACOPF failure screening and truth-call reduction.
- Therefore our loss is not dispatch error; it is screening loss.

## 2. Why A1-Guard Comes Before A2

- Under legacy guard, even a good failure detector can be forced to `K=N` because the guard protects ACOPF `s_any` ranking.
- A1-Guard aligns the evaluation objective with ACOPF failure membership.
- Without this alignment, A2-trained DCOPF scores could be incorrectly judged by the wrong guard target.
- Therefore A1-Guard is the necessary evaluation scaffold for A2.

## 3. A2 Definition

A2: ACOPF-guided DCOPF score-parameter training.

Purpose:
- Train physically interpretable DCOPF-derived score parameters from ACOPF failure labels.

Not:
- Not black-box ML surrogate.
- Not immediate formulation-level DCOPF modification.
- Not replacing ACOPF truth.

Inputs:
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- `ac_ext/experiments/out/ml_training_data_case118.csv`

Outputs:
- `ac_ext/experiments/out/dcopf_score_params_case118_v001.json`
- `ac_ext/experiments/out/dcopf_score_training_results_case118_v001.csv`
- `ac_ext/experiments/out/dcopf_score_training_report_case118_v001.md`

Candidate score:

```text
if dcopf_failed:
    l0_score = high_risk
else:
    l0_score = max_j(alpha_j * abs(PF_ij) / L_j + beta_j)
```

or first simpler version:

```text
if dcopf_failed:
    l0_score = high_risk
else:
    l0_score = max_j(abs(PF_ij) / learned_limit_j - 1)
```

Trainable parameters:
- global margin
- percentile `q`
- epsilon floor
- branch pseudo-limits `L_j`
- optional branch weights `alpha_j`
- optional branch bias `beta_j`
- failure penalty / high-risk score

Training split:
- train seeds: `7`, `42`, `100`, `200`
- validation seed: `300`
- unseen benchmark seeds: `901`, `902`, `903`

Loss / selection criteria:
Primary:
- minimize failure-label guard `K_final`
- minimize `l0_truth_calls`
- keep `tail_audit_failure_hits = 0` where possible

Secondary:
- maximize Top-K ACOPF failure recall
- maximize AUPRC
- preserve `pf_hat` after online benchmark

## 4. Roadmap After A2

A2.1 Offline score-level training
- train score parameters from PF/PT and ACOPF labels
- no controller integration yet

A2.2 Offline validation
- compare raw_success_fail, pseudo-limit, trained score
- validation seed=`300`
- per-lop breakdown

A3 Wrapper-level online proxy
- implement `proxy_mode="dcopf_optimized"`
- returns `l0_score`, `da_score`, `flow_score`, `fail_proxy`
- raw `proxy_mode="dcopf"` remains unchanged
- Level-0 reads `l0_score`
- DA initially remains raw DCOPF

A4 Formulation-level optimization
- closer to Taheri & Molzahn
- tune DC coefficient / injection-bias / flow-bias parameters
- only after A2/A3 demonstrate benefit
- screening loss replaces dispatch loss

C ML-calibrated DCOPF
- damage state + DCOPF flow features + trained DCOPF score
- output calibrated ACOPF failure risk
- benchmark against strong A1/A2 DCOPF baseline

## 5. Input Artifacts

Required artifacts:
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- `ac_ext/experiments/out/ml_training_data_case118.csv`

Derived alignment assumptions:
- `sample_id` must align between the NPZ and ACOPF label table
- failed DCOPF solves must be treated as high risk, not low-flow samples

## 6. Training Target

Target task:
- train DCOPF-derived `l0_score` parameters using ACOPF failure labels

Core label:
- `acopf_fail_label = (not acopf_success) or isinf(acopf_s_any)`

Primary use case:
- Level-0 top-K screening under `failure_label` guard

## 7. Candidate Score Family

Baseline rule:

```text
if dcopf_failed:
    l0_score = high_risk_penalty
else:
    l0_score = max_j(alpha_j * abs(PF_ij) / limit_j + beta_j)
```

Notes:
- `PF_ij` comes from branch-level DCOPF flow artifact
- `limit_j` is a train-derived pseudo-limit or calibrated branch limit
- `alpha_j` and `beta_j` may be branch-specific, grouped, or global

Practical first version:
- start with grouped or global parameters, not fully free branchwise parameters
- only move to branchwise `alpha_j` if validation shows clear underfitting

## 8. Train / Validation / Benchmark Split

Training seeds:
- `7`
- `42`
- `100`
- `200`

Validation seed:
- `300`

Unseen benchmark seeds:
- `901`
- `902`
- `903`

Rules:
- unseen benchmark seeds must not be used during parameter fitting
- seed `300` is for offline model/score selection, not final claims
- seeds `901-903` remain the frozen out-of-sample benchmark slice

## 9. Objectives

Primary objectives:
- minimize failure-label guard expansion
- reduce `l0_truth_calls`
- keep `tail_audit_failure_hits = 0` where possible

Supporting offline metrics:
- Top-K ACOPF failure recall
- Top-50 / Top-100 / Top-200 failure recall
- precision at K
- failure-label guard pass rate
- simulated `K_final`
- simulated `l0_truth_calls`
- AUPRC

Online benchmark metrics after promotion:
- `truth_calls`
- `l0_truth_calls`
- `l0_prescreen_K_final`
- `pf_hat`

## 10. Validation Logic

Offline validation must be guard-aware.

For each candidate score:
- rank samples by candidate `l0_score`
- simulate failure-label Level-0 guard
- measure whether final `K` remains close to `K_initial`
- reject any candidate that improves classifier metrics but still expands `K` materially

This is the key difference from generic classifier training:
- the target is not generic AUROC optimization
- the target is useful top-K failure screening inside the actual controller regime

## 11. Expected Outputs

Artifacts to produce after A2 implementation:
- `ac_ext/experiments/out/dcopf_score_params_case118_v001.json`
- `ac_ext/experiments/out/dcopf_score_training_results_case118_v001.csv`
- `ac_ext/experiments/out/dcopf_score_training_report_case118_v001.md`

The JSON parameter file should contain:
- pseudo-limit definition
- parameter values
- training seeds
- validation seed
- score version string
- score formula metadata

## 12. Next Implementation Scripts

Planned scripts:
- `train_dcopf_score_parameters.py`
- `evaluate_trained_dcopf_score.py`

Responsibilities:
- `train_dcopf_score_parameters.py`
- load NPZ + ACOPF labels
- estimate pseudo-limits on train split only
- fit score parameters
- write `dcopf_score_params_case118_v001.json`

- `evaluate_trained_dcopf_score.py`
- load trained parameter JSON
- run offline evaluation on validation and benchmark splits
- report recall / guard simulation / truth-call implications

## 13. Promotion Rule

Do not add `proxy_mode="dcopf_optimized"` immediately.

Promotion sequence:
1. train and validate score parameters offline
2. show improvement over raw DCOPF on validation seed `300`
3. verify no regression on unseen seeds `901-903`
4. only then expose `proxy_mode="dcopf_optimized"` in controller benchmark code

## 14. Scope Boundary

A2 is score-parameter training, not a MATPOWER rewrite.

In scope:
- pseudo-limits
- calibrated DCOPF-derived flow score
- parameter JSON artifact
- controller-facing `l0_score` design

Out of scope for the first A2 pass:
- changing raw DCOPF solver formulation
- changing DA logic
- changing ACOPF truth definition
- changing failure-label guard semantics again

## 15. Summary

A1-Guard established the correct Level-0 screening objective.

A2 should now train a DCOPF-derived continuous `l0_score` against ACOPF failure labels, using:
- `dcopf_flow_features_case118.npz`
- `ml_training_data_case118.csv`

The success criterion is not just a better offline score. It is a score that, under failure-label guard, keeps `K` small, reduces `l0_truth_calls`, and preserves `pf_hat` on unseen benchmark seeds.

## 16. A2.2 Offline Comparison Outcome (v001)

A2.2 compared three directions on validation seed `300` with per-lop failure-label guard simulation:
- A2.2a: guard parameter calibration
- A2.2b: failed-state severity tie-breaking
- A2.2c: DA-stage diagnostic readiness audit

Observed outcome:
- best A2.2a config remained `raw_success_fail` with `K_initial=200`, `tail_audit=25`
- no configuration with `K_initial < 200` passed all lops
- A2.2b severity tie-breakers did not beat `raw_success_fail`
- A2.2c confirmed current `final_guard_*` outputs are run-level only and do not contain proposal-level DA trajectory

Implication:
- A2 score/guard tuning appears saturated under current artifacts
- DA-side score training and DA gate redesign are not readiness-complete without proposal-level trace instrumentation

Readiness gate before any DA-side optimization:
- add disabled-by-default DA trace logging (proposal-level rows)
- keep DA decision logic unchanged
- verify logging-only overhead on debug-scale runs first

## 17. DA Trace and A4-Prep Handoff

The next active track is split in two:

- DA trace instrumentation
- A4 formulation-prep offline design

DA trace comes first for any DA-side learning question because current
`final_guard_*` outputs only contain run-level summaries. Without proposal-level
records, DA score training is not identifiable.

A4-prep then uses the Taheri & Molzahn structure more directly:

- training scenarios
- ACOPF teacher outputs
- parameterized lower-level DCOPF behavior
- screening loss
- sensitivity path
- quasi-Newton optimizer

See:

- `A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md`

## 18. Closure of A2 Simple Score Tuning

A2.1 and A2.2 establish a practical boundary for simple scalar score tuning:

- `raw_success_fail` remains best overall under the failure-label guard selection logic
- simple pseudo-limit and base/hybrid scalar variants do not beat raw
- further `margin/q/epsilon` expansion is not recommended as the primary next method step

Therefore, the next high-value path is:

- certificate audit of `DCOPF failed => ACOPF failed`
- DA trace analysis
- A4 formulation-prep with sensitivity-aware parameterization
