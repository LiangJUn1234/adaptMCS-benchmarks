# DA Trace Analysis case118 N1000 seed901 v001

- trace tsv: `ac_ext/experiments/out/da_traces/da_trace_case118_N1000_seed901_dcopf_failure_label/case118_corrected_da_dcopf_seed901_N1000_lop0008.tsv`
- run csv: `ac_ext/experiments/out/da_trace_case118_N1000_seed901_dcopf_failure_label.csv`

## Consistency Checks

- trace_tsv_exists: `True`
- run_csv_exists: `True`
- tsv_rows_equals_da_trace_rows: `True`
- seed_column_matches_csv_seed: `True`
- run_seed_column_matches_csv_seed: `True`
- csv_status_ok: `True`
- level_attempts_match_level_acceptance_rates_json: `True`
- truth_calls_decomposition_matches: `True`

## Overall

- total_proposals: `850`
- stage1_accept: `282` (0.331765)
- truth_evaluated: `282` (0.331765)
- final_accept: `192` (0.225882)
- reverse_proxy_reject: `25` (0.029412)

## By Level

| level | proposals | stage1_accept | truth_evaluated | final_accept | reverse_proxy_reject |
|---:|---:|---:|---:|---:|---:|
| 1 | 850 | 282 (0.331765) | 282 (0.331765) | 192 (0.225882) | 25 (0.029412) |

## Truth-evaluated Subset

- n: `282`
- ACOPF failed: `282`
- ACOPF safe: `0`
- failed_fraction: `1.000000`
- final_accept: `192`
- final_reject: `90`
- reverse_proxy_reject: `25`

## Interpretation

- All DA truth-evaluated proposals are ACOPF failures in this trace. Remaining DA truth calls are confirmation calls for failed proposals, not checks of safe proposals.
- Any DA shortcut must be preceded by cross-regime certificate audit before changing online DA logic.