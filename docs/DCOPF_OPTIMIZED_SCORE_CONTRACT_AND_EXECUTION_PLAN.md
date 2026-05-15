# DCOPF Optimized Score Contract and Execution Plan

## 0. Scope
This document freezes the next implementation step for optimized DCOPF without modifying the existing raw `proxy_mode="dcopf"` path. The immediate goal is to produce a branch-level DCOPF flow artifact that allows pseudo-limit and flow-stress scoring experiments to run fully offline after one data-collection pass.

## 1. Score Contract
Legacy compatibility fields remain required:
- `success`
- `s_line`
- `s_volt`
- `s_any`

New score contract fields:
- `l0_score: float`
- `da_score: float`
- `fail_proxy: float`
- `flow_score: float`
- `solver_failed: bool`
- `score_source: str`
- `score_version: str`
- `score_valid: bool`

Contract intent:
- `l0_score` is a continuous ranking score for Level-0 top-K selection.
- `da_score` is a conservative delayed-acceptance gate score.
- `fail_proxy` is an explicit failure-risk signal and must not be overloaded as a continuous successful-state ranker.
- `flow_score` is the raw continuous stress score before controller-specific post-processing.
- `solver_failed` explicitly records DCOPF hard/soft failure semantics.
- `score_source` describes the scoring method family, for example `pseudo_limit_flow_stress`.
- `score_version` identifies the exact scoring definition, for example `dcopf_raw`, `dcopf_pseudo_limit_base_margin`, `dcopf_hybrid_pseudolimit`, `dcopf_optimized_v001`.
- `score_valid` means the new score contract was constructed according to the selected method, not merely that the payload exists.

## 2. Fallback Rules
Required fallback semantics:

```python
if solver_failed:
    l0_score = float("inf")
    da_score = float("inf")
    fail_proxy = 1.0
    score_valid = True

if l0_score is missing:
    l0_score = s_any

if da_score is missing:
    da_score = s_any
```

Additional rule:
- If `fail_proxy` is missing in a legacy path, use `1.0` when the solver failed or `s_any` is `+inf`, otherwise `0.0`.

Rationale:
- New and old proxy modes will coexist for some time.
- The controller must not crash or silently mis-rank when consuming mixed payload versions.

## 3. Data Artifact
The first required artifact is:
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`

Required arrays:
- `sample_id` `(N,)`
- `seed` `(N,)`
- `line_outage_prob` `(N,)`
- `acopf_fail_label` `(N,)`
- `dcopf_success` `(N,)`
- `PF` `(N, 186)`
- `PT` `(N, 186)`
- `branch_status` `(N, 186)`
- `RATE_A` `(186,)`

Recommended additional arrays:
- `flow_valid` `(N,)`
- `basecase_PF` `(186,)`
- `basecase_PT` `(186,)`

Design constraints:
- The first version must export full branch-level `PF/PT` matrices.
- Compressed scalar features must not be the only saved artifact.
- Offline pseudo-limit experiments must not require re-running MATLAB.

## 4. Why NPZ Is Mandatory
The current `dcopf_s_line/s_volt/s_any` fields are insufficient for continuous rank optimization on `case118`.

Therefore:
- store the raw per-branch flow matrices once,
- derive pseudo-limit scores offline many times,
- keep MATLAB out of the inner optimization loop.

This is the minimum design that supports:
- base-margin pseudo limit,
- training-percentile pseudo limit,
- hybrid pseudo limit,
- branch-specific margin,
- global margin.

## 5. Immediate Script Roadmap
### 5.1 collect_dcopf_flow_feature_data.py
Purpose:
- read `ml_training_data_case118.csv`,
- rebuild each damage state,
- run `eval_proxy(..., proxy_mode="dcopf", debug=True)`,
- save branch-level flows to `dcopf_flow_features_case118.npz`.

Requirements:
- no ACOPF re-evaluation,
- preserve `sample_id`, `seed`, `line_outage_prob`, `acopf_fail_label`,
- save full `PF/PT` matrices,
- save `branch_status`,
- save `RATE_A` once,
- support checkpoint/resume,
- flush progress regularly,
- run safely in the background for the full dataset.

### 5.2 analyze_dcopf_flow_scores.py
Purpose:
- consume the NPZ artifact and evaluate candidate flow-stress score definitions fully offline.

Required outputs:
- AUROC / AUPRC for ACOPF failure,
- Top-K recall / precision,
- rank inversion statistics,
- guard simulation results,
- per-score comparison table.

Mandatory implementation rules:
- failed DCOPF samples must remain `+inf` in ranking-oriented scores,
- continuous flow score must be computed only on `dcopf_success == True` samples,
- outaged branches must be excluded from per-sample max-flow stress aggregation,
- pseudo-limit estimation must exclude failed samples and must use train split only.

Required ranking-side logic:

```python
success = d["dcopf_success"].astype(bool)
PF = d["PF"]
PT = d["PT"]
branch_status = d["branch_status"].astype(bool)

