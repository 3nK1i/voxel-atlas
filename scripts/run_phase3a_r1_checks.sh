#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMPDIR_PHASE3A_R1="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_PHASE3A_R1"' EXIT
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local safe_label="${label// /_}"
  safe_label="${safe_label//\//_}"
  safe_label="${safe_label//\\/_}"
  local log="$TMPDIR_PHASE3A_R1/${safe_label}.log"

  if "$@" >"$log" 2>&1; then
    printf '%-40s PASS\n' "$label"
  else
    printf '%-40s FAIL\n' "$label"
    cat "$log"
    FAIL=1
  fi
}

run_python_compile() {
  python -m py_compile \
    scripts/check_phase3a_r1_viewer_polish.py \
    tests/test_phase3a_r1_viewer_polish.py
}

run_shell_check() {
  bash -n scripts/run_phase3a_checks.sh scripts/run_phase3a_r1_checks.sh
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

run_diff_check() {
  git diff --check
}

echo "===== PHASE 3A-R1 COMPACT VALIDATION ====="
run_quiet "Phase 3A regression" bash scripts/run_phase3a_checks.sh
run_quiet "Viewer polish contract" python scripts/check_phase3a_r1_viewer_polish.py
run_quiet "Viewer polish unit tests" python -m unittest tests.test_phase3a_r1_viewer_polish
run_quiet "Python compile" run_python_compile
run_quiet "JavaScript syntax" node --check web/js/app.js
run_quiet "Shell syntax" run_shell_check
run_quiet "Retired feature scan" run_retired_scan
run_quiet "Em-dash scan" run_em_dash_scan
run_quiet "Diff whitespace" run_diff_check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE3A_R1_VIEWER_POLISH_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE3A_R1_VIEWER_POLISH_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
