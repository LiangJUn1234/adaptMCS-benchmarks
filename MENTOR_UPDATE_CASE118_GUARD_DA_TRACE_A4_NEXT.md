# Mentor Update: Case118 ACOPF Truth-Call Reduction via DCOPF Screening

## 1. One-sentence summary

The initial bottleneck was primarily an objective mismatch in Level-0 guard semantics rather than failure detection weakness; after aligning guard semantics to ACOPF failure membership, truth calls dropped substantially without changing `pf_hat`, and DA trace indicates remaining DA truth calls mainly confirm DCOPF-failed proposals.

## 2. Problem

- ACOPF truth calls are expensive.
- Rare-event screening must reduce truth calls without missing ACOPF failures.
- Early DCOPF proxy behavior appeared conservative/inefficient under the legacy guard objective.

## 3. A1-Guard Result

| Setting | mean truth_calls | mean l0_truth_calls | mean K_final | mean pf_hat |
|---|---:|---:|---:|---:|
| `legacy_truth_score` | 1320 | 1000 | 1000 | 0.07945 |
| `failure_label` | 577 | 250 | 200 | 0.07945 |

Context:

- case118
- `N=1000`
- `line_outage_prob=0.008`
- seeds `901,902,903`

## 4. A2 Score-Tuning Boundary

- `raw_success_fail` remained best overall.
- pseudo-limit/base-margin/hybrid did not beat raw baseline.
- `K_initial < 200` was not safe across all validation lops.
- `tail_audit` can be reduced (`50 -> 25`) to reduce overhead.
- simple failed-state severity tie-breakers did not improve over raw baseline.

## 5. DA Trace Result

Trace run:

- case118, `N=1000`, seed `901`, `lop=0.008`
- arm: `corrected_da_dcopf`
- guard: `failure_label`

Observed:

- total DA proposals: `850`
- `stage1_accept`: `282`
- `truth_evaluated`: `282`
- `final_accept`: `192`
- `reverse_proxy_reject`: `25`
- truth-evaluated ACOPF failed: `282`
- truth-evaluated ACOPF safe: `0`

Interpretation:

- remaining DA truth calls in this trace are confirmation calls for DCOPF-failed proposals.

## 6. Certificate Audit

From `dcopf_failure_certificate_audit_case118_v001` on case118 training/validation artifact (`30000` rows):

- `dcopf_failed_count`: `3770`
- `acopf_failed_count`: `3790`
- `true_certificate_count`: `3763`
- `false_certificate_count`: `7`
- `P(ACOPF fail | DCOPF fail)`: `0.998143`
- Wilson 95% CI: `[0.996172, 0.999100]`
- `false_certificate_rate`: `0.001857`
- `missed_failure_rate`: `0.007124`

Important nonzero false-certificate regimes:

- seed `7`, lop `0.005`: false `1/53`
- seed `7`, lop `0.008`: false `1/82`
- seed `7`, lop `0.011`: false `1/117`
- seed `7`, lop `0.014`: false `1/154`
- seed `200`, lop `0.014`: false `1/139`
- seed `200`, lop `0.020`: false `2/209`

Interpretation:

- precision is high, but not perfect; this supports a controlled certificate study, not an unconditional shortcut claim.

## 7. Literature Positioning

- Taheri & Molzahn motivate offline AC/ACOPF-guided optimization of DC/DCPF/DCOPF parameters (coefficient/bias tuning with sensitivity-aware optimization).
- Our project objective differs: screening quality and truth-call reduction, not dispatch-error minimization.
- Contingency-screening logic supports failure-preserving filtering.
- AC-feasibility literature warns against treating DCOPF as ACOPF-equivalent without audit.

## 8. Next Step

- complete certificate-aware regime map (already started; extend as needed across additional seeds/lops/cases)
- if certificate precision remains sufficiently high in selected regimes: design controlled `certified_dcopf_failure_shortcut` experiment
- if not sufficiently robust: prioritize A4 grouped parameterization + finite-difference sensitivity prep
- avoid continued scalar pseudo-limit grid expansion as primary effort

## 9. Questions for Mentor

1. Is a controlled certificate route acceptable as an intermediate screening shortcut study?
2. Should the next method milestone prioritize certificate validation breadth or formulation-level parameterization depth?
3. What failure tolerance is acceptable for screening shortcuts (e.g., max false-certificate rate)?
4. Should we extend to another MATPOWER case before deeper A4 optimization?
5. Should DA trace be expanded to more seeds/lops first, or only after certificate gating criteria are agreed?
6. Is the near-term target a conference-style methods contribution or an internal benchmark hardening phase first?
