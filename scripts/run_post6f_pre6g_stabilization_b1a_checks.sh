#!/usr/bin/env bash
# Run in the complete local GitHub checkout. No service, storage, or Git mutations.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
APP_PYTHON="${VOXELATLAS_APP_PYTHON:-$ROOT/.venv/bin/python}"
FAIL=0
run(){
  local label="$1"; shift
  printf '===== %s =====\n' "$label"
  "$@"; local rc=$?
  printf '%s_RC=%s\n' "$label" "$rc"
  if (( rc != 0 )); then FAIL=1; fi
}
run B1A_REGION_AND_LOGIN_TESTS "$SURFACE_PYTHON" -m unittest -v tests.test_post6f_pre6g_stabilization_b1a
run PRIOR_DIRECT_CT_AND_STABILIZATION_A "$APP_PYTHON" -m unittest -v tests.test_phase6d1_volume_derived_surfaces tests.test_post6f_pre6g_stabilization_a
run LOGIN_AND_WORKSPACE_REGRESSION "$APP_PYTHON" -m unittest -v tests.test_phase1c_login_ui_contract tests.test_phase2a_workspace_migration
run LOGIN_HTTP_CONTRACT "$APP_PYTHON" scripts/check_phase1c_login_ui.py
run WORKSPACE_CONTRACT "$APP_PYTHON" scripts/check_phase2a_workspace.py
run DIRECT_CT_BROWSER node scripts/check_phase6d1_volume_surface_viewer.mjs
run PYTHON_COMPILE "$SURFACE_PYTHON" -m py_compile scripts/diagnose_post6f_direct_ct_surface.py tests/test_post6f_pre6g_stabilization_b1a.py
run SHELL_SYNTAX bash -n scripts/run_post6f_pre6g_stabilization_b1a_checks.sh
run DIFF_CHECK git diff --check
printf 'STABILIZATION_B1A_AUTOMATED_CHECKS_OK=%s\n' "$([ "$FAIL" -eq 0 ] && echo YES || echo NO)"
[ "$FAIL" -eq 0 ]
