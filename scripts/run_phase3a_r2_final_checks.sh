#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMPDIR_CHECKS="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_CHECKS"' EXIT
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local safe_label="${label// /_}"
  safe_label="${safe_label//\//_}"
  local log="$TMPDIR_CHECKS/${safe_label}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-43s PASS\n' "$label"
  else
    printf '%-43s FAIL\n' "$label"
    cat "$log"
    FAIL=1
  fi
}

run_diff_check() { git diff --check; }

echo "===== PHASE 3A-R2 FINAL COMPACT VALIDATION ====="
run_quiet "R2 regression" bash scripts/run_phase3a_r2_checks.sh
run_quiet "Final correction contract" python scripts/check_phase3a_r2_final_correction.py
run_quiet "Final correction unit tests" python -m unittest tests.test_phase3a_r2_final_correction
run_quiet "Python compile" python -m py_compile scripts/check_phase3a_r2_final_correction.py tests/test_phase3a_r2_final_correction.py
run_quiet "JavaScript syntax" node --check web/js/app.js
run_quiet "Shell syntax" bash -n scripts/run_phase3a_r2_final_checks.sh
run_quiet "Diff whitespace" run_diff_check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE3A_R2_FINAL_CORRECTION_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE3A_R2_FINAL_CORRECTION_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
