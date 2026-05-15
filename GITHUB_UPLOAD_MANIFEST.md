# GitHub Upload Manifest

## A. Files to Track in Git

- `ac_ext/*.py`
- `ac_ext/matlab/*.m`
- `ac_ext/experiments/*.py`
- `README.md`
- `requirements.txt` and/or `environment.yml` if added later
- Markdown reports and planning documents in the repository root and `docs/`
- Final result summaries in `results/final_guard/`
- Lightweight repository-organization documents such as this manifest and local archive notes

## B. Files Not to Track

- Raw training CSV data under `ac_ext/experiments/out/`
- NPZ flow matrices and other dense array artifacts
- Trained model artifacts such as `*.joblib`, `*.pkl`
- Logs and `nohup` logs
- Smoke / debug / refreshed outputs
- Old hybrid benchmark outputs
- Single-seed non-final guard outputs

## C. Large Artifacts to Keep Locally

- `ac_ext/experiments/out/ml_training_data_case118.csv`
- `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`
- `ac_ext/experiments/out/dcopf_flow_features_case118.npz`

These are derived or large local artifacts. They should remain outside the tracked Git payload and be regenerated locally or stored externally.

## D. Results to Preserve

- `results/final_guard/final_guard_summary_case118_lop0008_seeds901_903.csv`
- `results/final_guard/final_guard_summary_case118_lop0008_seeds901_903.md`

These are the repository-facing frozen A1-Guard outputs that should remain visible on GitHub.

## E. Notes

- The raw experiment output directory `ac_ext/experiments/out/` is treated as a local workspace, not a Git-tracked results store.
- Repository-facing final outputs are copied into `results/` and reports/plans are copied into `docs/`.
