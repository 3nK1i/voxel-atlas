#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6a-checks.XXXXXXXX)" || exit 1
FAIL=0
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-}"

run_quiet() {
  local label="$1"
  shift
  local safe_label
  safe_label="$(printf '%s' "$label" | tr -cs '[:alnum:]_.-' '_')"
  local log="$LOG_DIR/${safe_label}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-52s PASS\n' "$label"
  else
    printf '%-52s FAIL\n' "$label"
    tail -n 120 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  if git ls-files --cached --others --exclude-standard | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2)$'; then
    return 1
  fi
}

check_heavy_dependency_boundary() {
  if grep -Eiq '^(scikit-image|trimesh|pyvista|torch|monai|nibabel|nnunetv2|totalsegmentator)(\[|=|<|>|$)' requirements/backend.txt; then
    return 1
  fi
  if grep -Eiq '^[[:space:]]*(from|import)[[:space:]]+(skimage|trimesh|pyvista|torch|nibabel|nnunetv2|totalsegmentator)' \
    backend/voxelatlas/segmentation_surfaces.py backend/voxelatlas/app.py; then
    return 1
  fi
  grep -Eq 'from skimage.measure import marching_cubes' scripts/phase6a_surface_worker.py
}

check_source_label_immutability() {
  if grep -Eiq '(save|write_bytes|tofile|open\([^)]*[wa+x]).*labels\.npy' \
    backend/voxelatlas/segmentation_surfaces.py scripts/phase6a_surface_worker.py; then
    return 1
  fi
}

check_phase6a_boundary() {
  if grep -Eiq 'laplacian|taubin|simplify_quadric|trimesh\.smoothing|export_stl|exploded_view' \
    backend/voxelatlas/segmentation_surfaces.py \
    scripts/phase6a_surface_worker.py \
    web/js/segmentation-surface-viewer.js; then
    return 1
  fi
}

echo "===== PHASE 6A ACCURATE PATIENT-SPACE SURFACE VALIDATION ====="
run_quiet "Phase 6A isolated surface runtime" \
  python scripts/check_phase6a_surface_environment.py --python "$SURFACE_PYTHON"
run_quiet "Phase 6A focused unit contracts" \
  python -m unittest tests.test_phase6a_accurate_patient_space_surfaces
run_quiet "Phase 6A architecture probe" \
  python scripts/check_phase6a_surface_architecture.py
run_quiet "Phase 6A browser v2/v1 transport contract" \
  node scripts/check_phase6a_surface_viewer.mjs
run_quiet "Phase 5G closure regression contracts" \
  python -m unittest tests.test_phase5g_segmentation_closure
run_quiet "Phase 5F1 preview compatibility contracts" \
  python -m unittest tests.test_phase5f1_segmentation_derived_3d_surfaces
run_quiet "Complete previous automated regression" \
  python scripts/run_phase5g_previous_regression.py
run_quiet "Phase 6A Python compile" \
  python -m py_compile \
    backend/voxelatlas/config.py \
    backend/voxelatlas/segmentation_surface_runtime.py \
    backend/voxelatlas/segmentation_surfaces.py \
    backend/voxelatlas/app.py \
    scripts/phase6a_surface_worker.py \
    scripts/check_phase6a_surface_environment.py \
    scripts/check_phase6a_surface_architecture.py \
    scripts/qualify_phase6a_real_segmentation_surface.py \
    tests/test_phase6a_accurate_patient_space_surfaces.py
run_quiet "Phase 6A JavaScript syntax" \
  bash -c 'node --check web/js/segmentation-surface-viewer.js && node --check web/js/app.js && node --check scripts/check_phase6a_surface_viewer.mjs'
run_quiet "Phase 6A shell syntax" bash -n scripts/run_phase6a_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy mesh runtime isolation" check_heavy_dependency_boundary
run_quiet "Canonical source-label immutability" check_source_label_immutability
run_quiet "Phase 6A roadmap boundary" check_phase6a_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE6A_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE6A_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_STUDY_QUALIFICATION=RUN_SEPARATELY"
echo "MANUAL_SURFACE_ALIGNMENT_REVIEW=RUN_SEPARATELY"
echo "SOURCE_LABEL_MAP=IMMUTABLE"
echo "PHASE6B_REFINEMENT=NOT_ENABLED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
