# Artifact Registry and Retention Plan

## Purpose

This document defines which files in the current project are:
- canonical and should be preserved in git;
- local-but-essential and must be preserved outside git;
- regenerable and lower-priority;
- temporary and noncanonical.

This is the artifact-management complement to:
- `MIGRATION_AND_REPRO_CHECKLIST.md`

## Artifact Classes

### Class A: Canonical repository artifacts

Definition:
- source code and versioned project-state documents that define the current
  stage of the project.

Keep in git:
- `ac_ext/*.py` and relevant subpackages;
- MATLAB helper files under `ac_ext/matlab/`;
- root planning/report markdown;
- `docs/report_package/`;
- intentionally tracked frozen summaries under `results/` and selected
  repository-facing outputs.

Examples:
- `DCOPF_IMPLEMENTATION_AND_DIAGNOSTIC_REPORT.md`
- `ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md`
- `A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md`
- `PROJECT_STAGE_CONTINUITY_A1_TO_A2.md`
- `MENTOR_UPDATE_CASE118_GUARD_DA_TRACE_A4_NEXT.md`
- `docs/report_package/...`

Retention policy:
- preserve indefinitely;
- include in project handoff;
- treat as authoritative narrative/state documentation.

### Class B: Local essential derived artifacts

Definition:
- large outputs not suitable for normal git tracking but required for offline
  continuation and reproducibility of the current stage.

Current critical examples:
- `ac_ext/experiments/out/ml_training_data_case118.csv`
- `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`

Why critical:
- A2 offline training/evaluation depends on them;
- certificate audit depends on them;
- they capture expensive prior computation that should not be casually lost.

Retention policy:
- preserve locally and in backups;
- include in machine migration;
- do not delete unless an external archive or exact regeneration path is
  already secured.

### Class C: Frozen benchmark evidence

Definition:
- outputs that directly support the A1/A2 stage conclusions and should remain
  available for reporting and verification.

Examples:
- `final_guard_summary_case118_lop0008_seeds901_903.*`
- `final_guard_legacy_case118_N1000_lop0008_seeds901_903.*`
- `final_guard_failure_label_case118_N1000_lop0008_seeds901_903.*`
- DA trace analysis reports
- certificate audit reports
- A2 comparison reports

Notes:
- many of these are intentionally snapshotted under `docs/report_package/`;
- some originals live in ignored output directories and are not git-tracked.

Retention policy:
- preserve at least one canonical copy;
- prefer repository-facing markdown/csv/json summaries over raw transient logs.

### Class D: Regenerable analysis outputs

Definition:
- analysis products that are useful, but can be recreated if the Class B local
  artifacts and scripts survive.

Examples:
- offline score comparison tables;
- guard tuning summaries;
- failed-state severity comparison reports;
- DA post-analysis tables derived from saved trace files.

Retention policy:
- useful to keep;
- not first-priority if storage is constrained;
- can be regenerated from preserved source artifacts.

### Class E: Temporary / debug / scratch outputs

Definition:
- noncanonical runs created during development, validation, or troubleshooting.

Examples:
- `*debug*`
- `*smoke*`
- `*refreshed*`
- one-off retry traces
- `nohup` logs
- superseded single-seed scratch benchmark files

Retention policy:
- do not treat as canonical;
- archive or delete only after final evidence has been verified;
- never use as the main source for project-stage conclusions.

## Current Canonical Result Set

The current project stage before A4 is supported by the following result
families:

### A1 guard-freeze evidence
- legacy vs failure-label summaries
- frozen summary markdown/csv

### A2 score-tuning closure evidence
- raw-success-fail vs trained-physics comparisons
- guard tuning results
- failed-state severity results
- combined A2.2 comparison report

### DA trace evidence
- representative DA trace run summary
- DA trace analysis report
- DA-stage readiness audit

### Certificate evidence
- DCOPF-failure certificate audit outputs

### A4-prep / mentor packaging
- A4 prep plan
- continuity note
- mentor update docs
- report package snapshot

## Current Risk if Artifacts Are Lost

### If Class A is lost
- project state and method rationale become ambiguous;
- future work may repeat already-resolved design questions.

### If Class B is lost
- A2/A4 offline continuation is severely weakened;
- prior expensive derived data must be regenerated;
- some analyses become blocked until MATLAB-backed steps are repeated.

### If Class C is lost
- reporting continuity suffers;
- conclusions may still be reconstructable, but only with extra effort.

### If Class E is lost
- usually low impact if canonical summaries are already preserved.

## Retention Decision Table

### Keep in git
- source code;
- root documentation;
- `docs/report_package/`;
- selected final summaries already intended for repository-facing use.

### Keep locally and back up
- `ml_training_data_case118.csv`
- `ml_training_data_with_dcopf_case118.csv`
- `dcopf_flow_features_case118.npz`

### Archive if storage pressure exists
- old intermediate analysis outputs not used directly in the frozen summary;
- large trace/debug outputs after their distilled reports are preserved;
- old refresh runs superseded by final summaries.

### Safe to treat as disposable only after verification
- debug retries;
- smoke outputs;
- transient logs;
- superseded scratch outputs.

## Recommended Artifact Transfer Bundle

For a serious migration or project handoff, transfer at minimum:
- the `adaptMCS-benchmarks` git repository;
- the outer `report/` directory if the recipient uses the standalone package;
- the three essential large local artifacts:
  - `ml_training_data_case118.csv`
  - `ml_training_data_with_dcopf_case118.csv`
  - `dcopf_flow_features_case118.npz`

If possible, also preserve:
- representative DA trace TSVs;
- key JSON summaries that support narrative claims;
- local archive manifests and cleanup plans.

## Relationship to `.gitignore`

The current `.gitignore` intentionally excludes most of:
- `ac_ext/experiments/out/**`
- logs
- debug/smoke/transient outputs

This is appropriate for repo hygiene, but it means:
- git status alone is not a sufficient artifact registry;
- some essential local artifacts exist outside the tracked set;
- migration requires an explicit artifact checklist, not just `git clone`.

## Recommended Next Administrative Step

To reduce future migration risk:
1. preserve a checksum or size manifest for Class B essential artifacts;
2. record where each artifact was produced and which script consumes it;
3. keep a short "last verified on machine X" note when moving environments.

That is enough to prevent most accidental loss without turning the project into
an artifact warehouse.
