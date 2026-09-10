#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6d2a-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6D2A_CHECK_TIMEOUT_SECONDS:-420}"
run_quiet(){ local label="$1"; shift; local safe log rc; safe="$(printf '%s' "$label"|tr -cs '[:alnum:]_.-' '_')"; log="$LOG_DIR/${safe}.log"; if declare -F "$1" >/dev/null 2>&1; then "$@" >"$log" 2>&1; rc=$?; else timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1; rc=$?; fi; if [[ "$rc" -eq 0 ]]; then printf '%-72s PASS\n' "$label"; else printf '%-72s FAIL\n' "$label"; [[ "$rc" -eq 124 ]] && printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"; tail -n 180 "$log"; FAIL=1; fi; }
check_patient_data_safety(){ if git ls-files --cached --others --exclude-standard | grep -Eiv '(^|/)\.env\.example$' | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2|vxvs)$|(^|/)\.env($|\.)'; then return 1; fi; }
check_6d1_implementation_untouched(){ local changed; changed="$({ git diff --name-only; git diff --cached --name-only; }|sort -u)"; ! printf '%s\n' "$changed" | grep -Eq '^(backend/voxelatlas/(volume_surfaces|volume_rendering)\.py|scripts/phase6d1_volume_surface_worker\.py|web/js/(app|volume-surface-viewer|segmentation-surface-viewer)\.js|web/index\.html|web/css/styles\.css)$'; }
check_scope_boundary(){ ! grep -Eiq 'presentation profile|fidelity profile|exploded view|hausdorff|export stl|export obj|marching_cubes' web/js/reconstruction-visualization-mode.js; }

echo "===== PHASE 6D2A VISUALIZATION-MODE CONTROLLER FOUNDATION ====="
run_quiet "Phase 6D2A focused unit contracts" python -m unittest tests.test_phase6d2a_visualization_mode_controller
run_quiet "Phase 6D2A controller behavior" node scripts/check_phase6d2a_visualization_mode_controller.mjs
run_quiet "Phase 6D2A architecture probe" python scripts/check_phase6d2a_architecture.py
run_quiet "Phase 6D1 complete regression" bash scripts/run_phase6d1_checks.sh
run_quiet "Complete previous automated regression" python scripts/run_phase6d2a_previous_regression.py
run_quiet "Phase 6D2A Python compile" python -m py_compile scripts/check_phase6d2a_architecture.py scripts/run_phase6d2a_previous_regression.py tests/test_phase6d2a_visualization_mode_controller.py
run_quiet "Phase 6D2A JavaScript syntax" bash -c 'node --check web/js/reconstruction-visualization-mode.js && node --check scripts/check_phase6d2a_visualization_mode_controller.mjs'
run_quiet "Phase 6D2A shell syntax" bash -n scripts/run_phase6d2a_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Phase 6D1 implementation preservation" check_6d1_implementation_untouched
run_quiet "Phase 6D2A roadmap boundary" check_scope_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'
printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then echo "PHASE6D2A_AUTOMATED_CHECKS_OK=YES"; else echo "PHASE6D2A_AUTOMATED_CHECKS_OK=NO"; fi
echo "EXPECTED_BASE=e96f0138bbfe55963b7069680d8ead3d641d64d7"
echo "VISUALIZATION_MODES=VOLUME,SURFACE,COMBINED"
echo "SURFACE_SOURCES=VOLUME_DERIVED,SEGMENTATION_DERIVED"
echo "MODE_SOURCE_STATE=SEPARATE"
echo "MODE_SWITCH_BUILDS_GEOMETRY=NO"
echo "VISIBLE_WORKSPACE_INTEGRATION=DEFERRED_TO_6D2B"
echo "PHASE6E_PRESENTATION_PROFILES=NOT_ENABLED"
echo "PHASE6F_ADVANCED_INTERACTION=NOT_ENABLED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
