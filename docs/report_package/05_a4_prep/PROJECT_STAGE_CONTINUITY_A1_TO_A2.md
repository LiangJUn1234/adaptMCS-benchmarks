# From A1-Guard to A2 ACOPF-Guided DCOPF Score Training

## Current Stage

The project has completed A1-Guard freeze.

Current state:
- Level-0 evaluation objective is now aligned with ACOPF failure membership
- clean freeze results exist for `case118`, `N=1000`, `line_outage_prob=0.008`, `seeds=901,902,903`
- A2 score-parameter training is the next method step

## What Has Been Proven

- Under `corrected_da_dcopf`, `failure_label` preserves the same mean `pf_hat` as legacy guard: `0.07945`
- Mean `truth_calls` drops from `1320` to `577`
- Mean `l0_truth_calls` drops from `1000` to `250`
- Mean `K_final` drops from `1000` to `200`
- Mean `l0_tail_audit_failure_hits` remains `0`

Interpretation:
- raw DCOPF became a much stronger truth-call reduction proxy once the guard objective matched the rare-event screening objective

## What Has Not Been Proven

- We have not yet trained optimized DCOPF score parameters
- We have not yet trained branch pseudo-limits or coefficient/bias parameters
- We have not yet implemented `proxy_mode="dcopf_optimized"`
- We have not yet shown wrapper-level or formulation-level optimized DCOPF beats raw DCOPF online

## Why A1-Guard Is Necessary

A1-Guard is not the final optimization method.

It is necessary because:
- the legacy Level-0 guard protected ACOPF `s_any` rank threshold
- the rare-event screening task needs to protect ACOPF failure membership
- without that correction, even a strong failure detector could still be forced to `K=N`

Therefore A1 provides the evaluation scaffold that makes downstream DCOPF optimization meaningful.

## Why A2 Is the Next Method Step

A2 is the first stage that actually trains DCOPF-derived score parameters from ACOPF teacher data.

That is the correct next move because:
- A1 solved the controller-objective mismatch
- A2 can now optimize the DCOPF-derived screening score itself
- the next gain should come from better continuous top-K failure ranking, not more guard patching

## How This Relates to Taheri & Molzahn

Taheri & Molzahn’s core idea is that DC / DCOPF approximation parameters should not remain fixed:
- AC / ACOPF results provide teacher information
- DC coefficient and bias parameters can be optimized offline
- optimized parameters are then used online

Their target:
- dispatch / flow approximation accuracy relative to ACOPF or ACPF

Our translation:
- optimize DCOPF-derived score parameters for ACOPF failure screening and truth-call reduction
- use screening loss rather than dispatch-error loss

So A2 is the project stage where the literature connection becomes operational.

## Read First

1. `DCOPF_IMPLEMENTATION_AND_DIAGNOSTIC_REPORT.md`
2. `ac_ext/experiments/out/final_guard_summary_case118_lop0008_seeds901_903.md`
3. `ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md`
4. `DCOPF_OPTIMIZED_SCORE_CONTRACT_AND_EXECUTION_PLAN.md`
5. `PROJECT_STAGE_CONTINUITY_A1_TO_A2.md`

## Do Not Delete

- `ac_ext/experiments/out/final_guard_summary_case118_lop0008_seeds901_903.md`
- `ac_ext/experiments/out/final_guard_summary_case118_lop0008_seeds901_903.csv`
- `ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md`
- `PROJECT_STAGE_CONTINUITY_A1_TO_A2.md`
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- `ac_ext/experiments/out/ml_training_data_case118.csv`
- `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`

## Immediate Next Implementation Scripts

- `train_dcopf_score_parameters.py`
- `evaluate_trained_dcopf_score.py`

These should be implemented next, but they are not part of this documentation task.

## Current Stage Update (A1/A2/DA Closure Before A4)

The project stage has moved from pure A2 setup to A1/A2/DA closure before A4:

- A1 guard objective alignment is frozen
- A2 simple score tuning boundary is established
- DA proposal-level trace instrumentation and first trace analysis are available
- certificate audit is now an explicit gate for any shortcut claim

Next reading order:

1. `ac_ext/experiments/out/dcopf_failure_certificate_audit_case118_v001.md`
2. `ac_ext/experiments/out/da_trace_analysis_case118_N1000_seed901_v001.md`
3. `A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md`
4. `ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md`