score = np.full(PF.shape[0], np.inf, dtype=float)

# only compute continuous flow score for successful DCOPF solves
abs_flow = np.maximum(np.abs(PF), np.abs(PT))

# outaged branches should not contribute
abs_flow = np.where(branch_status, abs_flow, np.nan)

ratio = abs_flow / pseudo_limit[None, :]
flow_score_success = np.nanmax(ratio - 1.0, axis=1)

score[success] = flow_score_success[success]

# failed samples remain +inf
assert np.all(np.isinf(score[~success]))
```

Metric-evaluation rule:
- `ranking_score` keeps `failed -> +inf`
- `metric_score` must cap failed samples above the largest finite score before AUROC/AUPRC evaluation

Recommended metric-side conversion:

```python
max_finite_score = np.max(ranking_score[np.isfinite(ranking_score)])
metric_score = np.where(
    np.isfinite(ranking_score),
    ranking_score,
    max_finite_score + 1.0,
)
```

Reason:
- ranking semantics remain unchanged,
- top-K and guard logic still see failed samples as maximal risk,
- AUROC/AUPRC code remains compatible with libraries such as `sklearn` that may reject `+inf`.

Required pseudo-limit estimation rule:

```python
train_success = train_mask & success
flows_train = abs_flow[train_success]
limit = np.nanpercentile(flows_train, q, axis=0)
```

This rule is mandatory because failed samples currently carry zero `PF/PT`, and including them in percentile estimation would bias pseudo-limits downward and manufacture false signal.

ML-feature handling rule:
- for ranking and guard simulation: `failed -> +inf`
- for downstream ML feature tables: do not feed `+inf` directly into tree models

Recommended ML-feature conversion:

```python
cap = np.nanpercentile(
    flow_score_success[np.isfinite(flow_score_success)],
    99.5,
)
model_feature_score = np.where(success, flow_score_success, cap + 1.0)
model_feature_failed = (~success).astype(int)
```

Interpretation:
- ranking logic should preserve the semantics that failed DCOPF is maximal risk,
- ML feature logic should convert that semantic into a capped high numeric feature plus an explicit failure flag.

## 6. Candidate Score Versions
Expected first score-version sequence:
- `dcopf_raw`
- `dcopf_pseudo_limit_base_margin`
- `dcopf_pseudo_limit_train_percentile`
- `dcopf_hybrid_pseudolimit`
- `dcopf_optimized_v001`

Recommended rule:
- `score_source` captures the family,
- `score_version` captures the exact frozen implementation.

## 7. Execution Order
1. Freeze this contract.
2. Build `collect_dcopf_flow_feature_data.py`.
3. Run a smoke collection.
4. Launch the full collection in the background.
5. Validate the NPZ artifact.
6. Only then build offline score-analysis code.
7. Only after a continuous `l0_score` is validated should controller-layer decoupling begin.

## 8. Current Implementation Decision
The current turn should implement and execute only the artifact-collection step.

Out of scope for this turn:
- modifying raw `dcopf` score computation,
- modifying the controller or guard,
- implementing `proxy_mode="dcopf_optimized"`,
- running any benchmark.

## 9. Progress Log
This section records what has already been implemented and executed so the work trace remains searchable later.

### 9.1 Files Added
Added:
- `DCOPF_OPTIMIZED_SCORE_CONTRACT_AND_EXECUTION_PLAN.md`
- `ac_ext/experiments/collect_dcopf_flow_feature_data.py`

### 9.2 Runtime Environment Notes
The default Conda `python3` in this environment is Python 3.13 and was not suitable for reliable MATLAB engine startup.

Working runtime for collection:
- interpreter: `/usr/bin/python3.10`
- `PYTHONPATH=/home/lhftr/tmp/matlab-engine-build/lib`
- `MATLAB_ENGINE_START_TIMEOUT_SEC=1800`

This was necessary because:
- `matlab.engine` supports Python 3.10 in this environment,
- the default Python 3.13 path caused engine startup stalls/timeouts,
- once the collector switched to Python 3.10, smoke and full collection succeeded.

### 9.3 Smoke Validation
Smoke artifact:
- `ac_ext/experiments/out/dcopf_flow_features_case118_smoke.npz`

Smoke result:
- 3-row run completed successfully.
- Verified shapes:
- `PF (3, 186)`
- `PT (3, 186)`
- `branch_status (3, 186)`
- `RATE_A (186,)`

Smoke also confirmed:
- MATLAB debug payload returns `branch` and `bus` as `matlab.double`, not Python `list`.
- The collector was updated to accept any array-convertible MATLAB payload, not just Python lists.

### 9.4 Full Collection Completed
Full artifact:
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`

