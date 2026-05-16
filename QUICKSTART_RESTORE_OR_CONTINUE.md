# Quickstart: Restore or Continue After Migration

## Purpose

This file is the fastest entry point after moving the project to a new
machine.

Use it when you want to answer one of two questions:
- "Have I restored enough of the project to safely continue from the current
  A1/A2/DA/A4-prep state?"
- "What is the next recommended step from the current project stage?"

## Fastest Path

From the repository root:

```bash
bash RESTORE_OR_CONTINUE_AFTER_MIGRATION.sh
```

The script does not run benchmarks. It only checks:
- repository structure;
- key documentation;
- required local large artifacts;
- Python interpreter availability;
- MATLAB / MATPOWER presence;
- current project stage continuation hints.

## Expected Outcome Levels

### Level 1: Documentation continuation ready

You can:
- read the frozen A1/A2/DA/certificate/A4-prep materials;
- continue writing documents;
- continue mentor reporting;
- continue A4 design work.

### Level 2: Offline analysis continuation ready

You can additionally:
- rerun offline A2 analysis scripts;
- rerun certificate audit;
- rerun DA trace post-analysis from saved artifacts.

This requires the local large artifacts:
- `ac_ext/experiments/out/ml_training_data_case118.csv`
- `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`

### Level 3: Benchmark reproduction ready

You can additionally:
- rerun controller benchmarks;
- rerun DA trace generation end-to-end.

This requires:
- Python environment;
- MATLAB;
- MATLAB Engine for Python;
- MATPOWER sibling checkout or equivalent configured path.

## Current Recommended Next Step

If the script reports Level 1 or Level 2 only, the recommended continuation is:
1. confirm large artifacts are present;
2. confirm MATLAB/MATPOWER path reconstruction if benchmark work is planned;
3. continue A4-prep rather than rerunning old A1/A2 work.

## Read First After Restore

1. `docs/report_package/00_overall/OVERALL_SUMMARY_README.md`
2. `MIGRATION_AND_REPRO_CHECKLIST.md`
3. `ARTIFACT_REGISTRY_AND_RETENTION_PLAN.md`
4. `A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md`

## If You Want to Continue the Research

The current project state before A4 is:
- A1 completed and frozen;
- A2 simple score tuning completed and saturated;
- DA trace completed;
- certificate audit completed;
- next step is A4 certificate-aware / parameterized DCOPF optimization.

This means the default continuation is not:
- rerun old smoke/debug jobs;
- expand simple margin/q/epsilon grids again;
- modify DA immediately.

The default continuation is:
- use the current frozen baseline;
- continue A4 branching design;
- decide between certificate route and parameterization route.
