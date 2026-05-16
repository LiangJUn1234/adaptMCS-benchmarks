# Candidate Cleanup After Guard Freeze

This document lists benchmark/output artifacts under `ac_ext/experiments/out` and `ac_ext/experiments/out/logs` that were created during DCOPF guard development, smoke testing, refreshed reruns, or mis-scoped all-arm runs.

No file is deleted by this document. The goal is only to separate:
- canonical artifacts that should stay
- temporary artifacts that can be removed after final guard-freeze results are verified
- artifacts that are still useful but should probably be archived
- artifacts that need manual review before any deletion

Warning:
- Do not delete `final_guard_summary_case118_lop0008_seeds901_903.md`
- Do not delete `final_guard_summary_case118_lop0008_seeds901_903.csv`
- Do not delete `ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md`
- Do not delete `PROJECT_STAGE_CONTINUITY_A1_TO_A2.md`
- Do not delete `dcopf_flow_features_case118.npz`
- Do not delete `ml_training_data_case118.csv`
- Do not delete `ml_training_data_with_dcopf_case118.csv`

Scan time context:
- project root: `/home/lhftr/code/power-rare-events/adaptMCS-benchmarks`
- scan date: `2026-05-15`
- note: this document was updated after the clean guard-freeze runs completed and after `final_guard_summary_*` was generated

## 1. Keep

### Core training / feature artifacts
- path: `ac_ext/experiments/out/ml_training_data_case118.csv`
  size: `42718017`
  modified: `2026-05-11 10:58:27 -0500`
  why: canonical ACOPF training label table
  recommended action: `keep`

- path: `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`
  size: `44269951`
  modified: `2026-05-14 02:03:47 -0500`
  why: canonical ACOPF labels plus DCOPF scalar diagnostics
  recommended action: `keep`

