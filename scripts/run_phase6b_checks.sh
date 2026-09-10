#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6b-checks.XXXXXXXX)" || exit 1
FAIL=0
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-}"
CHECK_TIMEOUT_SECONDS="${PHASE6B_CHECK_TIMEOUT_SECONDS:-240}"

run_quiet() {
  local label="$1"
  shift
  local safe_label
  safe_label="$(printf '%s' "$label" | tr -cs '[:alnum:]_.-' '_')"
  local log="$LOG_DIR/${safe_label}.log"
  local rc
  if declare -F "$1" >/dev/null 2>&1; then
    "$@" >"$log" 2>&1
    rc=$?
  else
    timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1
    rc=$?
  fi
  if [[ "$rc" -eq 0 ]]; then
    printf '%-55s PASS\n' "$label"
  else
    printf '%-55s FAIL\n' "$label"
    if [[ "$rc" -eq 124 ]]; then
      printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"
    fi
    tail -n 140 "$log"
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
  if grep -Eiq '^[[:space:]]*(from|import)[[:space:]]+(skimage|trimesh|pyvista)' scripts/phase6b_surface_worker.py; then
    return 1
  fi
}

check_source_label_immutability() {
  if grep -Eiq '(save|write_bytes|tofile|open\([^)]*[wa+x]).*labels\.npy' \
    backend/voxelatlas/segmentation_surfaces.py \
    scripts/phase6a_surface_worker.py \
    scripts/phase6b_surface_worker.py; then
    return 1
  fi
}

check_accurate_reference_preserved() {
  grep -Eq 'DEFAULT_SURFACE_QUALITY = ACCURATE_SURFACE_QUALITY' backend/voxelatlas/segmentation_surfaces.py &&
  grep -Eq 'PRESENTATION_SURFACE_QUALITY = REFINED_SURFACE_QUALITY' backend/voxelatlas/segmentation_surfaces.py &&
  grep -Eq 'derived_from_accurate_surface' backend/voxelatlas/segmentation_surfaces.py &&
  grep -Eq 'ACCURATE_REFERENCE=IMMUTABLE' scripts/qualify_phase6b_real_segmentation_surface.py
}

check_phase6b_boundary() {
  if grep -Eiq 'hausdorff|export_stl|export_obj|exploded_view|presentation_profile|fidelity_profile' \
    backend/voxelatlas/segmentation_surfaces.py \
    scripts/phase6b_surface_worker.py \
    web/js/segmentation-surface-viewer.js; then
    return 1
  fi
  if grep -Eiq '(^|[^[:alnum:]_])surface_to_mask[[:space:]]*\(' \
    backend/voxelatlas/segmentation_surfaces.py \
    scripts/phase6b_surface_worker.py \
    web/js/segmentation-surface-viewer.js; then
    return 1
  fi
  grep -Eq 'surface_to_mask_deviation_qualification.*deferred_to_phase6g' \
    backend/voxelatlas/segmentation_surfaces.py
}

echo "===== PHASE 6B TOPOLOGY REPAIR AND BOUNDED SURFACE REFINEMENT VALIDATION ====="
run_quiet "Phase 6B isolated surface runtime" \
  python scripts/check_phase6a_surface_environment.py --python "$SURFACE_PYTHON"
run_quiet "Phase 6B focused unit contracts" \
  python -m unittest tests.test_phase6b_bounded_surface_refinement
run_quiet "Phase 6B architecture probe" \
  python scripts/check_phase6b_surface_architecture.py
run_quiet "Phase 6B browser refined transport contract" \
  node scripts/check_phase6b_surface_viewer.mjs
run_quiet "Phase 6A accurate-reference regression contracts" \
  python -m unittest tests.test_phase6a_accurate_patient_space_surfaces
run_quiet "Phase 5G closure regression contracts" \
  python -m unittest tests.test_phase5g_segmentation_closure
run_quiet "Phase 5F1 preview compatibility contracts" \
  python -m unittest tests.test_phase5f1_segmentation_derived_3d_surfaces
run_quiet "Complete previous automated regression" \
  python scripts/run_phase6b_previous_regression.py
run_quiet "Phase 6B Python compile" \
  python -m py_compile \
    backend/voxelatlas/segmentation_surfaces.py \
    backend/voxelatlas/app.py \
    scripts/phase6b_surface_worker.py \
    scripts/check_phase6b_surface_architecture.py \
    scripts/qualify_phase6b_real_segmentation_surface.py \
    scripts/run_phase6b_previous_regression.py \
    tests/test_phase6b_bounded_surface_refinement.py
run_quiet "Phase 6B JavaScript syntax" \
  bash -c 'node --check web/js/segmentation-surface-viewer.js && node --check web/js/app.js && node --check scripts/check_phase6b_surface_viewer.mjs'
run_quiet "Phase 6B shell syntax" bash -n scripts/run_phase6b_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy mesh runtime isolation" check_heavy_dependency_boundary
run_quiet "Canonical source-label immutability" check_source_label_immutability
run_quiet "Phase 6A accurate reference preservation" check_accurate_reference_preserved
run_quiet "Phase 6B roadmap boundary" check_phase6b_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE6B_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE6B_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_STUDY_QUALIFICATION=RUN_SEPARATELY"
echo "MANUAL_REFINED_SURFACE_REVIEW=RUN_SEPARATELY"
echo "ACCURATE_REFERENCE=IMMUTABLE"
echo "SOURCE_LABEL_MAP=IMMUTABLE"
echo "PHASE6C_PRESENTATION=NOT_ENABLED"
echo "PHASE6G_SURFACE_TO_MASK_DEVIATION=NOT_RUN"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
