# Phase 5 Proxy Diagnostics Results

## Setup
- case: case14
- N: 200
- seed: 1
- truth: acopf
- damage parameters:
  - line_outage_prob = 0.01
  - bus_outage_prob = 0.0

## DCPF
Status: completed

Artifacts:
- ac_ext/experiments/out/diag_dcpf/proxy_diagnostics.csv
- ac_ext/experiments/out/diag_dcpf/truth_vs_proxy_scatter.png
- ac_ext/experiments/out/diag_dcpf/proxy_quantile_truth_mean.png

Summary:
- finite_pair_count: 194 / 200
- Pearson(s_any): 1.3129918688133189e-17
- Spearman(s_any): null
- top-10% Jaccard: 0.21212121212121213
- top-10% overlap: 7 / 20
- top-10% overlap_rate: 0.35

Interpretation:
- DCPF is technically integrated and diagnostics-complete.
- Under the current setup, DCPF proxy scores collapse to an almost constant value (-0.06 for most finite samples).
- This causes essentially zero linear correlation with truth and prevents meaningful rank discrimination.
- DCPF still identifies some of the same extreme failure states as truth through shared +Inf failure outcomes, which explains the nonzero top-10% overlap.

## FDXB
Status: completed

Artifacts:
- ac_ext/experiments/out/diag_fdxb/proxy_diagnostics.csv
- ac_ext/experiments/out/diag_fdxb/truth_vs_proxy_scatter.png
- ac_ext/experiments/out/diag_fdxb/proxy_quantile_truth_mean.png

Summary:
- finite_pair_count: 194 / 200
- Pearson(s_any): 0.10055052057097247
- Spearman(s_any): 0.12086706276182277
- top-10% Jaccard: 0.21212121212121213
- top-10% overlap: 7 / 20
- top-10% overlap_rate: 0.35

Interpretation:
- FDXB is technically integrated and diagnostics-complete.
- Under case14 + acopf truth + light line-outage setting, FDXB shows weak but nonzero proxy alignment.
- Compared with DCPF, FDXB retains slightly more score variation and produces measurable Pearson/Spearman correlation.
- However, the ranking signal is still weak, and proxy scores remain highly compressed across many samples.

## Comparative Conclusion
- FDXB performs better than DCPF under the current diagnostic setup because it preserves at least a small amount of ranking information.
- DCPF behaves mostly like a near-constant proxy and is therefore weaker for Stage-1 screening.
- Neither proxy is strong on case14 under the current setup, so this recommendation should be treated as provisional rather than final.

## Next Action
- Use FDXB as the provisional default proxy for the next round of development.
- Keep DCPF as a baseline/debug proxy.
- Before entering Phase 6 in full, repeat the same diagnostics on at least one PGLib-style case with meaningful line limits and richer operating variation.
