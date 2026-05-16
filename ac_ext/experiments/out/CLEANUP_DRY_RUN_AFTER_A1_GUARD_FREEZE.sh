#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/lhftr/code/power-rare-events/adaptMCS-benchmarks"
cd "$ROOT"

echo "Dry run only. No file will be moved or deleted."
echo

echo "[KEEP]"
keep_paths=(
  "ac_ext/experiments/out/ml_training_data_case118.csv"
  "ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv"
  "ac_ext/experiments/out/dcopf_flow_features_case118.npz"
  "ac_ext/experiments/out/final_guard_legacy_case118_N1000_lop0008_seeds901_903.csv"
  "ac_ext/experiments/out/final_guard_legacy_case118_N1000_lop0008_seeds901_903.json"
  "ac_ext/experiments/out/final_guard_failure_label_case118_N1000_lop0008_seeds901_903.csv"
  "ac_ext/experiments/out/final_guard_failure_label_case118_N1000_lop0008_seeds901_903.json"
  "ac_ext/experiments/out/final_guard_summary_case118_lop0008_seeds901_903.csv"
  "ac_ext/experiments/out/final_guard_summary_case118_lop0008_seeds901_903.md"
  "ac_ext/experiments/out/logs/final_guard_legacy_case118_N1000_lop0008_seeds901_903.nohup.log"
  "ac_ext/experiments/out/logs/final_guard_failure_label_case118_N1000_lop0008_seeds901_903.nohup.log"
  "DCOPF_IMPLEMENTATION_AND_DIAGNOSTIC_REPORT.md"
  "ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md"
  "ac_ext/experiments/out/CANDIDATE_CLEANUP_AFTER_GUARD_FREEZE.md"
  "ac_ext/experiments/out/CLEANUP_DRY_RUN_AFTER_A1_GUARD_FREEZE.sh"
)
for path in "${keep_paths[@]}"; do
  if [[ -e "$path" ]]; then
    echo "KEEP $path"
  else
    echo "KEEP_MISSING $path"
  fi
done

echo
echo "[ARCHIVE_CANDIDATE]"
archive_patterns=(
  "ac_ext/experiments/out/dcopf_flow_score_analysis_case118_lop0008_*"
  "ac_ext/experiments/out/dcopf_flow_score_analysis_case118_all_lop_*"
  "ac_ext/experiments/out/dcopf_guard_failure_label_case118_N1000_seed901_refreshed.*"
  "ac_ext/experiments/out/dcopf_guard_legacy_case118_N1000_seed901_refreshed.*"
  "ac_ext/experiments/out/logs/dcopf_guard_failure_label_case118_N1000_seed901_refreshed.nohup.log"
  "ac_ext/experiments/out/logs/dcopf_guard_legacy_case118_N1000_seed901_refreshed.nohup.log"
)
for pattern in "${archive_patterns[@]}"; do
  mapfile -t matches < <(compgen -G "$pattern" || true)
  if [[ ${#matches[@]} -eq 0 ]]; then
    echo "ARCHIVE_NONE $pattern"
    continue
  fi
  for path in "${matches[@]}"; do
    echo "ARCHIVE $path"
  done
done

echo
echo "[DELETE_AFTER_VERIFICATION_CANDIDATE]"
delete_patterns=(
  "ac_ext/experiments/out/*smoke*"
  "ac_ext/experiments/out/*debug*"
  "ac_ext/experiments/out/hybrid_case118_N1000_seed901.*"
  "ac_ext/experiments/out/dcopf_guard_failure_label_case118_N1000_seed901.csv"
  "ac_ext/experiments/out/dcopf_guard_failure_label_case118_N1000_seed901.json"
  "ac_ext/experiments/out/dcopf_guard_legacy_case118_N1000_seed901.csv"
  "ac_ext/experiments/out/dcopf_guard_legacy_case118_N1000_seed901.json"
  "ac_ext/experiments/out/logs/*smoke*"
  "ac_ext/experiments/out/logs/*debug*"
  "ac_ext/experiments/out/logs/dcopf_guard_failure_label_case118_N1000_seed901.nohup.log"
  "ac_ext/experiments/out/logs/dcopf_guard_legacy_case118_N1000_seed901.nohup.log"
)
for pattern in "${delete_patterns[@]}"; do
  mapfile -t matches < <(compgen -G "$pattern" || true)
  if [[ ${#matches[@]} -eq 0 ]]; then
    echo "DELETE_NONE $pattern"
    continue
  fi
  for path in "${matches[@]}"; do
    echo "DELETE_AFTER_VERIFICATION $path"
  done
done

echo
echo "[NOTES]"
echo "This script does not delete or move anything."
echo "If you later want a real cleanup script, generate it from the reviewed keep/archive/delete lists."
