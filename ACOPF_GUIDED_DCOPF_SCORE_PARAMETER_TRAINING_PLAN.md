# ACOPF-Guided DCOPF Score Parameter Training Plan

## 0. Purpose

This document defines the A2 plan: move from A1-Guard objective alignment to ACOPF-guided DCOPF score-parameter training.

The immediate goal is not to change MATPOWER physics or DA logic. The goal is to train a DCOPF-derived `l0_score` that better ranks ACOPF failure risk while keeping the Level-0 guard objective fixed on ACOPF failure membership.

## 1. Why A1-Guard Comes First

A1-Guard was necessary because the previous Level-0 controller objective was misaligned:
- legacy guard protected ACOPF `s_any` rank threshold
- the desired screening objective is ACOPF failure membership

Without fixing that mismatch first, any A2 score training would be confounded:
- a better score could still be forced to `K=N` by the wrong guard objective
- score improvements and controller-objective problems would remain entangled

The freeze result now isolates the problem correctly:
- Level-0 objective alignment is fixed by `failure_label`
- A2 can focus on training a better DCOPF-derived continuous risk score

## 2. Input Artifacts

Required artifacts:
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- `ac_ext/experiments/out/ml_training_data_case118.csv`

Derived alignment assumptions:
- `sample_id` must align between the NPZ and ACOPF label table
- failed DCOPF solves must be treated as high risk, not low-flow samples

## 3. Training Target

Target task:
- train DCOPF-derived `l0_score` parameters using ACOPF failure labels

Core label:
- `acopf_fail_label = (not acopf_success) or isinf(acopf_s_any)`

Primary use case:
- Level-0 top-K screening under `failure_label` guard

## 4. Candidate Score Family

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

## 5. Train / Validation / Benchmark Split

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
- seeds `901–903` remain the frozen out-of-sample benchmark slice

## 6. Objectives

Primary objectives:
- maximize Top-K ACOPF failure recall
- minimize failure-label guard expansion
- reduce `l0_truth_calls`
- preserve `pf_hat`

Supporting offline metrics:
- Top-50 / Top-100 / Top-200 failure recall
- precision at K
- failure-label guard pass rate
- simulated `K_final`
- simulated `l0_truth_calls`

Online benchmark metrics after promotion:
- `truth_calls`
- `l0_truth_calls`
- `l0_prescreen_K_final`
- `pf_hat`

## 7. Validation Logic

Offline validation must be guard-aware.

For each candidate score:
- rank samples by candidate `l0_score`
- simulate failure-label Level-0 guard
- measure whether final `K` remains close to `K_initial`
- reject any candidate that improves classifier metrics but still expands `K` materially

This is the key difference from generic classifier training:
- the target is not generic AUROC optimization
- the target is useful top-K failure screening inside the actual controller regime

## 8. Expected Outputs

Artifacts to produce after A2 implementation:
- `ac_ext/experiments/out/dcopf_score_params_case118_v001.json`
- `ac_ext/experiments/out/trained_dcopf_score_analysis_case118.csv`
- `ac_ext/experiments/out/trained_dcopf_score_analysis_case118.md`

The JSON parameter file should contain:
- pseudo-limit definition
- parameter values
- training seeds
- validation seed
- score version string
- score formula metadata

## 9. Next Implementation Scripts

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

## 10. Promotion Rule

Do not add `proxy_mode="dcopf_optimized"` immediately.

Promotion sequence:
1. train and validate score parameters offline
2. show improvement over raw DCOPF on validation seed `300`
3. verify no regression on unseen seeds `901–903`
4. only then expose `proxy_mode="dcopf_optimized"` in controller benchmark code

## 11. Scope Boundary

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

## 12. Summary

A1-Guard established the correct Level-0 screening objective.

A2 should now train a DCOPF-derived continuous `l0_score` against ACOPF failure labels, using:
- `dcopf_flow_features_case118.npz`
- `ml_training_data_case118.csv`

The success criterion is not just a better offline score. It is a score that, under failure-label guard, keeps `K` small, reduces `l0_truth_calls`, and preserves `pf_hat` on unseen benchmark seeds.
