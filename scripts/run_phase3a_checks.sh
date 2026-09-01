#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMPDIR_PHASE3A="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_PHASE3A"' EXIT

FAIL=0

run_quiet() {
  local label="$1"
  shift

  # Labels are user-facing and may contain path separators (for example
  # "pydicom / contract probe"). Never use the raw label as a filesystem path.
  local safe_label="${label// /_}"
  safe_label="${safe_label//\//_}"
  safe_label="${safe_label//\\/_}"

  local log="$TMPDIR_PHASE3A/${safe_label}.log"

  if "$@" >"$log" 2>&1; then
    printf '%-38s PASS\n' "$label"
  else
    printf '%-38s FAIL\n' "$label"
    cat "$log"
    FAIL=1
  fi
}

run_shell_check() {
  bash -n scripts/run_phase3a_checks.sh
}

run_diff_check() {
  git diff --check
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

echo "===== PHASE 3A COMPACT VALIDATION ====="
run_quiet "Phase 2B regression" bash scripts/run_phase2b_checks.sh
run_quiet "pydicom / contract probe" python scripts/check_phase3a_dicom_ingestion.py
run_quiet "Phase 3A unit contract" python -m unittest tests.test_phase3a_dicom_ingestion_foundation
run_quiet "Python compile" python -m py_compile backend/voxelatlas/app.py backend/voxelatlas/dicom_ingestion.py scripts/check_phase3a_dicom_ingestion.py tests/test_phase3a_dicom_ingestion_foundation.py
run_quiet "JavaScript syntax" node --check web/js/app.js
run_quiet "Shell syntax" run_shell_check
run_quiet "Retired feature scan" run_retired_scan
run_quiet "Em-dash scan" run_em_dash_scan
run_quiet "Diff whitespace" run_diff_check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE3A_DICOM_INGESTION_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE3A_DICOM_INGESTION_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
