#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6c-checks.XXXXXXXX)" || exit 1
FAIL=0
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-}"
CHECK_TIMEOUT_SECONDS="${PHASE6C_CHECK_TIMEOUT_SECONDS:-300}"

run_quiet() {
  local label="$1"
  shift
  local safe_label log rc
  safe_label="$(printf '%s' "$label" | tr -cs '[:alnum:]_.-' '_')"
  log="$LOG_DIR/${safe_label}.log"
  if declare -F "$1" >/dev/null 2>&1; then
    "$@" >"$log" 2>&1
    rc=$?
  else
    timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1
    rc=$?
  fi
  if [[ "$rc" -eq 0 ]]; then
    printf '%-58s PASS\n' "$label"
  else
    printf '%-58s FAIL\n' "$label"
    if [[ "$rc" -eq 124 ]]; then
      printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"
    fi
    tail -n 160 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  if git ls-files --cached --others --exclude-standard | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2)$'; then
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

check_phase6ab_geometry_untouched() {
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; } | sort -u)"
  if printf '%s\n' "$changed" | grep -Eq '^backend/voxelatlas/segmentation_surfaces\.py$|^scripts/phase6[ab]_surface_worker\.py$'; then
    return 1
  fi
  grep -Eq 'DEFAULT_SURFACE_QUALITY = ACCURATE_SURFACE_QUALITY' backend/voxelatlas/segmentation_surfaces.py &&
  grep -Eq 'PRESENTATION_SURFACE_QUALITY = REFINED_SURFACE_QUALITY' backend/voxelatlas/segmentation_surfaces.py &&
  grep -Eq 'derived_from_accurate_surface' backend/voxelatlas/segmentation_surfaces.py
}

check_phase6c_boundary() {
  if grep -Eiq 'start segmentation|volume-derived surface|custom hu|presentation profile|fidelity profile|exploded view|export stl|export obj|hausdorff' \
    web/js/segmentation-surface-viewer.js \
    web/js/segmentation-structure-panel.js \
    web/js/app.js \
    web/index.html; then
    return 1
  fi
  if grep -Eiq 'marching_cubes|smooth_bounded|cluster_candidate' web/js/segmentation-surface-viewer.js; then
    return 1
  fi
}

echo "===== PHASE 6C POLISHED MULTI-STRUCTURE PRESENTATION VALIDATION ====="
run_quiet "Phase 6C isolated surface runtime" \
  python scripts/check_phase6a_surface_environment.py --python "$SURFACE_PYTHON"
run_quiet "Phase 6C focused unit contracts" \
  python -m unittest tests.test_phase6c_polished_multi_structure_presentation
run_quiet "Phase 6C architecture probe" \
  python scripts/check_phase6c_presentation_architecture.py
run_quiet "Phase 6C browser multi-structure contract" \
  node scripts/check_phase6c_multi_structure_viewer.mjs
run_quiet "Phase 6B architecture regression" \
  python scripts/check_phase6b_surface_architecture.py
run_quiet "Phase 6B browser regression" \
  node scripts/check_phase6b_surface_viewer.mjs
run_quiet "Phase 5E structure-panel regression contracts" \
  python -m unittest tests.test_phase5e_anatomical_structure_panel
run_quiet "Complete previous automated regression" \
  python scripts/run_phase6c_previous_regression.py
run_quiet "Phase 6C Python compile" \
  python -m py_compile \
    scripts/check_phase6c_presentation_architecture.py \
    scripts/qualify_phase6c_real_multi_structure_surface_set.py \
    scripts/run_phase6c_previous_regression.py \
    tests/test_phase6c_polished_multi_structure_presentation.py
run_quiet "Phase 6C JavaScript syntax" \
  bash -c 'node --check web/js/segmentation-surface-viewer.js && node --check web/js/segmentation-structure-panel.js && node --check web/js/app.js && node --check scripts/check_phase6c_multi_structure_viewer.mjs'
run_quiet "Phase 6C shell syntax" bash -n scripts/run_phase6c_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Canonical source-label immutability" check_source_label_immutability
run_quiet "Phase 6A/6B geometry preservation" check_phase6ab_geometry_untouched
run_quiet "Phase 6C roadmap boundary" check_phase6c_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE6C_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE6C_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_MULTI_STRUCTURE_QUALIFICATION=RUN_SEPARATELY"
echo "MANUAL_MULTI_STRUCTURE_PRESENTATION_REVIEW=RUN_SEPARATELY"
echo "PHASE6A_ACCURATE_REFERENCE=IMMUTABLE"
echo "PHASE6B_REFINED_GEOMETRY=PRESERVED"
echo "SOURCE_LABEL_MAP=IMMUTABLE"
echo "PHASE6D_WORKFLOW=NOT_ENABLED"
echo "PHASE6F_ADVANCED_MULTI_ISOLATION=NOT_ENABLED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
