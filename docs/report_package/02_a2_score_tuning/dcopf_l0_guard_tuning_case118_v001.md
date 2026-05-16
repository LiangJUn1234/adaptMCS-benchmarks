# A2.2a Guard Parameter Tuning

- eval seeds: `300`
- train seeds (for trained score reconstruction): `7,42,100,200`
- candidates: `raw_success_fail, base_margin_m1.2_e10, base_margin_m1.2_e20, base_margin_m1.2_e5`
- total grid rows: `240`
- pass_all_lops rows: `48`

## Best Configuration

- score: `raw_success_fail` (raw_success_fail)
- K_initial: `200`
- tail_audit: `25`
- expand_factor: `1.25`
- pass_all_lops: `True`
- mean_l0_truth_calls: `225.0`
- max_K_final: `200`
- max_tail_audit_failure_hits: `0`
- mean_top100_recall: `0.7983897196733317`
- mean_top200_recall: `1.0`
