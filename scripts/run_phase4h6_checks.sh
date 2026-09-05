#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
H6_LOG_DIR="$(mktemp -d -t voxelatlas-h6-checks.XXXXXXXX)" || exit 1
FAIL=0
run_quiet() {
  local label="$1"; shift
  local log="$H6_LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-46s PASS\n' "$label"
  else
    printf '%-46s FAIL\n' "$label"
    tail -n 60 "$log"
    FAIL=1
  fi
}
echo "===== PHASE 4H6 COMPACT VALIDATION ====="
run_quiet "H6 qualification and evidence tests" python -m unittest tests.test_phase4h6_qualification tests.test_phase4h6_evidence
run_quiet "H5 and full previous regression" bash scripts/run_phase4h5_checks.sh
run_quiet "H6 repeated lifecycle probe" node scripts/check_phase4h6_qualification.mjs
run_quiet "Application JavaScript syntax" node --check web/js/app.js
run_quiet "Ray marcher JavaScript syntax" node --check web/js/patient-volume-ray-marcher.js
run_quiet "Diagnostics JavaScript syntax" node --check web/js/rendering-qualification.js
run_quiet "H6 probe JavaScript syntax" node --check scripts/check_phase4h6_qualification.mjs
run_quiet "Python compile" python -m py_compile scripts/check_phase4h6_evidence.py tests/test_phase4h6_qualification.py tests/test_phase4h6_evidence.py
run_quiet "Shell syntax" bash -n scripts/run_phase4h6_checks.sh
run_quiet "Diff whitespace" git diff --check
printf 'CHECK_LOG_DIR=%s\n' "$H6_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE4H6_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE4H6_AUTOMATED_CHECKS_OK=NO"
fi
echo "PC_RUNTIME_AND_VISUAL_ACCEPTANCE=PENDING"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
