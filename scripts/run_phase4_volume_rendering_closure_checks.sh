#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
CLOSURE_LOG_DIR="$(mktemp -d -t voxelatlas-phase4-closure.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$CLOSURE_LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-46s PASS\n' "$label"
  else
    printf '%-46s FAIL\n' "$label"
    tail -n 80 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  if git ls-files | grep -Eiq '(^|/)(uploads?|sample_studies|patients?)(/|$)|\.(dcm|nii|nii\.gz)$'; then
    return 1
  fi
}

echo "===== PHASE 4 VOLUME RENDERING CLOSURE VALIDATION ====="
run_quiet "Phase 4 closure contract" \
  python -m unittest tests.test_phase4_volume_rendering_closure
run_quiet "Phase 4H6 and full previous regression" \
  bash scripts/run_phase4h6_checks.sh
run_quiet "Closure Python compile" \
  python -m py_compile tests/test_phase4_volume_rendering_closure.py
run_quiet "Closure shell syntax" \
  bash -n scripts/run_phase4_volume_rendering_closure_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$CLOSURE_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE4_VOLUME_RENDERING_CLOSURE_CHECKS_OK=YES"
else
  echo "PHASE4_VOLUME_RENDERING_CLOSURE_CHECKS_OK=NO"
fi
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
