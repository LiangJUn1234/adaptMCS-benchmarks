# Migration and Repro Checklist

## Purpose

This document defines the minimum checklist for moving the current
`adaptMCS-benchmarks` project state to a new machine or handing it off to a
new operator without losing the ability to inspect, continue, and eventually
reproduce the A1/A2/DCOPF-screening workflow.

The goal is not only to move source code. The goal is to preserve:
- repository history and project-stage documentation;
- the MATLAB/MATPOWER execution path used by the controller;
- the derived artifacts needed for offline analysis;
- the distinction between frozen results, regenerable outputs, and local-only
  scratch/debug files.

## Current Scope

The current completed scope before A4 is:
- A1 guard objective alignment is frozen.
- A2 simple score tuning is completed and closed.
- DA trace instrumentation and representative DA analysis are completed.
- DCOPF-failure certificate audit is completed.
- A4 formulation-prep is documented, but A4 optimization itself is not yet
  implemented.

## Repository Boundary

The active git repository is:
- `/home/lhftr/code/power-rare-events/adaptMCS-benchmarks`

Important:
- `/home/lhftr/code/power-rare-events` is not the git root.
- `/home/lhftr/code/power-rare-events/report` is a higher-level handoff
  package outside this git repo.
- A repository-local snapshot of that report package is stored under:
  `docs/report_package/`

Migration must preserve both:
- the git repo itself;
- the outer `report/` directory if the handoff consumer expects the standalone
  organized report package.

## Migration Levels

### Level 1: Documentation / analysis continuation

Sufficient for:
- reading code and reports;
- continuing A4 design work;
- continuing offline CSV/JSON/TSV-based analysis;
- mentor reporting and paper planning.

Required:
- git repo;
- `docs/report_package/`;
- root markdown planning/report files;
- frozen summary outputs tracked in repo.

### Level 2: Offline artifact analysis continuation

Sufficient for:
- re-running A2 offline scripts that consume existing CSV/NPZ artifacts;
- re-running certificate audit;
- re-running DA trace post-processing;
- regenerating markdown/csv/json summaries from existing artifacts.

Required:
- everything in Level 1;
- local large artifacts not tracked in git, especially:
  - `ac_ext/experiments/out/ml_training_data_case118.csv`
  - `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`
  - `ac_ext/experiments/out/dcopf_flow_features_case118.npz`

### Level 3: Full benchmark reproduction

Sufficient for:
- re-running controller-driven SuS/DCOPF/ACOPF benchmarks;
- re-running DA trace generation end-to-end;
- regenerating new experiment outputs from source code rather than reading
  previously saved outputs.

Required:
- everything in Levels 1 and 2;
- correct Python environment;
- correct MATLAB installation;
- MATLAB Engine for Python;
- MATPOWER installation and path setup;
- any case files / helper files expected by the wrappers.

Current project status:
- Level 1 is ready.
- Level 2 is mostly ready if large artifacts are preserved.
- Level 3 still depends on explicit environment recreation.

## Environment Freeze Checklist

### Python

Record and recreate:
- Python interpreter version.
- Virtual environment path currently used in this project:
  `/home/lhftr/venv310/bin/python`
- Installed package set for the benchmark scripts.
- `numpy`, `scipy`, and any other imported scientific packages.

Recommended action:
- export the package list from the active venv before migration;
- store a reproducible environment file in the repo later if long-term
  portability becomes a priority.

### MATLAB

Record and recreate:
- MATLAB version used by the project.
- Any MATLAB startup behavior needed for the engine.
- The timeout environment variable used during runs:
  `MATLAB_ENGINE_START_TIMEOUT_SEC`

Known historical context from repository docs:
- MATLAB 2022a has been the expected environment in repo documentation.

### MATLAB Engine for Python

Record and recreate:
- the exact Python package / build used for MATLAB Engine;
- whether it is installed into the active venv or supplied externally;
- any custom `PYTHONPATH` overrides used in prior runs.

