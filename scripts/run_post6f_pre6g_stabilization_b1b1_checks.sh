#!/usr/bin/env bash
# B1B1: synthetic, source-only association; no patient files, service, or Git mutations.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
FAIL=0
run() {
  local name="$1"; shift
  printf '\n===== %s =====\n' "$name"
  "$@"; local rc=$?
  printf '%s_RC=%s\n' "$name" "$rc"
  if [ "$rc" -ne 0 ]; then FAIL=1; fi
}
run B1B1_SYNTHETIC_TRIANGLE_ASSOCIATION "$SURFACE_PYTHON" -m unittest -v tests.test_post6f_pre6g_stabilization_b1b1
run B1A_AND_PREVIOUS_REGRESSION bash scripts/run_post6f_pre6g_stabilization_b1a_checks.sh
run DIRECT_CT_VIEWER_REGRESSION node scripts/check_phase6d1_volume_surface_viewer.mjs
run B1B1_PYTHON_COMPILE "$SURFACE_PYTHON" -m py_compile backend/voxelatlas/direct_ct_surface_regions.py tests/test_post6f_pre6g_stabilization_b1b1.py
run B1B1_BASH_SYNTAX bash -n scripts/run_post6f_pre6g_stabilization_b1b1_checks.sh
run DIFF_CHECK git diff --check
printf '\nSTABILIZATION_B1B1_AUTOMATED_CHECKS_OK=%s\n' "$([ "$FAIL" -eq 0 ] && echo YES || echo NO)"
[ "$FAIL" -eq 0 ]
