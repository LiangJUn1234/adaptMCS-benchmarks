# A2.2c DA-stage Diagnostic Readiness Audit

## Current DA Data Availability

Current `final_guard_*` CSV/JSON provides run-level summaries only:
- arm-level `pf_hat`
- `truth_calls`
- `proxy_calls`
- `acceptance_rate`
- `reverse_proxy_rejects`
- L0 metadata
- level acceptance summary

Missing proposal-level trajectory fields:
- `run_id`
- `arm_name`
- `seed`
- `level`
- `proposal_index`
- `current_sample_id`
- `proposal_sample_id`
- `proxy_mode`
- `l0_guard_mode`
- `proxy_score_current`
- `proxy_score_proposal`
- `truth_score_current`
- `truth_score_proposal`
- `truth_success_current`
- `truth_success_proposal`
- `truth_failed_current`
- `truth_failed_proposal`
- `stage1_accept`
- `final_accept`
- `reverse_proxy_reject`
- `truth_evaluated`
- `proxy_evaluated`
- `wall_time_proxy`
- `wall_time_truth`

## Consequence

Because proposal-level records are absent:
- cannot estimate whether pseudo-limit score would improve DA-stage rejection
- cannot train `da_score`
- cannot compare DA score scales
- cannot diagnose why upper-level truth calls remain after L0 reduction
- cannot safely modify DA yet

## Recommended Minimal Instrumentation

Introduce disabled-by-default tracing:
- CLI flag: `--da-trace-enabled`
- config field: `da_trace_enabled: false`

When enabled, write one row per DA proposal with required fields:
- `run_id`
- `arm_name`
- `seed`
- `level`
- `proposal_index`
- `current_sample_id`
- `proposal_sample_id`
- `proxy_mode`
- `l0_guard_mode`
- `proxy_score_current`
- `proxy_score_proposal`
- `truth_score_current`
- `truth_score_proposal`
- `truth_success_current`
- `truth_success_proposal`
- `truth_failed_current`
- `truth_failed_proposal`
- `stage1_accept`
- `final_accept`
- `reverse_proxy_reject`
- `truth_evaluated`
- `proxy_evaluated`
- `wall_time_proxy`
- `wall_time_truth`

Optional fields:
- `damage_state_hash`
- `n_line_out`
- `dcopf_success`
- `l0_score`
- `da_score`
- `flow_score`

## Safety Requirements

- disabled by default
- no DA decision change
- no random seed change
- no acceptance logic change
- no truth/proxy call behavior change except logging overhead
- write only when enabled
- start with N=1000 debug-size runs

## Conclusion

- current final_guard outputs are insufficient for DA-stage score analysis
- no per-proposal proxy/truth trajectory is available
- DA-side score training or DA gate redesign cannot be evaluated yet
- next step requires disabled-by-default instrumentation

Do not implement instrumentation in this task.