If this is missing on the destination machine:
- offline report analysis can still continue;
- end-to-end benchmark reproduction will fail.

### MATPOWER

Record and recreate:
- MATPOWER repository location;
- MATPOWER version;
- how the MATLAB wrappers discover MATPOWER functions.

Current outer project contains:
- `/home/lhftr/code/power-rare-events/matpower`

Migration risk:
- moving only `adaptMCS-benchmarks` without the expected MATPOWER sibling can
  break runtime resolution unless the destination layout is updated.

### Filesystem Layout Assumption

Current path pattern:
- `/home/lhftr/code/power-rare-events/adaptMCS-benchmarks`
- `/home/lhftr/code/power-rare-events/matpower`

If the new machine uses a different layout:
- code may still work if configuration paths are corrected;
- benchmark scripts must not assume the old absolute paths remain valid.

## Artifact Freeze Checklist

### Artifacts that should remain in git

These are the minimum versioned handoff materials:
- controller / experiment / audit scripts;
- root planning and report markdown;
- `docs/report_package/` snapshot;
- frozen summary outputs already intentionally versioned;
- cleanup manifests and archive plans.

### Artifacts that should be preserved locally even if not in git

These are required for meaningful offline continuation:
- `ac_ext/experiments/out/ml_training_data_case118.csv`
- `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- any additional large derived tables used by downstream notebooks/scripts
  outside git.

### Artifacts that are useful but not critical

These help trace prior reasoning, but are not the first files to save in a
constrained migration:
- debug DA trace outputs;
- intermediate flow-score analysis outputs;
- smoke outputs;
- refreshed / temporary benchmark refresh files;
- old logs.

### Artifacts that should not be treated as canonical

These may exist locally but should not define the project state:
- `debug*`
- `smoke*`
- `refreshed*`
- transient `nohup` logs
- nonfinal single-seed scratch outputs superseded by frozen summaries

## Minimum File Bundle for Immediate Handoff

For a compact handoff that preserves project continuity, carry:
- the git repo at `adaptMCS-benchmarks/`;
- the outer `report/` directory if used by the recipient;
- the three large local artifacts:
  - `ml_training_data_case118.csv`
  - `ml_training_data_with_dcopf_case118.csv`
  - `dcopf_flow_features_case118.npz`

Without those three large artifacts:
- A4 planning can still continue;
- offline score/certificate analyses may not be rerunnable;
- benchmark reproduction from source remains incomplete.

## Verification Checklist After Migration

### Documentation verification

Confirm:
- repo opens cleanly;
- `README.md` is present;
- `docs/report_package/` is present;
- A1/A2/A4 docs are readable.

### Offline artifact verification

Confirm existence of:
- `ac_ext/experiments/out/ml_training_data_case118.csv`
- `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`

### Python verification

Confirm:
- the intended Python interpreter exists;
- imports for the offline scripts succeed.

### MATLAB/MATPOWER verification

Confirm:
- MATLAB launches;
- MATLAB Engine import works in Python;
- MATPOWER path is resolvable.

### Controlled smoke verification

Before any full benchmark:
- run a minimal non-heavy offline script first;
- then run a very small benchmark/debug path only if environment validation is
  required.

Do not use a full benchmark as the first migration check.

## Current Practical Assessment

The project currently has:
- good source and report continuity;
- good stage-level documentation continuity;
- partial reproducibility readiness;
- remaining dependence on explicit environment recreation and large local
  artifact preservation.

Therefore the correct claim is:
- the project is migration-ready for continuation and handoff;
- it is not yet fully environment-frozen for one-command benchmark
  reproduction on a fresh machine.

## Recommended Next Hardening Step

To move from "migration-capable" to "reproducibility-hardened", the next
highest-value actions are:
1. record the exact Python package environment;
2. record the MATLAB / Engine / MATPOWER setup procedure;
3. keep a formal registry of required local artifacts and their roles.

The artifact side is documented in:
- `ARTIFACT_REGISTRY_AND_RETENTION_PLAN.md`
