#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
LOG_DIR="$(mktemp -d -t voxelatlas-phase5f1-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$LOG_DIR/${label// /_}.log"
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
    backend/voxelatlas/segmentation_surfaces.py \
    backend/voxelatlas/app.py; then
    return 1
  fi
}

check_phase6_boundary() {
  if grep -Eiq 'laplacian|taubin|decimat|topology.repair|export.(stl|glb)' \
    backend/voxelatlas/segmentation_surfaces.py \
    web/js/segmentation-surface-viewer.js; then
    return 1
  fi
}

echo "===== PHASE 5F1 SEGMENTATION-DERIVED 3D SURFACE VALIDATION ====="
run_quiet "Phase 5F1 unit and HTTP contracts" \
  python -m unittest tests.test_phase5f1_segmentation_derived_3d_surfaces
run_quiet "Phase 5F1 architecture probe" \
  python scripts/check_phase5f1_segmentation_surface_architecture.py
run_quiet "Phase 5F1 browser surface contract" \
  node scripts/check_phase5f1_surface_viewer.mjs
run_quiet "Phase 5E and full previous regression" \
  python scripts/run_phase5f1_previous_regression.py
run_quiet "Phase 5F1 Python compile" \
  python -m py_compile \
    backend/voxelatlas/segmentation_surfaces.py \
    backend/voxelatlas/app.py \
    scripts/check_phase5f1_segmentation_surface_architecture.py \
    scripts/qualify_phase5f1_real_segmentation_surface.py \
    scripts/run_phase5f1_previous_regression.py \
    tests/test_phase5f1_segmentation_derived_3d_surfaces.py
run_quiet "Phase 5F1 JavaScript syntax" \
  bash -c 'node --check web/js/app.js && node --check web/js/segmentation-surface-viewer.js && node --check scripts/check_phase5f1_surface_viewer.mjs'
run_quiet "Phase 5F1 shell syntax" bash -n scripts/run_phase5f1_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy dependency boundary" check_heavy_dependency_boundary
run_quiet "Phase 6 refinement boundary" check_phase6_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5F1_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5F1_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_3D_SEGMENTATION_SURFACE=RUN_SEPARATELY"
echo "COMBINED_SURFACE_VOLUME=READY_FOR_MANUAL_QUALIFICATION"
echo "SOURCE_LABEL_MAP=IMMUTABLE"
echo "SURFACE_REFINEMENT=DEFERRED_TO_PHASE6"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
