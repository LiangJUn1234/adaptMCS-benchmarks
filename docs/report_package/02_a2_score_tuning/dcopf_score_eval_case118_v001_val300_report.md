# A2 DCOPF Score Evaluation

- params: `ac_ext/experiments/out/dcopf_score_params_case118_v001.json`
- eval seeds: `300`
- note: if multiple line-outage probabilities are mixed in one eval split, the global failure-label guard row is a pooled diagnostic only.
- the per-lop rows are the benchmark-relevant view for Level-0 screening.

## Candidates

### raw_success_fail
- method family: `raw_success_fail`
- AUROC: `1.0000`
- AUPRC: `1.0000`
- top200_recall: `0.2751`
- K_final: `6000`
- l0_truth_calls: `6000`
- tail_audit_failure_hits: `200`

### base_margin_m1.2_e10
- method family: `base_margin`
- AUROC: `1.0000`
- AUPRC: `1.0000`
- top200_recall: `0.2751`
- K_final: `6000`
- l0_truth_calls: `6000`
- tail_audit_failure_hits: `200`
