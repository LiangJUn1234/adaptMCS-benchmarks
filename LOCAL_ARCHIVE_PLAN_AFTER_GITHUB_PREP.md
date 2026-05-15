# Local Archive Plan After GitHub Prep

This note describes which local artifacts are good archive candidates after GitHub upload preparation.

No file is deleted or moved by this document.

## Recommended Archive Categories

- Smoke outputs
- Debug outputs
- Refreshed reruns
- Old hybrid benchmark outputs
- Old `nohup` logs
- Single-seed non-final guard outputs

## Typical Examples

- `*smoke*`
- `*debug*`
- `*refreshed*`
- `hybrid_case118_N1000_seed901.*`
- `hybrid_smoke_case118_N500_seed901.*`
- `dcopf_guard_*seed901.*`
- old `*.nohup.log`

## Rationale

These artifacts were useful during development and diagnosis, but they are not required for GitHub upload once the following are preserved:

- final A1-Guard summaries
- current reports and planning documents
- source code and MATLAB wrappers

## GitHub Upload Boundary

These local artifacts are not required for GitHub upload if the final guard summaries are preserved:

- `results/final_guard/final_guard_summary_case118_lop0008_seeds901_903.csv`
- `results/final_guard/final_guard_summary_case118_lop0008_seeds901_903.md`
