#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3 || command -v python)"; fi
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6j-d5c-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6J_D5C_CHECK_TIMEOUT_SECONDS:-900}"

run_quiet(){
  local label="$1"; shift
  local safe log rc
  safe="$(printf '%s' "$label" | tr -cs '[:alnum:]_.-' '_')"
  log="$LOG_DIR/${safe}.log"
  timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1
  rc=$?
  if [[ "$rc" -eq 0 ]]; then
    printf '%-96s PASS\n' "$label"
  else
    printf '%-96s FAIL\n' "$label"
    [[ "$rc" -eq 124 ]] && printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"
    tail -n 200 "$log"
    FAIL=1
  fi
}

printf '%s\n' '===== PHASE 6J-D5C SAME-STUDY DIRECT / SEMANTIC LIFECYCLE ====='
run_quiet "D5C focused same-study contracts" "$PYTHON" -m unittest -v tests.test_phase6j_d5c_same_study_surface_lifecycle
run_quiet "D5C browser lifecycle probe" node scripts/check_phase6j_d5c_same_study_lifecycle.mjs
run_quiet "D5C app syntax" node --check web/js/app.js
run_quiet "D5C browser probe syntax" node --check scripts/check_phase6j_d5c_same_study_lifecycle.mjs
run_quiet "D5B full lifecycle regression" env PYTHON="$PYTHON" VOXELATLAS_SURFACE_PYTHON="$SURFACE_PYTHON" bash scripts/run_phase6j_d5b_checks.sh
run_quiet "D5C Python compile" "$PYTHON" -m py_compile tests/test_phase6j_d5c_same_study_surface_lifecycle.py tests/test_phase6j_d5b_study_transition_lifecycle.py
run_quiet "D5C shell syntax" bash -n scripts/run_phase6j_d5c_checks.sh
run_quiet "D5C whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6J_D5C_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6J_D5C_CHECKS_OK=YES
SAME_STUDY_DIRECT_SEMANTIC_COEXISTENCE=PASS
DIRECT_SELECTION_IN_ACTIVE_SURFACE_MODE=PREPARES_ON_DEMAND
VOLUME_MODE_SELECTION=INTENT_ONLY
RESIDENT_DIRECT_GEOMETRY=REUSED
RESIDENT_SEGMENTATION_GEOMETRY=PRESERVED
MODE_TRANSITIONS=PRESENTATION_ONLY
D5B_STUDY_ISOLATION=PRESERVED
DIRECT_MR_BEHAVIOR=PRESERVED
DIRECT_CT_BEHAVIOR=PRESERVED
MRI_INFERENCE=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
