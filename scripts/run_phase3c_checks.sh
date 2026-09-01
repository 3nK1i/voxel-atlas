#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local safe="${label// /_}"
  safe="${safe//\//_}"
  safe="${safe//\\/_}"
  local log="$TMP/${safe}.log"
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
    --exclude='*.png' \
    --exclude='*.glb' \
    --exclude-dir='__pycache__' \
    'cranial|aperture|cutaway|skull_open|openingSlider|openingValue' \
    web backend
}

run_em_dash_scan() {
  ! grep -RIn \
    --exclude='*.png' \
    --exclude='*.glb' \
    --exclude-dir='__pycache__' \
    '—' web backend
}

run_shell_check() {
  bash -n scripts/run_phase3c_checks.sh
}

run_diff_check() {
  git diff --check
}

echo "===== PHASE 3C COMPACT VALIDATION ====="
run_quiet "Phase 3B regression" bash scripts/run_phase3b_checks.sh
run_quiet "Canonical volume probe" python scripts/check_phase3c_canonical_volume.py
run_quiet "Phase 3C unit contract" python -m unittest tests.test_phase3c_canonical_volume_construction
run_quiet "Python compile" python -m py_compile backend/voxelatlas/app.py backend/voxelatlas/dicom_ingestion.py backend/voxelatlas/dicom_volume.py scripts/check_phase3c_canonical_volume.py tests/test_phase3c_canonical_volume_construction.py
run_quiet "JavaScript syntax" node --check web/js/app.js
run_quiet "Shell syntax" run_shell_check
run_quiet "Retired feature scan" run_retired_scan
run_quiet "Em-dash scan" run_em_dash_scan
run_quiet "Diff whitespace" run_diff_check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE3C_CANONICAL_VOLUME_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE3C_CANONICAL_VOLUME_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
