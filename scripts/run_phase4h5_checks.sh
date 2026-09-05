#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
H5_LOG_DIR="$(mktemp -d -t voxelatlas-h5-checks.XXXXXXXX)"
FAIL=0
run_quiet() {
  local label="$1"; shift
  local log="$H5_LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-46s PASS\n' "$label"
  else
    printf '%-46s FAIL\n' "$label"
    tail -n 80 "$log"
    FAIL=1
  fi
}
echo "===== PHASE 4H5 COMPACT VALIDATION ====="
run_quiet "Phase 4H5 geometry and UI tests" python -m unittest tests.test_phase4h5_mpr_clipping_visualization
run_quiet "Phase 4H4 and previous checks" bash scripts/run_phase4h4_checks.sh
run_quiet "Full unit regression" python -m unittest discover -s tests -p 'test_*.py'
run_quiet "Phase 4H5 MPR clipping probe" node scripts/check_phase4h5_mpr_clipping.mjs
run_quiet "Application JavaScript syntax" node --check web/js/app.js
run_quiet "Overlay JavaScript syntax" node --check web/js/mpr-clipping-overlay.js
run_quiet "Browser probe syntax" node --check scripts/check_phase4h5_browser.mjs
run_quiet "Python compile" python -m py_compile tests/test_phase4h5_mpr_clipping_visualization.py
run_quiet "Shell syntax" bash -n scripts/run_phase4h5_checks.sh
run_quiet "Diff whitespace" git diff --check
printf 'CHECK_LOG_DIR=%s\n' "$H5_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE4H5_MPR_CLIPPING_VISUALIZATION_CHECKS_OK=YES"
else
  echo "PHASE4H5_MPR_CLIPPING_VISUALIZATION_CHECKS_OK=NO"
fi
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