Log:
- `ac_ext/experiments/out/logs/dcopf_flow_features_case118.nohup.log`

Observed completion summary from the log:
- `written=30000 completed_total=30000/30000`
- `Finished. new_rows=30000 total_rows=30000 elapsed=911.0s rate=32.93/s`

Artifact summary:
- file size: about `28M`
- `sample_id (30000,)`
- `PF (30000, 186)`
- `PT (30000, 186)`
- `branch_status (30000, 186)`
- `RATE_A (186,)`
- `dcopf_success_sum = 26230`
- `flow_valid_sum = 30000`

Interpretation:
- all 30000 rows produced usable flow matrices,
- every row has valid branch-level `PF/PT` data,
- future pseudo-limit and flow-stress experiments can now run fully offline from this NPZ.

### 9.5 Important Implementation Detail
The collector intentionally stores full branch-level flow matrices first and defers all pseudo-limit logic.

That means:
- no pseudo-limit assumptions are baked into the artifact,
- future score designs can be tested offline without rerunning MATLAB,
- compressed features should be derived downstream from the NPZ, not used as the only stored representation.

Failure-path constraint discovered after artifact validation:
- in `dcopf_success == 0` samples, stored `PF/PT` are all zeros,
- these zeros must not be interpreted as low-stress or low-risk flows,
- downstream score construction must branch on solver outcome before using flow magnitudes.

Required rule for every future flow-based score:

```python
if dcopf_success == False:
    flow_score = float("inf")
    fail_proxy = 1.0
else:
    flow_score = max(abs(PF_active) / pseudo_limit - 1.0)
```

Interpretation:
- failed DCOPF samples do not carry a usable continuous flow solution,
- the stored zero flows are an artifact of the failure path, not evidence of safety,
- any score pipeline that ignores `dcopf_success` will catastrophically mis-rank the highest-risk samples.

### 9.6 Immediate Next Step After This Collection
The next script should be:
- `ac_ext/experiments/analyze_dcopf_flow_scores.py`

Its job should be to consume `dcopf_flow_features_case118.npz` and evaluate:
- base-margin pseudo limit
- training-percentile pseudo limit
- hybrid pseudo limit
- branch-specific margin
- global margin

All of that work should now be MATLAB-free and NPZ-driven.

Non-negotiable analysis constraints for that script:
- failed samples must never contribute zero-flow evidence to pseudo-limit estimation,
- failed samples must remain `+inf` in ranking outputs,
- any ML-oriented export derived from that analysis must convert failure into `capped score + failure flag`, not raw `+inf`.

### 9.7 Searchable Work Trace
Checkpoint date:
- `2026-05-14`

This subsection is intentionally redundant so later repository search can recover the work trace quickly.

Key search terms:
- `RATE_A=0`
- `dcopf_flow_features_case118.npz`
- `collect_dcopf_flow_feature_data.py`
- `dcopf_success_sum = 26230`
- `flow_valid_sum = 30000`
- `written=30000 completed_total=30000/30000`
- `MATLAB engine Python 3.10`

Artifacts confirmed present:
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- `ac_ext/experiments/out/dcopf_flow_features_case118_smoke.npz`
- `ac_ext/experiments/out/logs/dcopf_flow_features_case118.nohup.log`
- `DCOPF_IMPLEMENTATION_AND_DIAGNOSTIC_REPORT.md`

