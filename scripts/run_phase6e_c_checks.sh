#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6e-c-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6E_C_CHECK_TIMEOUT_SECONDS:-420}"

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
    printf '%-92s PASS\n' "$label"
  else
    printf '%-92s FAIL\n' "$label"
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

check_validated_geometry_extraction_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; } | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^(backend/voxelatlas/(volume_surfaces|segmentation_surfaces|volume_rendering)\.py|scripts/(phase6d1_volume_surface_worker|phase6a_surface_worker|phase6b_surface_worker)\.py|web/js/patient-volume-ray-marcher\.js)$'
}

check_profile_switch_no_geometry_or_io(){
  python - <<'PY'
from pathlib import Path
s=Path('web/js/app.js').read_text()
start=s.index('function applyReconstructionPresentationProfileSnapshot(')
end=s.index('function requestReconstructionPresentationProfile(', start)
block=s[start:end].lower()
for token in ('fetch(', '.build(', 'clearsurface', '.clear(', 'segmentation-workflow', 'setdescriptor(', 'applymatrix4', 'geometry.setattribute', 'geometry.setindex'):
    if token in block:
        raise SystemExit(1)
PY
}

check_reconstruction_mode_semantics_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; } | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^web/js/reconstruction-visualization-mode\.js$'
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

printf '%s\n' '===== PHASE 6E-C FIDELITY PROFILE QUALIFICATION ====='
run_quiet "Phase 6E-C focused unit contracts" python -m unittest -v tests.test_phase6e_c_fidelity_profile_qualification
run_quiet "Phase 6E-C Fidelity reference round-trip" node scripts/check_phase6e_c_fidelity_profile.mjs
run_quiet "Phase 6E-C architecture probe" python scripts/check_phase6e_c_architecture.py
run_quiet "Phase 6E-B shared lighting/material regression" python -m unittest -v tests.test_phase6e_b_shared_lighting_material_foundation
run_quiet "Phase 6E-B shared presentation behavior regression" node scripts/check_phase6e_b_surface_presentation.mjs
run_quiet "Phase 6E-A profile architecture regression" python -m unittest -v tests.test_phase6e_a_presentation_profile_architecture
run_quiet "Phase 6E-A controller regression" node scripts/check_phase6e_a_presentation_profile_controller.mjs
run_quiet "Phase 6D2D focused regression" python -m unittest -v tests.test_phase6d2d_reset_study_error_closure
run_quiet "Phase 6D2C combined/source regression" python -m unittest -v tests.test_phase6d2c_combined_visualization
run_quiet "Phase 6D2C controller regression" node scripts/check_phase6d2c_combined_mode.mjs
run_quiet "Phase 6D2B preserved behavior regression" check_phase6d2b_preserved
run_quiet "Phase 6D2B non-destructive visibility regression" node scripts/check_phase6d2b_nondestructive_visibility.mjs
run_quiet "Phase 6D1 volume-surface browser regression" node scripts/check_phase6d1_volume_surface_viewer.mjs
run_quiet "Phase 6C multi-structure browser regression" node scripts/check_phase6c_multi_structure_viewer.mjs
run_quiet "Complete previous automated regression" python scripts/run_phase6e_c_previous_regression.py
run_quiet "Phase 6E-C Python compile" python -m py_compile tests/test_phase6e_c_fidelity_profile_qualification.py scripts/check_phase6e_c_architecture.py scripts/run_phase6e_c_previous_regression.py
run_quiet "Phase 6E-C JavaScript syntax" bash -lc 'node --check web/js/reconstruction-surface-presentation.js && node --check web/js/reconstruction-presentation-profile.js && node --check web/js/app.js && node --check scripts/check_phase6e_c_fidelity_profile.mjs'
run_quiet "Phase 6E-C shell syntax" bash -n scripts/run_phase6e_c_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Validated geometry extraction implementation preservation" check_validated_geometry_extraction_untouched
run_quiet "Profile switching remains geometry/I-O free" check_profile_switch_no_geometry_or_io
run_quiet "Reconstruction mode semantics implementation untouched" check_reconstruction_mode_semantics_untouched
run_quiet "Diff whitespace" git diff --check

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  printf '%s\n' 'PHASE6E_C_AUTOMATED_CHECKS_OK=NO'
  exit 1
fi
printf '%s\n' 'PHASE6E_C_AUTOMATED_CHECKS_OK=YES'
printf '%s\n' 'EXPECTED_BASE=51d276b903ada7eac904b9f73f17881673d45918'
printf '%s\n' 'FIDELITY_PROFILE=DETERMINISTIC_NEUTRAL_REFERENCE'
printf '%s\n' 'FIDELITY_LIGHTING=6E_B_BASELINE_LOCKED'
printf '%s\n' 'FIDELITY_DIRECT_CT_MATERIAL=6E_B_BASELINE_LOCKED'
printf '%s\n' 'FIDELITY_SEGMENTATION_SEMANTIC_COLORS=PRESERVED'
printf '%s\n' 'FIDELITY_SEGMENTATION_STRUCTURE_OPACITY=PRESERVED'
printf '%s\n' 'RECONSTRUCTION_CARD_NONACTIVE_BORDER=UNIFORM_NEUTRAL'
printf '%s\n' 'ACTIVE_RECONSTRUCTION_MODE=ACTIVE_EMPHASIS_PLUS_SINGLE_GREEN_CHECK'
printf '%s\n' 'PROFILE_SWITCH_BUILDS_GEOMETRY=NO'
printf '%s\n' 'PROFILE_SWITCH_FETCHES_GEOMETRY=NO'
printf '%s\n' 'PROFILE_SWITCH_MUTATES_PATIENT_SPACE_GEOMETRY=NO'
printf '%s\n' 'PHASE6D1_DEFAULT_CT_ISOVALUE_HU=300'
printf '%s\n' 'PHASE6E_C_MANUAL_QUALIFICATION=REQUIRED_BEFORE_CLOSE'
printf '%s\n' 'PHASE6E_D_PRESENTATION_SKULL_CAVITY_POLISH=NOT_YET_CLOSED'
printf '%s\n' 'PHASE6F_ADVANCED_INTERACTION=NOT_ENABLED'
printf '%s\n' 'CLINICAL_VALIDATION=NOT_CLAIMED'
printf '%s\n' 'TEST_RC=0'