- path: `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
  size: `28784214`
  modified: `2026-05-14 03:04:28 -0500`
  why: canonical branch-level DCOPF PF/PT artifact for offline pseudo-limit and flow-score analysis
  recommended action: `keep`

### Clean guard-freeze run artifacts
- path: `ac_ext/experiments/out/logs/final_guard_legacy_case118_N1000_lop0008_seeds901_903.nohup.log`
  size: `1833`
  modified: `2026-05-15 01:23:26 -0500`
  why: canonical clean freeze benchmark log for legacy guard
  recommended action: `keep`

- path: `ac_ext/experiments/out/logs/final_guard_failure_label_case118_N1000_lop0008_seeds901_903.nohup.log`
  size: `1841`
  modified: `2026-05-15 01:23:25 -0500`
  why: canonical clean freeze benchmark log for failure-label guard
  recommended action: `keep`

- path: `ac_ext/experiments/out/final_guard_legacy_case118_N1000_lop0008_seeds901_903.csv`
  size: `3250`
  modified: `2026-05-15 01:37:19 -0500`
  why: canonical frozen legacy-guard result table
  recommended action: `keep`

- path: `ac_ext/experiments/out/final_guard_legacy_case118_N1000_lop0008_seeds901_903.json`
  size: `8949`
  modified: `2026-05-15 01:37:19 -0500`
  why: canonical frozen legacy-guard JSON
  recommended action: `keep`

- path: `ac_ext/experiments/out/final_guard_failure_label_case118_N1000_lop0008_seeds901_903.csv`
  size: `3118`
  modified: `2026-05-15 01:34:41 -0500`
  why: canonical frozen failure-label result table
  recommended action: `keep`

- path: `ac_ext/experiments/out/final_guard_failure_label_case118_N1000_lop0008_seeds901_903.json`
  size: `8817`
  modified: `2026-05-15 01:34:41 -0500`
  why: canonical frozen failure-label JSON
  recommended action: `keep`

- path: `ac_ext/experiments/out/final_guard_summary_case118_lop0008_seeds901_903.csv`
  size: generated after freeze
  modified: generated after freeze
  why: canonical per-seed and aggregate freeze summary table
  recommended action: `keep`

- path: `ac_ext/experiments/out/final_guard_summary_case118_lop0008_seeds901_903.md`
  size: generated after freeze
  modified: generated after freeze
  why: canonical human-readable freeze summary
  recommended action: `keep`

## 2. Temporary Smoke / Debug Candidates

- path: `ac_ext/experiments/out/dcopf_flow_features_case118_smoke.npz`
  size: `6761`
  modified: `2026-05-14 02:48:31 -0500`
  why: tiny smoke artifact superseded by full `dcopf_flow_features_case118.npz`
  recommended action: `delete_after_final_results_verified`

- path: `ac_ext/experiments/out/ml_training_data_with_dcopf_case118_smoke.csv`
  size: `14967`
  modified: `2026-05-14 01:45:50 -0500`
  why: smoke version of DCOPF-augmented training table; superseded by full dataset
  recommended action: `delete_after_final_results_verified`

- path: `ac_ext/experiments/out/hybrid_smoke_case118_N500_seed901.csv`
  size: `2030`
  modified: `2026-05-13 21:41:53 -0500`
  why: early smoke benchmark; not part of final guard freeze
  recommended action: `archive`

- path: `ac_ext/experiments/out/hybrid_smoke_case118_N500_seed901.json`
  size: `5230`
  modified: `2026-05-13 21:41:53 -0500`
  why: paired JSON for early smoke benchmark
  recommended action: `archive`

- path: `ac_ext/experiments/out/ml_failure_smoke_benchmark_case118.csv`
  size: `2001`
  modified: `2026-05-11 17:51:45 -0500`
  why: unrelated smoke benchmark for ML failure arm; not part of guard freeze
  recommended action: `archive`

- path: `ac_ext/experiments/out/ml_failure_smoke_benchmark_case118.json`
  size: `5201`
  modified: `2026-05-11 17:51:45 -0500`
  why: paired JSON for unrelated smoke benchmark
  recommended action: `archive`

- path: `ac_ext/experiments/out/collect_dcopf_feature_data_case118.log`
  size: `18954152`
  modified: `2026-05-14 02:03:47 -0500`
  why: large collection log; useful only for forensic rerun/debug if feature collection is questioned
  recommended action: `archive`

- path: `ac_ext/experiments/out/logs/dcopf_flow_features_case118.nohup.log`
  size: `18994001`
  modified: `2026-05-14 03:04:28 -0500`
  why: large background log for full NPZ collection; useful only if the NPZ provenance is challenged
  recommended action: `archive`

## 3. Misrun / Extra-Arm Output Candidates

- path: `ac_ext/experiments/out/dcopf_guard_failure_label_case118_N1000_seed901.csv`
  size: `1294`
  modified: `2026-05-14 04:04:02 -0500`
  why: single-seed failure-label run before refreshed metadata freeze; superseded by clean final multi-seed run
  recommended action: `delete_after_final_results_verified`

- path: `ac_ext/experiments/out/dcopf_guard_failure_label_case118_N1000_seed901.json`
  size: `2552`
  modified: `2026-05-14 04:04:02 -0500`
  why: paired JSON for the same superseded single-seed run
  recommended action: `delete_after_final_results_verified`

- path: `ac_ext/experiments/out/dcopf_guard_failure_label_case118_N1000_seed901_refreshed.csv`
  size: `2710`
  modified: `2026-05-15 00:42:50 -0500`
  why: refreshed metadata run, but still not the final clean multi-seed freeze and included extra arms
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_guard_failure_label_case118_N1000_seed901_refreshed.json`
  size: `7314`
  modified: `2026-05-15 00:42:50 -0500`
  why: paired JSON for refreshed but non-final run
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_guard_legacy_case118_N1000_seed901.csv`
  size: `1335`
  modified: `2026-05-14 04:04:55 -0500`
  why: single-seed legacy run superseded by clean final multi-seed freeze
  recommended action: `delete_after_final_results_verified`

- path: `ac_ext/experiments/out/dcopf_guard_legacy_case118_N1000_seed901.json`
  size: `2589`
  modified: `2026-05-14 04:04:55 -0500`
  why: paired JSON for the same superseded legacy run
  recommended action: `delete_after_final_results_verified`

- path: `ac_ext/experiments/out/hybrid_case118_N1000_seed901.csv`
  size: `2156`
  modified: `2026-05-13 22:08:31 -0500`
  why: earlier all-arm / hybrid run with extra arms; useful historically but not a clean guard-freeze artifact
  recommended action: `archive`

- path: `ac_ext/experiments/out/hybrid_case118_N1000_seed901.json`
  size: `5356`
  modified: `2026-05-13 22:08:31 -0500`
  why: paired JSON for earlier all-arm run
  recommended action: `archive`

- path: `ac_ext/experiments/out/logs/dcopf_guard_failure_label_case118_N1000_seed901.nohup.log`
  size: `1038`
  modified: `2026-05-14 04:04:02 -0500`
  why: log for superseded single-seed failure-label run
  recommended action: `delete_after_final_results_verified`

- path: `ac_ext/experiments/out/logs/dcopf_guard_failure_label_case118_N1000_seed901_refreshed.nohup.log`
  size: `1797`
  modified: `2026-05-15 00:42:50 -0500`
  why: log for refreshed but non-final run with extra arms
  recommended action: `archive`

- path: `ac_ext/experiments/out/logs/dcopf_guard_legacy_case118_N1000_seed901.nohup.log`
  size: `1025`
  modified: `2026-05-14 04:04:55 -0500`
  why: log for superseded single-seed legacy run
  recommended action: `delete_after_final_results_verified`

- path: `ac_ext/experiments/out/logs/dcopf_guard_legacy_case118_N1000_seed901_refreshed.nohup.log`
  size: `951`
  modified: `2026-05-15 00:43:56 -0500`
  why: log for refreshed but non-final legacy run
  recommended action: `archive`

## 4. Needs Review

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_summary.csv`
  size: `23923`
  modified: `2026-05-14 03:38:07 -0500`
  why: valid offline score-analysis summary; may still be cited during A1.1 flow-score work
  recommended action: `needs_review`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_summary.json`
  size: `124260`
  modified: `2026-05-14 03:38:07 -0500`
  why: detailed JSON backing the above summary
  recommended action: `needs_review`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_per_lop_summary.csv`
  size: `25473`
  modified: `2026-05-14 03:38:07 -0500`
  why: per-LOP analysis output that may be useful for later pseudo-limit tuning
  recommended action: `needs_review`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_cohorts.csv`
  size: `12768`
  modified: `2026-05-14 03:38:07 -0500`
  why: cohort breakdown for general score analysis; may be reproducible but still analytically useful
  recommended action: `needs_review`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_lop0008_summary.csv`
  size: `23923`
  modified: `2026-05-14 03:41:01 -0500`
  why: directly relevant to the `lop=0.008` guard diagnosis and supports the reasoning that guard-objective mismatch preceded A2
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_lop0008_summary.json`
  size: `124260`
  modified: `2026-05-14 03:41:01 -0500`
  why: detailed JSON for the key `lop=0.008` slice and supports the reasoning that guard-objective mismatch preceded A2
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_lop0008_per_lop_summary.csv`
  size: `25473`
  modified: `2026-05-14 03:41:01 -0500`
  why: per-LOP table generated during slice-specific analysis; should be archived rather than deleted because it supports pre-A2 reasoning
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_lop0008_cohorts.csv`
  size: `12768`
  modified: `2026-05-14 03:41:01 -0500`
  why: cohort breakdown for key slice; analytically useful for the guard-mismatch-to-A2 transition and should be archived
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_all_lop_summary.csv`
  size: `29278`
  modified: `2026-05-14 03:44:36 -0500`
  why: broad all-LOP analysis useful for later training design and supports the reasoning that guard-objective mismatch preceded A2
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_all_lop_summary.json`
  size: `129848`
  modified: `2026-05-14 03:44:36 -0500`
  why: detailed JSON backing all-LOP flow-score analysis and supporting the reasoning that guard-objective mismatch preceded A2
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_all_lop_per_lop_summary.csv`
  size: `141989`
  modified: `2026-05-14 03:44:36 -0500`
  why: large derived table that may still support later pseudo-limit parameter sweeps and should be archived rather than deleted
  recommended action: `archive`

- path: `ac_ext/experiments/out/dcopf_flow_score_analysis_case118_all_lop_cohorts.csv`
  size: `80398`
  modified: `2026-05-14 03:44:36 -0500`
  why: companion cohort table for the above all-LOP analysis and useful supporting evidence for the A1-to-A2 transition
  recommended action: `archive`

## 5. Notes

- `DCOPF_IMPLEMENTATION_AND_DIAGNOSTIC_REPORT.md` is not in `out`, but it should remain part of the permanent record.
- `ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md` should also remain part of the permanent record.
- `PROJECT_STAGE_CONTINUITY_A1_TO_A2.md` should also remain part of the permanent record.
- Do not delete any `final_guard_*` output until both guard modes finish and their CSV/JSON are manually verified.
- Do not delete `final_guard_summary_*`; these are now part of the frozen A1-Guard record.
- After verification, the safest deletion order is:
- old single-seed `dcopf_guard_*`
- smoke artifacts
- refreshed extra-arm reruns
- only then consider large debug logs or offline analysis summaries
