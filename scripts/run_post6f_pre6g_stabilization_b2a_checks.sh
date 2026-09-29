#!/usr/bin/env bash
# B2A: display-only segmentation face orientation under the fixed LPS->viewer reflection.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
FAIL=0
run() {
  local name="$1"; shift
  printf '\n===== %s =====\n' "$name"
  "$@"
  local rc=$?
  printf '%s_RC=%s\n' "$name" "$rc"
  if [ "$rc" -ne 0 ]; then FAIL=1; fi
}
run B2A_WINDING node scripts/check_post6f_pre6g_stabilization_b2a_winding.mjs
run PHASE6A_SEGMENTATION_DECODE node scripts/check_phase6a_surface_viewer.mjs
run PHASE6C_SEGMENTATION_RESIDENCY node scripts/check_phase6c_multi_structure_viewer.mjs
run PHASE6B_REFINED_FALLBACK node scripts/check_phase6b_refined_surface_fallback.mjs
run PHASE6E_B_MATERIAL node scripts/check_phase6e_b_surface_presentation.mjs
run PHASE6E_C_FIDELITY node scripts/check_phase6e_c_fidelity_profile.mjs
run PHASE6E_D_PRESENTATION node scripts/check_phase6e_d_presentation_polish.mjs
run PHASE6F_B_VISIBILITY node scripts/check_phase6f_b_visibility_isolation.mjs
run PHASE6F_C_TRANSPARENCY node scripts/check_phase6f_c_transparency.mjs
run PHASE6F_D_CLIPPING node scripts/check_phase6f_d_clipping.mjs
run PHASE6F_E_EXPLOSION node scripts/check_phase6f_e_exploded_presentation.mjs
run DIRECT_CT_REGION_BROWSER node scripts/check_post6f_pre6g_stabilization_b1b2b.mjs
run PHASE6E_D_PYTHON python3 -m unittest discover -s tests -p 'test_phase6e_d_presentation_skull_cavity_polish.py' -q
run PHASE6E_B_PYTHON python3 -m unittest discover -s tests -p 'test_phase6e_b_shared_lighting_material_foundation.py' -q
run PHASE6F_C_PYTHON python3 -m unittest discover -s tests -p 'test_phase6f_c_structure_transparency_robustness.py' -q
run B2A_JS_SYNTAX node --check web/js/segmentation-surface-viewer.js
run B2A_HELPER_SYNTAX node --check web/js/segmentation-viewer-winding.js
run B2A_TEST_SYNTAX node --check scripts/check_post6f_pre6g_stabilization_b2a_winding.mjs
run B2A_SHELL_SYNTAX bash -n scripts/run_post6f_pre6g_stabilization_b2a_checks.sh
run DIFF_CHECK git diff --check
printf '\nSTABILIZATION_B2A_AUTOMATED_CHECKS_OK=%s\n' "$([ "$FAIL" -eq 0 ] && echo YES || echo NO)"
[ "$FAIL" -eq 0 ]
