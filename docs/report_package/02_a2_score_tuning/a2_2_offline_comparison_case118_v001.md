# A2.2 Offline Comparison v001

## 1. Purpose

- A2.1 reached ceiling behavior at `K_initial=200, tail_audit=50` on validation per-lop view.
- A2.2 compares three next directions: A2.2a guard tuning, A2.2b failed-state severity tie-break, A2.2c DA-stage readiness audit.

## 2. A2.2a Result

- best score/config: `raw_success_fail`, `K_initial=200`, `tail_audit=25`, `expand_factor=1.25`
- pass_all_lops: `True`
- mean_l0_truth_calls: `225.0`
- max_K_final: `200`

## 3. A2.2b Result

- best score/config: `raw_success_fail`, `K_initial=200`, `tail_audit=25`, `expand_factor=1.5`
- pass_all_lops: `True`
- mean_l0_truth_calls: `225.0`
- max_K_final: `200`

## 4. A2.2c Result

### Current DA Data Availability

- current final_guard CSV/JSON is run-level summary only
- available: pf_hat / truth_calls / proxy_calls / acceptance_rate / reverse_proxy_rejects / l0 metadata / level acceptance summary
- missing proposal-level required fields: `20`

### Consequence

- current final_guard outputs are insufficient for DA-stage score analysis
- no per-proposal proxy/truth trajectory is available
- DA-side score training or DA gate redesign cannot be evaluated yet
- disabled-by-default instrumentation is required before DA-side changes

### Recommended Minimal Instrumentation

- disabled-by-default flag: `--da-trace-enabled` or `da_trace_enabled: false`
- required fields include proposal_id/level/current-vs-proposal proxy+truth scores/stage1+final accepts/reverse_proxy_reject/timing
- instrumentation must be logging-only and must not alter DA decisions or RNG state

## 5. Recommended Next Step

- `hold_A2_and_keep_raw_failure_label_guard`
- rationale: A2.2a is already saturated and A2.2b does not provide practical gain

## 6. Relation to Literature

- Taheri & Molzahn optimize DC approximation parameters using AC/ACOPF teacher data.
- This A2.2 comparison remains score/guard parameter training.
- A4 is the later stage closer to formulation-level coefficient/bias optimization.