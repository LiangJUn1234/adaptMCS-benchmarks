#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PARENT="$(cd "$ROOT_DIR/.." && pwd)"
REPORT_DIR="$PROJECT_PARENT/report"
OUT_DIR="$ROOT_DIR/ac_ext/experiments/out"
MATPOWER_DIR="$PROJECT_PARENT/matpower"
PREFERRED_PYTHON="/home/lhftr/venv310/bin/python"

status_ok=0
status_warn=0
status_fail=0
matlab_python_import_available=0
python_for_matlab_check=""

say() {
  printf '%s\n' "${1-}"
}

ok() {
  status_ok=$((status_ok + 1))
  printf '[OK] %s\n' "$1"
}

warn() {
  status_warn=$((status_warn + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  status_fail=$((status_fail + 1))
  printf '[FAIL] %s\n' "$1"
}

check_file() {
  local path="$1"
  local label="$2"
  if [ -f "$path" ]; then
    ok "$label: $path"
  else
    fail "$label missing: $path"
  fi
}

check_dir() {
  local path="$1"
  local label="$2"
  if [ -d "$path" ]; then
    ok "$label: $path"
  else
    fail "$label missing: $path"
  fi
}

check_optional_dir() {
  local path="$1"
  local label="$2"
  if [ -d "$path" ]; then
    ok "$label: $path"
  else
    warn "$label not present: $path"
  fi
}

check_optional_file() {
  local path="$1"
  local label="$2"
  if [ -f "$path" ]; then
    ok "$label: $path"
  else
    warn "$label not present: $path"
  fi
}

say "== Restore / Continue Status Check =="
say "repo root: $ROOT_DIR"
say

check_dir "$ROOT_DIR/.git" "git repository"
check_file "$ROOT_DIR/README.md" "repository README"
check_file "$ROOT_DIR/MIGRATION_AND_REPRO_CHECKLIST.md" "migration checklist"
check_file "$ROOT_DIR/ARTIFACT_REGISTRY_AND_RETENTION_PLAN.md" "artifact registry"
check_dir "$ROOT_DIR/docs/report_package" "repository-local report snapshot"
check_optional_dir "$REPORT_DIR" "outer standalone report package"

say
say "== Stage Documents =="
check_file "$ROOT_DIR/DCOPF_IMPLEMENTATION_AND_DIAGNOSTIC_REPORT.md" "DCOPF diagnostic report"
check_file "$ROOT_DIR/ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md" "A2 training plan"
check_file "$ROOT_DIR/A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md" "A4 prep plan"
check_file "$ROOT_DIR/PROJECT_STAGE_CONTINUITY_A1_TO_A2.md" "continuity note"

say
say "== Frozen Result Summaries =="
check_optional_file "$ROOT_DIR/results/final_guard/final_guard_summary_case118_lop0008_seeds901_903.csv" "tracked final guard summary csv"
check_optional_file "$ROOT_DIR/results/final_guard/final_guard_summary_case118_lop0008_seeds901_903.md" "tracked final guard summary md"
check_optional_file "$OUT_DIR/final_guard_summary_case118_lop0008_seeds901_903.csv" "local final guard summary csv"
check_optional_file "$OUT_DIR/final_guard_summary_case118_lop0008_seeds901_903.md" "local final guard summary md"

say
say "== Local Essential Artifacts =="
check_optional_file "$OUT_DIR/ml_training_data_case118.csv" "ACOPF label table"
check_optional_file "$OUT_DIR/ml_training_data_with_dcopf_case118.csv" "DCOPF-augmented label table"
check_optional_file "$OUT_DIR/dcopf_flow_features_case118.npz" "DCOPF flow feature matrix"

say
say "== Python Environment =="
if [ -x "$PREFERRED_PYTHON" ]; then
  ok "preferred interpreter found: $PREFERRED_PYTHON"
  python_for_matlab_check="$PREFERRED_PYTHON"
else
  warn "preferred interpreter not found: $PREFERRED_PYTHON"
fi

if command -v python3 >/dev/null 2>&1; then
  ok "python3 available: $(command -v python3)"
  if [ -z "$python_for_matlab_check" ]; then
    python_for_matlab_check="$(command -v python3)"
  fi
else
  fail "python3 not available on PATH"
fi

say
say "== MATLAB / MATPOWER =="
if command -v matlab >/dev/null 2>&1; then
  ok "MATLAB executable available: $(command -v matlab)"
else
  warn "MATLAB executable not available on PATH"
fi

check_optional_dir "$MATPOWER_DIR" "MATPOWER sibling directory"

if [ -n "$python_for_matlab_check" ]; then
  if "$python_for_matlab_check" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys
sys.exit(0 if importlib.util.find_spec("matlab") else 1)
PY
  then
    matlab_python_import_available=1
    ok "Python matlab package import is available via: $python_for_matlab_check"
  else
    warn "Python matlab package import is not available via: $python_for_matlab_check"
  fi
fi

say
say "== Stage Assessment =="
level1_ready=0
level2_ready=0
level3_ready=0

if [ -f "$ROOT_DIR/MIGRATION_AND_REPRO_CHECKLIST.md" ] \
  && [ -d "$ROOT_DIR/docs/report_package" ] \
  && [ -f "$ROOT_DIR/A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md" ]; then
  level1_ready=1
fi

if [ "$level1_ready" -eq 1 ] \
  && [ -f "$OUT_DIR/ml_training_data_case118.csv" ] \
  && [ -f "$OUT_DIR/ml_training_data_with_dcopf_case118.csv" ] \
  && [ -f "$OUT_DIR/dcopf_flow_features_case118.npz" ]; then
  level2_ready=1
fi

if [ "$level2_ready" -eq 1 ] \
  && [ -n "$python_for_matlab_check" ] \
  && command -v matlab >/dev/null 2>&1 \
  && [ -d "$MATPOWER_DIR" ] \
  && [ "$matlab_python_import_available" -eq 1 ]; then
  level3_ready=1
fi

if [ "$level3_ready" -eq 1 ]; then
  ok "Level 3 ready: benchmark reproduction is plausibly available"
elif [ "$level2_ready" -eq 1 ]; then
  ok "Level 2 ready: offline continuation is available"
elif [ "$level1_ready" -eq 1 ]; then
  ok "Level 1 ready: documentation / design continuation is available"
else
  fail "Level 1 is not fully restored yet"
fi

say
say "== Recommended Next Step =="
if [ "$level3_ready" -eq 1 ]; then
  say "Current status supports code, reports, offline analysis, and likely benchmark work."
  say "Recommended next research step: continue A4 certificate-aware / parameterized DCOPF preparation."
elif [ "$level2_ready" -eq 1 ]; then
  say "Current status supports offline continuation."
  say "Recommended next step: use the frozen A1/A2 baseline and continue A4-prep, not old A2 grid expansion."
elif [ "$level1_ready" -eq 1 ]; then
  say "Current status supports reading, planning, and report-based handoff."
  say "Recommended next step: restore the three essential local artifacts before attempting offline reruns."
else
  say "Current status is incomplete."
  say "Recommended next step: restore repository docs first, then essential artifacts, then environment."
fi

say
say "Read first:"
say "  1. docs/report_package/00_overall/OVERALL_SUMMARY_README.md"
say "  2. MIGRATION_AND_REPRO_CHECKLIST.md"
say "  3. ARTIFACT_REGISTRY_AND_RETENTION_PLAN.md"
say "  4. A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md"

say
say "Counters: ok=$status_ok warn=$status_warn fail=$status_fail"

if [ "$status_fail" -gt 0 ]; then
  exit 1
fi

exit 0
