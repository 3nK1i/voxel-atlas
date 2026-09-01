#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FAIL=0

run_quiet() {
  local label="$1"; shift
  local safe="${label// /_}"; safe="${safe//\//_}"
  local log="$TMP/${safe}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-44s PASS\n' "$label"
  else
    printf '%-44s FAIL\n' "$label"
    cat "$log"
    FAIL=1
  fi
}

run_shell() {
  bash -n \
    scripts/run_phase3d_r2_final_checks.sh \
    scripts/run_phase3d_r21_checks.sh
}

run_retired() {
  ! grep -RInE \
    --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' \
    'cranial|aperture|cutaway|skull_open|openingSlider|openingValue' web backend
}

run_dash() {
  ! grep -RIn \
    --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' \
    '—' web backend
}

echo "===== PHASE 3D-R2.1 COMPACT VALIDATION ====="
run_quiet "Phase 3D-R2 regression" bash scripts/run_phase3d_r2_final_checks.sh
run_quiet "Crosshair / CTA probe" python scripts/check_phase3d_r21_crosshair_cta.py
run_quiet "Crosshair / CTA unit contract" python -m unittest tests.test_phase3d_r21_crosshair_cta_polish
run_quiet "Python compile" python -m py_compile scripts/check_phase3d_r21_crosshair_cta.py tests/test_phase3d_r21_crosshair_cta_polish.py
run_quiet "JavaScript syntax" node --check web/js/app.js
run_quiet "Shell syntax" run_shell
run_quiet "Retired feature scan" run_retired
run_quiet "Em-dash scan" run_dash
run_quiet "Diff whitespace" git diff --check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE3D_R21_PHASE3_CLOSURE_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE3D_R21_PHASE3_CLOSURE_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