Collection status:
- Smoke collection completed successfully.
- Full `case118` DCOPF flow collection completed successfully.
- Final NPZ contains all 30000 samples with valid flow matrices.
- Subsequent score-design work should use the NPZ artifact, not repeated MATLAB collection.

Confirmed artifact summary:
- `sample_id (30000,)`
- `PF (30000, 186)`
- `PT (30000, 186)`
- `branch_status (30000, 186)`
- `RATE_A (186,)`
- `dcopf_success_sum = 26230`
- `flow_valid_sum = 30000`

Additional validation result:
- `sample_id` aligns exactly with `ml_training_data_case118.csv`
- sampled `branch_status` matches `line_out_json` with no audited mismatches
- outaged branches have `PF=PT=0` as expected
- failed samples (`n=3770`) also have `PF/PT=0` on all branches, so solver failure must be handled before any flow-based stress calculation

Recorded execution pattern:
- smoke run used `/usr/bin/python3.10`
- required `PYTHONPATH=/home/lhftr/tmp/matlab-engine-build/lib`
- used `MATLAB_ENGINE_START_TIMEOUT_SEC=1800`
- full collection was launched in the background and completed in about `911s`

Operational conclusion:
- The expensive MATLAB-backed branch-flow extraction step has been completed once for `case118`.
- The next stage should remain fully offline unless new raw proxy fields or a new case are required.

### 9.8 Offline Flow-Score Analysis Implemented
Added:
- `ac_ext/experiments/analyze_dcopf_flow_scores.py`

Current analysis scope:
- compares `raw_success_fail_score`
- compares `base_margin_score`
- compares `train_percentile_score`
- compares `hybrid_score`
- uses train seeds `7, 42, 100, 200`
- uses eval seed `300`
- supports optional `--eval-lop` to align directly with benchmark-style single-LOP runs (for example `--eval-lop 0.008`)
- uses the current guard-simulation defaults:
- `K_initial=200`
- `sus_p0=0.15` with `n_seed=ceil(N_eval * sus_p0)` when `--n-seed` is not provided
- `tail_audit=50`
- `expand_factor=1.5`
- `max_expand_rounds=3`

Generated outputs:
- `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_summary.csv`
- `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_per_lop_summary.csv`
- `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_cohorts.csv`
- `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_summary.json`

Guard outputs now include two explicit modes:
- `legacy_truth_score_guard` semantics (aligned with current controller behavior using ACOPF `s_any`)
- `failure_label_guard` semantics (event-oriented guard on ACOPF failure labels)
: this mode does **not** use `gamma_candidate` from `n_seed`; it audits only whether tail samples contain failure events.

Failure-label guard rule:

```python
hits_this_round = int(np.sum(risk_event_label[audit_indices]))
```

This avoids the binary-threshold pathology where `n_seed` can exceed the number of failures and force `gamma=-1`, which would otherwise count all safe audit samples as inversions.

Backward compatibility:
- legacy-style fields (`rank_inversion_hits`, `simulated_K_final`, `guard_fallback_flag`, etc.) are still present and map to legacy guard semantics.

Additional score safety rule now implemented:
- if a successful DCOPF sample yields non-finite flow score, it is forced to `+inf` and counted in `n_bad_success_flow_score`.

First-run result:
- `73` candidate score configurations were evaluated offline.
- On the eval seed `300`, all tested score families produced identical ACOPF-failure classification metrics:
- `AUROC = 1.0`
- `AUPRC = 1.0`
- `Top-200 recall = 0.2751031636863824`
- `simulated_K_final = 6000`
- `guard_fallback_flag = True`

Interpretation of that result:
- this does not mean the continuous flow score is constant or broken,
- it means `dcopf_success=False` already separates all ACOPF-failure samples from ACOPF-success samples on this split,
- therefore the current failure-label metrics are dominated by the binary fail signal,
- the continuous pseudo-limit score only changes ordering among successful DCOPF samples and does not change failure-vs-success separation on seed `300`.

Important validation detail:
- continuous successful-sample scores are not degenerate;
- for one tested base-margin score on seed `300`, the successful-sample flow score had about `1583` rounded unique values with median about `2.64` and 99th percentile about `26.67`;
- therefore the score pipeline is producing continuous variation, but that variation is currently masked by perfect fail/success separation in the chosen eval split.
