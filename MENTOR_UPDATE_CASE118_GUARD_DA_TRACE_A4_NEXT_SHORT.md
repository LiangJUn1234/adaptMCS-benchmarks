# Mentor Update (Short): Case118 Guard + DA Trace + A4 Next

- A1 guard alignment produced the main win: under `corrected_da_dcopf`, mean `truth_calls` dropped `1320 -> 577` while mean `pf_hat` stayed `0.07945`.
- A2 simple scalar score tuning saturated: `raw_success_fail` remained best overall; pseudo-limit variants did not beat raw; `K_initial < 200` not safe across all validation lops.
- DA trace (`N=1000`, seed `901`, lop `0.008`) shows remaining DA truth calls are confirmation-heavy: `850` proposals, `282` truth-evaluated, and all `282` are ACOPF failures.
- Certificate audit is high precision but not perfect: `P(ACOPF fail | DCOPF fail)=0.998143`, `false_certificate_count=7`, with nonzero false-certificate regimes in seeds `7` and `200` at selected lops.
- Immediate next step should be certificate-aware A4 prep, not more scalar margin/q/epsilon tuning.

| Comparison | mean truth_calls | mean l0_truth_calls | mean K_final | mean pf_hat |
|---|---:|---:|---:|---:|
| `legacy_truth_score` | 1320 | 1000 | 1000 | 0.07945 |
| `failure_label` | 577 | 250 | 200 | 0.07945 |

Questions for next meeting:

1. Should we pursue a controlled `certified_dcopf_failure_shortcut` study under regime constraints?
2. What false-certificate tolerance is acceptable for screening?
3. Should we expand certificate/trace audits to additional seeds/lops/cases before A4 optimization?
4. If shortcut tolerance is strict, should we prioritize grouped A4 parameterization first?
5. Is near-term priority a publishable methods narrative or internal benchmark hardening?
