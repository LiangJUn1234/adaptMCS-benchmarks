# Proxy Selection Recommendation

## Current Status
- DCPF and FDXB are both fully operational in the unified Phase-5 proxy evaluation pipeline.
- Both proxies now support damaged-case evaluation and return the same minimal scalar schema as truth:
  - success
  - s_line
  - s_volt
  - s_any

## Diagnostics Basis
Diagnostics were run under the following setup:
- case: case14
- truth: acopf
- N: 200
- seed: 1
- line_outage_prob = 0.01
- bus_outage_prob = 0.0

### DCPF summary
- Pearson(s_any): ~0
- Spearman(s_any): null
- top-10% Jaccard: 0.2121
- overlap: 7 / 20

### FDXB summary
- Pearson(s_any): 0.1006
- Spearman(s_any): 0.1209
- top-10% Jaccard: 0.2121
- overlap: 7 / 20

## Default Stage-1 Proxy Decision
**Recommendation: use FDXB as the provisional default Stage-1 proxy.**

## Rationale
1. FDXB preserves weak but nonzero correlation with truth, while DCPF is effectively constant over most finite samples.
2. FDXB yields a defined Spearman rank correlation, whereas DCPF does not provide meaningful rank resolution in the current setup.
3. Although both proxies have the same top-10% overlap under this case, FDXB carries more usable ordering information for screening.

## Why DCPF is not the Default
- DCPF is still useful as a baseline/debug proxy.
- However, under the current case14/acopf/light-damage configuration, its proxy scores collapse to a near-single value and therefore provide almost no ranking signal.
- That makes it a poor default choice for Stage-1 screening in later DA-style workflows.

## Limitations
- The current recommendation is based on case14, which is a small system and not ideal for strong line-limit discrimination.
- Both proxies are weak under this setup, so the decision should be treated as provisional.
- Before Phase 6 is finalized, the same diagnostics should be repeated on at least one more realistic case (preferably a PGLib-style case with meaningful branch limits and richer operating behavior).

## Phase-6 Implication
- If development proceeds immediately, FDXB should be wired in as the default Stage-1 proxy.
- DCPF should remain available for comparison, debugging, and sanity checks.
