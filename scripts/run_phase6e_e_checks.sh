#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6e-e-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6E_E_CHECK_TIMEOUT_SECONDS:-420}"

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
    printf '%-96s PASS\n' "$label"
  else
    printf '%-96s FAIL\n' "$label"
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

check_profile_material_policy_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; } | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^web/js/reconstruction-surface-presentation\.js$'
}

check_segmentation_surface_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; } | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^web/js/segmentation-surface-viewer\.js$'
}

check_combined_balance_no_geometry_or_io(){
  python - <<'PY'
from pathlib import Path
s=Path('web/js/reconstruction-combined-presentation.js').read_text().lower()
for token in ('fetch(', '/api/', 'marching', 'applymatrix4', 'geometry.', 'setattribute', 'setindex', 'dispose('):
    if token in s:
        raise SystemExit(1)
PY
}

check_reconstruction_mode_semantics_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; } | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^web/js/reconstruction-visualization-mode\.js$'
}

printf '%s\n' '===== PHASE 6E-E COMBINED-MODE VISUAL BALANCING ====='
run_quiet "Phase 6E-E focused unit contracts" python -m unittest -v tests.test_phase6e_e_combined_mode_visual_balancing
run_quiet "Phase 6E-E combined presentation behavior" node scripts/check_phase6e_e_combined_presentation.mjs
run_quiet "Phase 6E-E architecture probe" python scripts/check_phase6e_e_architecture.py
run_quiet "Phase 6E-D focused regression" python -m unittest -v tests.test_phase6e_d_presentation_skull_cavity_polish
run_quiet "Phase 6E-D presentation behavior regression" node scripts/check_phase6e_d_presentation_polish.mjs
run_quiet "Phase 6E-C focused regression" python -m unittest -v tests.test_phase6e_c_fidelity_profile_qualification
run_quiet "Phase 6E-C Fidelity round-trip regression" node scripts/check_phase6e_c_fidelity_profile.mjs
run_quiet "Phase 6E-B shared lighting/material regression" python -m unittest -v tests.test_phase6e_b_shared_lighting_material_foundation
run_quiet "Phase 6E-B shared presentation behavior regression" node scripts/check_phase6e_b_surface_presentation.mjs
run_quiet "Phase 6D2C combined/source regression" python -m unittest -v tests.test_phase6d2c_combined_visualization
run_quiet "Complete previous automated regression" python scripts/run_phase6e_e_previous_regression.py
run_quiet "Phase 6E-E Python compile" python -m py_compile scripts/check_phase6e_e_architecture.py scripts/run_phase6e_e_previous_regression.py tests/test_phase6e_e_combined_mode_visual_balancing.py
run_quiet "Phase 6E-E JavaScript syntax" node --check web/js/reconstruction-combined-presentation.js
run_quiet "Phase 6E-E app JavaScript syntax" node --check web/js/app.js
run_quiet "Phase 6E-E volume surface JavaScript syntax" node --check web/js/volume-surface-viewer.js
run_quiet "Phase 6E-E shell syntax" bash -n scripts/run_phase6e_e_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Validated geometry extraction implementation preservation" check_validated_geometry_extraction_untouched
run_quiet "Fidelity/Presentation material policy preservation" check_profile_material_policy_untouched
run_quiet "Segmentation surface implementation preservation" check_segmentation_surface_untouched
run_quiet "Combined balance remains geometry/I-O free" check_combined_balance_no_geometry_or_io
run_quiet "Reconstruction mode semantics implementation untouched" check_reconstruction_mode_semantics_untouched
run_quiet "Diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6E_E_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6E_E_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=fd74ea2161ea19388c7503be97b055d9d31c896a
COMBINED_BALANCE=NON_DESTRUCTIVE_DISPLAY_COMPOSITION
FIDELITY_COMBINED_VOLUME_OPACITY_MULTIPLIER=0.78
FIDELITY_COMBINED_DIRECT_CT_OPACITY=0.84
PRESENTATION_COMBINED_VOLUME_OPACITY_MULTIPLIER=0.62
PRESENTATION_COMBINED_DIRECT_CT_OPACITY=0.72
SEGMENTATION_SEMANTIC_COLORS=PRESERVED
SEGMENTATION_STRUCTURE_OPACITY=PRESERVED
USER_VOLUME_OPACITY_STATE=PRESERVED
LEAVING_COMBINED=EXACT_USER_VOLUME_OPACITY_PLUS_OPAQUE_DIRECT_CT_RESTORED
MODE_PROFILE_BALANCE_BUILDS_GEOMETRY=NO
MODE_PROFILE_BALANCE_FETCHES_GEOMETRY=NO
MODE_PROFILE_BALANCE_MUTATES_PATIENT_SPACE_GEOMETRY=NO
PHASE6D1_DEFAULT_CT_ISOVALUE_HU=300
PHASE6E_F_FINAL_REAL_STUDY_QUALIFICATION=NOT_YET_CLOSED
PHASE6F_ADVANCED_INTERACTION=NOT_ENABLED
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
