#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3 || command -v python)"; fi
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6j-d5b-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6J_D5B_CHECK_TIMEOUT_SECONDS:-900}"

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
    tail -n 180 "$log"
    FAIL=1
  fi
}

printf '%s\n' '===== PHASE 6J-D5B STUDY TRANSITION / STALE ASYNC ISOLATION ====='
run_quiet "D5B focused lifecycle contracts" "$PYTHON" -m unittest -v tests.test_phase6j_d5b_study_transition_lifecycle
run_quiet "D5B browser lifecycle probe" node scripts/check_phase6j_d5b_study_lifecycle.mjs
run_quiet "D5B app syntax" node --check web/js/app.js
run_quiet "D5B browser probe syntax" node --check scripts/check_phase6j_d5b_study_lifecycle.mjs
run_quiet "D5B prior reset/mode regressions" "$PYTHON" -m unittest -v \
  tests.test_phase6d2d_reset_study_error_closure \
  tests.test_phase6i_b1_automatic_direct_ct_mode \
  tests.test_phase6i_b2_existing_segmentation_mode \
  tests.test_phase6j_d45c_direct_mri_surface_ui
run_quiet "D4.5C Direct MR + CT regression" env PYTHON="$PYTHON" VOXELATLAS_SURFACE_PYTHON="$SURFACE_PYTHON" bash scripts/run_phase6j_d45c_checks.sh
run_quiet "D4 semantic MRI regression" env PYTHON="$PYTHON" VOXELATLAS_SURFACE_PYTHON="$SURFACE_PYTHON" bash scripts/run_phase6j_d4_checks.sh
run_quiet "D5B Python compile" "$PYTHON" -m py_compile tests/test_phase6j_d5b_study_transition_lifecycle.py
run_quiet "D5B shell syntax" bash -n scripts/run_phase6j_d5b_checks.sh
run_quiet "D5B whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6J_D5B_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6J_D5B_CHECKS_OK=YES
STUDY_TRANSITION_INVALIDATION=PASS
STALE_MPR_COMPLETION=GUARDED
STALE_DIRECT_SURFACE_DESCRIPTOR=GUARDED
STALE_SEGMENTATION_DESCRIPTOR=GUARDED
STALE_VOLUME_BUILD_COMPLETION=GUARDED
DIRECT_MR_BEHAVIOR=PRESERVED
DIRECT_CT_BEHAVIOR=PRESERVED
MRI_INFERENCE=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
