# A2.1 DCOPF Score Training Report v001

## 1. Purpose

- A2.1 ACOPF-guided DCOPF score-parameter training.
- Inspired by ACOPF-guided DCOPF parameter optimization literature.
- The target here is failure-screening / truth-call reduction, not dispatch error.

## 2. Data

- NPZ path: `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- truth CSV path: `ac_ext/experiments/out/ml_training_data_case118.csv`
- train seeds: `7,42,100,200`
- validation seeds: `300`
- lops included: `0.005,0.008,0.011,0.014,0.017,0.02`

## 3. Candidate score families

- `raw_success_fail`
- `base_margin`
- `train_percentile`
- `hybrid`

## 4. Selection rule

- failure-label guard metrics are prioritized over AUPRC.
- Selection order:
- minimize validation per-lop max `tail_audit_failure_hits`
- minimize validation per-lop max `K_final`
- minimize validation mean `l0_truth_calls`
- maximize validation mean `top200_recall`
- maximize validation mean `AUPRC`
- prefer lower-complexity score families on ties

## 5. Best overall result

- candidate: `raw_success_fail`
- method family: `raw_success_fail`
- parameters: `dcopf_failed -> +inf`, solved -> `0`
- validation mean AUPRC across lops: `1.0000`
- validation mean top200 recall across lops: `1.0000`
- validation max K_final across lops: `200`
- validation mean l0_truth_calls across lops: `250.0000`

## 6. Best trained physics score

- candidate: `base_margin_m1.2_e10`
- method family: `base_margin`
- parameters: `margin=1.2`, `q=None`, `epsilon=10.0`
- validation mean AUPRC across lops: `1.0000`
- validation mean top200 recall across lops: `1.0000`
- validation max K_final across lops: `200`
- validation mean l0_truth_calls across lops: `250.0000`

## 7. Comparison to raw_success_fail

- `raw_success_fail` remained the best overall candidate on the validation selection rule.
- This should be reported directly rather than forcing a trained score win.
- A1-Guard already makes raw DCOPF very strong, so A2.1 may only match or narrowly trail the raw baseline.

## 8. Per-lop findings

- hardest validation lops under the best trained physics score: `lop=0.019999999552965164` (K_final=200, top100_recall=0.5435, top50_recall=0.2717), `lop=0.017000000923871994` (K_final=200, top100_recall=0.6329, top50_recall=0.3165), `lop=0.014000000432133675` (K_final=200, top100_recall=0.7519, top50_recall=0.3759)
- per-lop guard performance is the primary reason candidates are accepted or rejected

## 9. Next step recommendation

- Do not enter A3 yet. The trained physics score did not beat the raw success/fail baseline on the validation selection rule. The next method step should be branch-weight training or formulation-level coefficient/bias optimization.
