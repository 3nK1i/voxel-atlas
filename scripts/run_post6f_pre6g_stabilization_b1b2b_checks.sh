#!/usr/bin/env bash
# B1B2A+B: real source-bound region evidence and explicit reversible display.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
APP_PYTHON="$ROOT/.venv/bin/python"
FAIL=0
run() {
  local name="$1"; shift
  printf '\n===== %s =====\n' "$name"
  "$@"; local rc=$?
  printf '%s_RC=%s\n' "$name" "$rc"
  if [ "$rc" -ne 0 ]; then FAIL=1; fi
}
run B1B2B_SYNTHETIC_WORKER "$SURFACE_PYTHON" -m unittest -v tests.test_post6f_pre6g_stabilization_b1b2b
run B1B2B_AUTH_HTTP "$APP_PYTHON" -m unittest -v tests.test_post6f_pre6g_stabilization_b1b2b_http
run B1B2B_BROWSER_BINDING node scripts/check_post6f_pre6g_stabilization_b1b2b.mjs
run B1B2A_AND_PREVIOUS_REGRESSION bash scripts/run_post6f_pre6g_stabilization_b1b2a_checks.sh
run B1B2B_PYTHON_COMPILE "$APP_PYTHON" -m py_compile backend/voxelatlas/app.py backend/voxelatlas/volume_surfaces.py tests/test_post6f_pre6g_stabilization_b1b2b_http.py
run B1B2B_WORKER_COMPILE "$SURFACE_PYTHON" -m py_compile scripts/phase6b_direct_ct_region_worker.py tests/test_post6f_pre6g_stabilization_b1b2b.py
run B1B2B_JS_SYNTAX node --check web/js/app.js
run B1B2B_VIEWER_SYNTAX node --check web/js/volume-surface-viewer.js
run B1B2B_BROWSER_TEST_SYNTAX node --check scripts/check_post6f_pre6g_stabilization_b1b2b.mjs
run B1B2B_SHELL_SYNTAX bash -n scripts/run_post6f_pre6g_stabilization_b1b2b_checks.sh
run DIFF_CHECK git diff --check
printf '\nSTABILIZATION_B1B2B_AUTOMATED_CHECKS_OK=%s\n' "$([ "$FAIL" -eq 0 ] && echo YES || echo NO)"
[ "$FAIL" -eq 0 ]
