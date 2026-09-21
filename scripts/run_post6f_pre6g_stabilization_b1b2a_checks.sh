#!/usr/bin/env bash
# B1B2A: resident display-only visibility; user repository remains uncommitted.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
FAIL=0
run() {
  local label="$1"; shift
  printf '\n===== %s =====\n' "$label"
  "$@"; local rc=$?
  printf '%s_RC=%s\n' "$label" "$rc"
  if [ "$rc" -ne 0 ]; then FAIL=1; fi
}
run B1B2A_RESIDENT_VISIBILITY node scripts/check_post6f_pre6g_stabilization_b1b2a.mjs
run B1B1_AND_PREVIOUS_REGRESSION bash scripts/run_post6f_pre6g_stabilization_b1b1_checks.sh
run B1B2A_JS_SYNTAX node --check web/js/direct-ct-region-visibility.js
run B1B2A_VIEWER_SYNTAX node --check web/js/volume-surface-viewer.js
run B1B2A_CHECK_SYNTAX node --check scripts/check_post6f_pre6g_stabilization_b1b2a.mjs
run B1B2A_SHELL_SYNTAX bash -n scripts/run_post6f_pre6g_stabilization_b1b2a_checks.sh
run DIFF_CHECK git diff --check
printf '\nSTABILIZATION_B1B2A_AUTOMATED_CHECKS_OK=%s\n' "$([ "$FAIL" -eq 0 ] && echo YES || echo NO)"
[ "$FAIL" -eq 0 ]
