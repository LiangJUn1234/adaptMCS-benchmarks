# A4 ACOPF-Guided DCOPF Formulation Prep Plan

## 1. Purpose

A4 is the first stage that is structurally close to Taheri & Molzahn.

It is not another score-grid search. Its purpose is to build an offline
teacher-driven parameter optimization loop:

- training scenarios representative of online use
- ACOPF teacher outputs
- parameterized DC/DCOPF lower-level outputs
- screening loss
- parameter sensitivities or usable gradient surrogates
- offline optimizer
- online fixed parameters

In this project, the target is not dispatch accuracy. The target is
rare-event screening quality:

- preserve ACOPF failure membership in top-K
- reduce Level-0 truth calls
- reduce total truth calls after delayed acceptance
- preserve benchmark `pf_hat`

## 2. Why A4 Comes After A1 and A2

A1-Guard established the correct evaluation target for Level-0:

- legacy guard protected ACOPF `s_any` ranking
- failure-label guard protects ACOPF failure membership

A2.1 and A2.2 then showed:

- raw DCOPF success/fail is already a strong Level-0 signal
- simple pseudo-limit score tuning saturates quickly
- failed-state tie-breaking does not improve the current best baseline

That means the next method step should not be another shallow score family.
The next step should move toward parameterized DCOPF behavior, guided by ACOPF
teacher data.

## 3. Relation to Taheri & Molzahn

Taheri & Molzahn optimize DC/DCPF/DCOPF parameters using AC/ACOPF teacher
solutions. Their structure is the key reference:

- offline training scenarios
- AC/ACOPF teacher outputs
- parameterized lower-level DC or DCOPF model
- loss as a function of those parameters
- sensitivities / gradients
- quasi-Newton optimization such as BFGS, L-BFGS-B, or TNC
- online use of fixed optimized parameters

What carries over directly:

- training scenarios must match deployment conditions
- parameters should be optimized offline
- optimization needs a task loss and sensitivity path

What changes in this project:

- their loss is dispatch / flow approximation accuracy
- our loss must be screening loss and truth-call reduction loss

## 4. Required Inputs

Current artifacts already available:

- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- `ac_ext/experiments/out/ml_training_data_case118.csv`
- `ac_ext/experiments/out/dcopf_score_params_case118_v001.json`
- `ac_ext/experiments/out/a2_2_offline_comparison_case118_v001.json`

Required additional artifact before DA-side work:

- disabled-by-default proposal-level DA trace

The DA trace must capture, per proposal:

- `run_id`
- `arm_name`
- `seed`
- `level`
- `proposal_index`
- `proxy_mode`
- `l0_guard_mode`
- `proxy_score_proposal`
- `proxy_score_current` when available
- `truth_score_proposal` when evaluated
- `truth_score_current`
- `stage1_accept`
- `final_accept`
- `reverse_proxy_reject`
- `truth_evaluated`
- `proxy_evaluated`
- proxy/truth timing

Optional but useful:

- state hash
- number of outaged lines
- proxy success flag
- future `l0_score`, `da_score`, `flow_score`

## 5. A4 Parameterization Ladder

### A4.1 Grouped score-side coefficients

Offline score only, no new DCOPF solve:

```text
score_i(theta) = max_j alpha_g(j) * abs_flow_ij / L_g(j) + beta_g(j)
```

where branches are grouped by:

- base-flow quantile
- outage frequency
- topology zone if available

This is the lowest-risk bridge from A2 to A4.

### A4.2 Wrapper-level parameterized DCOPF

Still avoid direct MATPOWER source edits. Expose parameters through project-local
wrapper logic:

- branch limit scaling
- global flow bias
- branch-group flow bias
- solver-failure penalty
- optional branch-group pseudo-limits

This requires rerunning DCOPF for parameter candidates.

### A4.3 Formulation-level coefficient / bias optimization

Closest to Taheri & Molzahn:

- susceptance coefficient scaling
- injection bias
- flow bias
- PTDF/Bf/Bbus-like corrections if accessible through wrapper-local MATLAB

This is the first stage where lower-level solution sensitivities become central.

## 6. Loss Definition

The loss must be task-aligned. A candidate A4 loss is:

```text
L(theta) =
  lambda1 * missed_failure_topK(theta)
+ lambda2 * tail_audit_failure_hits(theta)
+ lambda3 * l0_truth_calls(theta)
+ lambda4 * pairwise_rank_loss(theta)
+ lambda5 * da_trace_loss(theta)
+ lambda6 * regularization(theta)
```

Hard benchmark quantities are not smooth, so the optimizer should use smooth
surrogates during training and hard metrics for selection:

