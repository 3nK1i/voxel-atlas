#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6e-a-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6E_A_CHECK_TIMEOUT_SECONDS:-420}"

run_quiet(){
  local label="$1"; shift
  local safe log rc
  safe="$(printf '%s' "$label" | tr -cs '[:alnum:]_.-' '_')"
  log="$LOG_DIR/${safe}.log"
  if declare -F "$1" >/dev/null 2>&1; then
    "$@" >"$log" 2>&1
    rc=$?
  else
    timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1
    rc=$?
  fi
  if [[ "$rc" -eq 0 ]]; then
    printf '%-84s PASS\n' "$label"
  else
    printf '%-84s FAIL\n' "$label"
    [[ "$rc" -eq 124 ]] && printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"
    tail -n 180 "$log"
    FAIL=1
  fi
}

check_patient_data_safety(){
  if git ls-files --cached --others --exclude-standard \
    | grep -Eiv '(^|/)\.env\.example$' \
    | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2|vxvs)$|(^|/)\.env($|\.)'; then
    return 1
  fi
}

check_geometry_implementation_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; } | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^(backend/voxelatlas/(volume_surfaces|segmentation_surfaces|volume_rendering)\.py|scripts/(phase6d1_volume_surface_worker|phase6a_surface_worker|phase6b_surface_worker)\.py|web/js/(volume-surface-viewer|segmentation-surface-viewer|patient-volume-ray-marcher)\.js)$'
}


check_phase6d2b_preserved(){
  python -m unittest \
    tests.test_phase6d2b_volume_surface_transitions.Phase6D2BVolumeSurfaceTransitionTests.test_app_wires_controller_to_non_destructive_layer_visibility \
    tests.test_phase6d2b_volume_surface_transitions.Phase6D2BVolumeSurfaceTransitionTests.test_mode_switch_does_not_build_or_clear_surface_geometry \
    tests.test_phase6d2b_volume_surface_transitions.Phase6D2BVolumeSurfaceTransitionTests.test_volume_surface_layer_has_non_destructive_presentation_visibility \
    tests.test_phase6d2b_volume_surface_transitions.Phase6D2BVolumeSurfaceTransitionTests.test_segmentation_surface_layer_visibility_does_not_abort_pending_work \
    tests.test_phase6d2b_volume_surface_transitions.Phase6D2BVolumeSurfaceTransitionTests.test_volume_opacity_remains_part_of_volume_visibility_policy \
    tests.test_phase6d2b_volume_surface_transitions.Phase6D2BVolumeSurfaceTransitionTests.test_building_surface_does_not_implicitly_change_visualization_mode \
    tests.test_phase6d2b_volume_surface_transitions.Phase6D2BVolumeSurfaceTransitionTests.test_phase6d1_300_hu_baseline_and_later_phase_boundaries_remain_intact
}
check_profile_switch_no_geometry_or_io(){
  python - <<'PY'
from pathlib import Path
s=Path('web/js/app.js').read_text()
start=s.index('function applyReconstructionPresentationProfileSnapshot(')
end=s.index('function applyReconstructionVisualizationSnapshot(', start)
block=s[start:end].lower()
raise SystemExit(1 if any(token in block for token in ('fetch(', '.build(', 'clearsurface', 'segmentation-workflow', 'material', 'light')) else 0)
PY
}

printf '%s\n' '===== PHASE 6E-A FIDELITY / PRESENTATION PROFILE ARCHITECTURE ====='
run_quiet "Phase 6E-A focused unit contracts" python -m unittest -v tests.test_phase6e_a_presentation_profile_architecture
run_quiet "Phase 6E-A profile controller behavior" node scripts/check_phase6e_a_presentation_profile_controller.mjs
run_quiet "Phase 6E-A architecture probe" python scripts/check_phase6e_a_architecture.py
run_quiet "Phase 6D2D focused regression" python -m unittest -v tests.test_phase6d2d_reset_study_error_closure
run_quiet "Phase 6D2C focused regression" python -m unittest -v tests.test_phase6d2c_combined_visualization
run_quiet "Phase 6D2B preserved behavior regression" check_phase6d2b_preserved
run_quiet "Phase 6D2A focused regression" python -m unittest -v tests.test_phase6d2a_visualization_mode_controller
run_quiet "Complete previous automated regression" python scripts/run_phase6e_a_previous_regression.py
run_quiet "Phase 6E-A Python compile" python -m py_compile tests/test_phase6e_a_presentation_profile_architecture.py scripts/check_phase6e_a_architecture.py scripts/run_phase6e_a_previous_regression.py
run_quiet "Phase 6E-A JavaScript syntax" bash -lc 'node --check web/js/reconstruction-presentation-profile.js && node --check web/js/app.js'
run_quiet "Phase 6E-A shell syntax" bash -n scripts/run_phase6e_a_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Validated geometry implementation preservation" check_geometry_implementation_untouched
run_quiet "Profile switching performs no geometry work or I/O" check_profile_switch_no_geometry_or_io
run_quiet "Diff whitespace" git diff --check

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  printf '%s\n' 'PHASE6E_A_AUTOMATED_CHECKS_OK=NO'
  exit 1
fi
printf '%s\n' 'PHASE6E_A_AUTOMATED_CHECKS_OK=YES'
printf '%s\n' 'EXPECTED_BASE=a7b8637460bc3c5ae657b4fd5ef8a8d5199ee474'
printf '%s\n' 'PRESENTATION_PROFILES=FIDELITY,PRESENTATION'
printf '%s\n' 'DEFAULT_PROFILE=FIDELITY'
printf '%s\n' 'PROFILE_STATE=SEPARATE_FROM_VISUALIZATION_MODE_AND_SURFACE_SOURCE'
printf '%s\n' 'PROFILE_SWITCH_BUILDS_GEOMETRY=NO'
printf '%s\n' 'PROFILE_SWITCH_FETCHES_GEOMETRY=NO'
printf '%s\n' 'PROFILE_SWITCH_MUTATES_GEOMETRY=NO'
printf '%s\n' 'LIGHTING_MATERIAL_VALUES=DEFERRED_TO_6E_B'
printf '%s\n' 'PHASE6D1_DEFAULT_CT_ISOVALUE_HU=300'
printf '%s\n' 'PHASE6F_ADVANCED_INTERACTION=NOT_ENABLED'
printf '%s\n' 'CLINICAL_VALIDATION=NOT_CLAIMED'
printf '%s\n' 'TEST_RC=0'
