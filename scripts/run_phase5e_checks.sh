#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PHASE5E_LOG_DIR="$(mktemp -d -t voxelatlas-phase5e-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$PHASE5E_LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-46s PASS\n' "$label"
  else
    printf '%-46s FAIL\n' "$label"
    tail -n 100 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  if git ls-files | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy)$'; then
    return 1
  fi
}

check_heavy_dependency_boundary() {
  if grep -Eiq '^(torch|monai|nibabel|nnunetv2|totalsegmentator)(\[|=|<|>|$)' requirements/backend.txt; then
    return 1
  fi
  if grep -Eiq '^[[:space:]]*(from|import)[[:space:]]+(torch|nibabel|nnunetv2|totalsegmentator)' \
    backend/voxelatlas/segmentation_structures.py \
    backend/voxelatlas/segmentation_overlays.py \
    backend/voxelatlas/app.py; then
    return 1
  fi
}

check_no_phase5f_surface_work() {
  if grep -Eiq 'marching.cubes|surface.mesh|STL|GLB' \
    backend/voxelatlas/segmentation_structures.py \
    web/js/segmentation-structure-panel.js; then
    return 1
  fi
}

echo "===== PHASE 5E ANATOMICAL STRUCTURE PANEL VALIDATION ====="
run_quiet "Phase 5E unit and UI contracts" \
  python -m unittest tests.test_phase5e_anatomical_structure_panel
run_quiet "Phase 5E architecture probe" \
  python scripts/check_phase5e_structure_panel_architecture.py
run_quiet "Phase 5E browser interaction contract" \
  node scripts/check_phase5e_structure_panel.mjs
run_quiet "Phase 5D and full previous regression" \
  python scripts/run_phase5e_previous_regression.py
run_quiet "Phase 5E Python compile" \
  python -m py_compile \
    backend/voxelatlas/segmentation_structures.py \
    backend/voxelatlas/segmentation_overlays.py \
    scripts/check_phase5e_structure_panel_architecture.py \
    scripts/run_phase5e_previous_regression.py \
    tests/test_phase5e_anatomical_structure_panel.py
run_quiet "Phase 5E JavaScript syntax" \
  bash -c 'node --check web/js/app.js && node --check web/js/segmentation-overlay.js && node --check web/js/segmentation-structure-panel.js && node --check scripts/check_phase5e_structure_panel.mjs'
run_quiet "Phase 5E shell syntax" bash -n scripts/run_phase5e_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy dependency boundary" check_heavy_dependency_boundary
run_quiet "Phase 5F1 surface boundary" check_no_phase5f_surface_work
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$PHASE5E_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5E_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5E_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_STRUCTURE_PANEL=READY_FOR_MANUAL_QUALIFICATION"
echo "SOURCE_LABEL_MAP=IMMUTABLE"
echo "PHASE5F1_3D_SURFACES=NOT_ENABLED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