- pairwise ranking loss between failure and safe states
- soft top-K recall surrogate
- soft penalty for score separation failures
- regularization toward raw DCOPF parameters

Selection remains hard-metric based:

- per-lop `tail_audit_failure_hits`
- per-lop `K_final`
- `l0_truth_calls`
- later, DA trace rejection quality

## 7. Sensitivity Strategy

### Stage S1: finite-difference sensitivity

Start with low-dimensional grouped parameters and estimate:

```text
dL / dtheta_k ~= (L(theta + eps e_k) - L(theta - eps e_k)) / (2 eps)
```

Use this on:

- global flow scaling
- branch-group scaling
- branch-group bias
- solver-failure penalty

This is the minimum credible path before deriving lower-level sensitivities.

### Stage S2: grouped quasi-Newton optimization

If finite-difference signal is stable:

- optimize grouped parameters with `L-BFGS-B` or `TNC`
- impose conservative bounds
- validate on seed `300`

### Stage S3: lower-level sensitivity / bilevel-style optimization

Only if S1 and S2 show real gain:

- derive sensitivity of lower-level DCOPF outputs to coefficient/bias parameters
- treat the problem as upper-level parameter training over a lower-level DCOPF
- move closer to Taheri & Molzahn’s structure

## 8. Optimizer Plan

Recommended order:

1. `scipy.optimize.minimize(method="L-BFGS-B")`
2. `scipy.optimize.minimize(method="TNC")`
3. only then consider more specialized constrained optimization

Bounds should keep parameters physically interpretable and numerically stable.

## 9. Data Splits

Use the existing split discipline:

- train seeds: `7, 42, 100, 200`
- validation seed: `300`
- unseen benchmark seeds: `901, 902, 903`

Do not use `901-903` for parameter selection.

## 10. Immediate Work Queue

### Track 1: DA trace

Implement and verify disabled-by-default DA trace:

- configuration flag
- per-proposal TSV output
- no decision changes
- debug verification on small runs

### Track 2: grouped A4-prep trainer

Create a new offline trainer for grouped coefficients / biases:

- `train_dcopf_grouped_parameters_v001.py`
- objective based on failure-label screening loss
- low-dimensional grouped parameter vector
- finite-difference sensitivities
- `L-BFGS-B` or `TNC`

### Track 3: A4 readiness report

Compare:

- raw failure-label baseline
- A2 best score baseline
- grouped A4-prep candidate

Promote only if validation improves under hard per-lop guard metrics.

## 11. Promotion Rule

Proceed toward online integration only if offline evidence shows:

- no per-lop guard failure regression
- equal or lower `l0_truth_calls`
- later, evidence that DA-stage scores have usable signal from trace data

Until then:

- keep raw DCOPF + failure-label guard as the benchmark baseline
- keep DA unchanged
- treat A4 as offline method development

## 12. Evidence from A1/A2/DA Trace

Evidence established so far:

- A1 failure-label guard reduced truth calls while preserving `pf_hat`.
- A2.1/A2.2 scalar score tuning saturated:
  - `raw_success_fail` remained best overall
  - pseudo-limit style scores did not beat raw
  - `K_initial < 200` was not safe across all validation lops
  - `tail_audit` can reduce overhead (`50 -> 25`) without changing safety for the validated setting
- DA trace (`N=1000`, `seed=901`, `lop=0.008`) showed all DA truth-evaluated proposals were ACOPF failures.

This means the next decision should be certificate-aware:

- if DCOPF failure behaves as a high-precision empirical certificate across regimes, a controlled shortcut route is plausible
- if not, formulation-prep should focus on separating high-confidence failure from uncertain failure

## 13. Certificate-Aware A4 Branch

### A4 Branch 1: certificate route

Objective:

- verify and safely exploit `DCOPF failure => ACOPF failure` in controlled regimes

Output candidate:

- `certified_dcopf_failure_shortcut` experimental path

Constraint:

- only proceed if false certificate rate is near-zero in validation regimes and remains stable across seeds/lops

### A4 Branch 2: parameterization route

Objective:

- improve DCOPF-derived behavior where the certificate is not reliable enough

Methods:

- grouped coefficient/bias parameterization
- finite-difference sensitivities
- quasi-Newton offline optimization (`L-BFGS-B` / `TNC`)
- later lower-level sensitivity work when warranted

## 14. Do Not Overclaim

Current status must be stated conservatively:

- current results do not prove DCOPF is ACOPF-equivalent
- DCOPF-failure shortcut is not enabled
- A4 formulation-level optimization has not been executed yet
- completed result is A1 + A2 boundary + DA trace readiness and analysis
