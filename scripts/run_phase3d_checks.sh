#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMPDIR_PHASE3D="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_PHASE3D"' EXIT
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local safe_label="${label// /_}"
  safe_label="${safe_label//\//_}"
  safe_label="${safe_label//\\/_}"
  local log="$TMPDIR_PHASE3D/${safe_label}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-43s PASS\n' "$label"
  else
    printf '%-43s FAIL\n' "$label"
    cat "$log"
    FAIL=1
  fi
}

run_retired_scan() {
  ! grep -RInE \
    --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' \
    'cranial|aperture|cutaway|skull_open|openingSlider|openingValue' web backend
}

run_em_dash_scan() {
  ! grep -RIn --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' '—' web backend
}

echo "===== PHASE 3D COMPACT VALIDATION ====="
run_quiet "Phase 3C regression" bash scripts/run_phase3c_checks.sh
run_quiet "Patient-space MPR probe" python scripts/check_phase3d_mpr.py
run_quiet "Phase 3D unit contract" python -m unittest tests.test_phase3d_real_mpr_integration
run_quiet "Full unit suite" python -m unittest discover -s tests
run_quiet "Python compile" python -m py_compile backend/voxelatlas/app.py backend/voxelatlas/dicom_mpr.py scripts/check_phase3d_mpr.py tests/test_phase3d_real_mpr_integration.py
run_quiet "JavaScript syntax" node --check web/js/app.js
run_quiet "Shell syntax" bash -n scripts/run_phase3d_checks.sh
run_quiet "Retired feature scan" run_retired_scan
run_quiet "Em-dash scan" run_em_dash_scan
run_quiet "Diff whitespace" git diff --check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE3D_REAL_MPR_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE3D_REAL_MPR_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
