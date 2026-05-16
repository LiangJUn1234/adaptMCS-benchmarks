# README: Restore on a New Machine

## Purpose

This is the final handoff entry for restoring the current project state on a
new machine.

Use this file when you already have:
- the git repository;
- the HPC backup under `~/power`;
- or both.

The goal is to restore the project to the current A1/A2/DA/A4-prep state
without guessing which files matter.

## What Exists in Each Location

### Git repository

The git repository contains:
- source code;
- controller logic;
- A1/A2/A4-prep documentation;
- repository-local report snapshot under `docs/report_package/`;
- migration and artifact-management instructions.

### HPC backup

The HPC directory contains:
- `~/power/report/`
- `~/power/artifacts/`

These preserve the project handoff package and the three most important local
large artifacts that are not suitable for normal git tracking.

## Minimum Restore Paths

### Path A: Documentation / planning only

If you only need to read and continue planning:
1. clone the git repository;
2. open:
   - `docs/report_package/00_overall/OVERALL_SUMMARY_README.md`
   - `MIGRATION_AND_REPRO_CHECKLIST.md`
   - `A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md`

This is enough for:
- A4 design work;
- mentor reporting;
- project handoff review;
- writing and literature positioning.

### Path B: Offline analysis continuation

If you need to rerun offline A2 / certificate / DA-postprocessing scripts:
1. clone the git repository;
2. copy these three files from HPC into:
   `ac_ext/experiments/out/`
   - `ml_training_data_case118.csv`
   - `ml_training_data_with_dcopf_case118.csv`
   - `dcopf_flow_features_case118.npz`
3. run:

```bash
bash RESTORE_OR_CONTINUE_AFTER_MIGRATION.sh
```

This is enough for:
- offline score analysis;
- certificate audit reruns;
- DA trace analysis reruns from saved data;
- A4 prep based on the existing artifacts.

### Path C: Full benchmark continuation

If you need to rerun controller benchmarks:
1. complete Path B;
2. restore Python environment;
3. restore MATLAB;
4. restore MATLAB Engine for Python;
5. restore MATPOWER in the expected sibling location or equivalent path;
6. rerun the restore script.

Only after that should you attempt benchmark execution.

## Suggested Restore Order

1. Restore the git repository.
2. Restore the three essential large artifacts from HPC.
3. Run:

```bash
bash RESTORE_OR_CONTINUE_AFTER_MIGRATION.sh
```

4. Read the recommended files printed by the script.
5. Continue with A4-prep unless you explicitly need to rerun older stages.

## Where to Copy the HPC Files

From the HPC side, the important files currently live at:
- `~/power/artifacts/ml_training_data_case118.csv`
- `~/power/artifacts/ml_training_data_with_dcopf_case118.csv`
- `~/power/artifacts/dcopf_flow_features_case118.npz`

On the restored machine, place them into:
- `adaptMCS-benchmarks/ac_ext/experiments/out/`

The report package on HPC lives at:
- `~/power/report/`

This is useful for quick reading, but the git repository already includes a
repository-local snapshot under:
- `docs/report_package/`

## What the Restore Script Means

The restore script reports one of three practical levels:

### Level 1
- documentation and project-continuation ready

### Level 2
- offline artifact analysis ready

### Level 3
- likely benchmark-ready, assuming environment checks succeed

The script is only a status checker. It does not run benchmarks.

## Current Recommended Continuation

The next intended stage is:
- A4 certificate-aware / parameterized DCOPF optimization preparation

The default continuation is not:
- rerunning old smoke/debug jobs;
- repeating simple A2 grid expansion;
- changing DA immediately.

The default continuation is:
- use the frozen A1/A2 baseline;
- use the certificate audit and DA trace evidence;
- continue A4 branch design.

## Read First After Restore

1. `docs/report_package/00_overall/OVERALL_SUMMARY_README.md`
2. `MIGRATION_AND_REPRO_CHECKLIST.md`
3. `ARTIFACT_REGISTRY_AND_RETENTION_PLAN.md`
4. `QUICKSTART_RESTORE_OR_CONTINUE.md`
5. `A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md`

## One-Sentence Summary

If you have the git repo plus the three HPC-backed large artifacts, you can
restore the current project state well enough to continue A4 work without
reconstructing the entire A1/A2 pipeline from scratch.
