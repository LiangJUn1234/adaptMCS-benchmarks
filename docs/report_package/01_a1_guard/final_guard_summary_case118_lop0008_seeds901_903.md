# A1-Guard Freeze Summary

Benchmark slice:
- `case118`
- `N=1000`
- `line_outage_prob=0.008`
- `seeds=901, 902, 903`
- clean arms only: `truth_only`, `corrected_da_dcopf`
- guard comparison: `legacy_truth_score` vs `failure_label`

## Per-seed corrected_da_dcopf comparison

| seed | legacy pf_hat | failure_label pf_hat | legacy truth_calls | failure_label truth_calls | truth-call saving | legacy l0_truth_calls | failure_label l0_truth_calls | legacy K_final | failure_label K_final |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 901 | 0.06825 | 0.06825 | 1269 | 532 | 737 | 1000 | 250 | 1000 | 200 |
| 902 | 0.08085 | 0.08085 | 1325 | 585 | 740 | 1000 | 250 | 1000 | 200 |
| 903 | 0.08925 | 0.08925 | 1366 | 614 | 752 | 1000 | 250 | 1000 | 200 |

## Aggregate statistics

| metric | truth_only | legacy_truth_score | failure_label |
| --- | ---: | ---: | ---: |
| pf_hat mean | 0.07950 | 0.07945 | 0.07945 |
| pf_hat std | 0.01035 | 0.01057 | 0.01057 |
| truth_calls mean | 1850.0 | 1320.0 | 577.0 |
| truth_calls std | 0.0 | 48.69 | 41.58 |
| l0_truth_calls mean | not_applicable | 1000.0 | 250.0 |
| K_final mean | not_applicable | 1000.0 | 200.0 |
| l0_tail_audit_failure_hits mean | not_applicable | 0.0 | 0.0 |

## Savings

- `legacy_truth_score -> failure_label`:
- mean truth-call saving = `743.0`
- mean relative saving = `56.33%`

- `truth_only -> failure_label`:
- mean truth-call saving = `1273.0`
- mean relative saving = `68.81%`

## Interpretation

- For `corrected_da_dcopf`, `failure_label` preserves the same per-seed `pf_hat` values as `legacy_truth_score`: `[0.06825, 0.08085, 0.08925]`.
- The improvement comes from controller semantics, not from changing DCOPF physics or DA scoring.
- Mean `truth_calls` drops from `1320.0` to `577.0`.
- Mean `l0_truth_calls` drops from `1000.0` to `250.0`.
- Mean `K_final` drops from `1000.0` to `200.0`.
- Mean `l0_tail_audit_failure_hits` remains `0.0` under `failure_label`, consistent with the guard objective: no missed ACOPF failures were observed in the audited tail.
- This freeze establishes A1-Guard as an objective-alignment result. The next stage is A2: ACOPF-guided DCOPF score-parameter training on top of the now-correct Level-0 objective.
