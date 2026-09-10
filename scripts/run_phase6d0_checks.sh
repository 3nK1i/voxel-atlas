#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6d0-checks.XXXXXXXX)" || exit 1
FAIL=0
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-}"
CHECK_TIMEOUT_SECONDS="${PHASE6D0_CHECK_TIMEOUT_SECONDS:-300}"

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
    printf '%-64s PASS\n' "$label"
  else
    printf '%-64s FAIL\n' "$label"
    if [[ "$rc" -eq 124 ]]; then
      printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"
    fi
    tail -n 180 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  if git ls-files --cached --others --exclude-standard \
    | grep -Eiv '(^|/)\.env\.example$' \
    | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2)$|(^|/)\.env($|\.)'; then
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

check_phase6d0_boundary() {
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; } | sort -u)"
  if printf '%s\n' "$changed" | grep -Eq '^backend/voxelatlas/segmentation_surfaces\.py$|^scripts/phase6[ab]_surface_worker\.py$'; then
    return 1
  fi
  if grep -Eiq 'volume-derived surface|custom hu|surface source selector|presentation profile|fidelity profile|exploded view|export stl|export obj|hausdorff' \
    backend/voxelatlas/segmentation_workflow.py \
    web/js/segmentation-workflow-panel.js \
    web/js/app.js \
    web/index.html; then
    return 1
  fi
}

echo "===== PHASE 6D0 ON-DEMAND SEGMENTATION WORKFLOW VALIDATION ====="
run_quiet "Phase 6D0 focused unit contracts" \
  python -m unittest tests.test_phase6d0_on_demand_segmentation_workflow
run_quiet "Phase 6D0 architecture probe" \
  python scripts/check_phase6d0_on_demand_architecture.py
run_quiet "Phase 6D0 browser workflow contract" \
  node scripts/check_phase6d0_segmentation_workflow_panel.mjs
run_quiet "Phase 5A provider-neutral segmentation regression" \
  python -m unittest tests.test_phase5a_segmentation_architecture
run_quiet "Phase 5B2 TotalSegmentator execution contract regression" \
  python -m unittest tests.test_phase5b2_totalsegmentator_execution
run_quiet "Phase 5C canonical label-map regression" \
  python -m unittest tests.test_phase5c_canonical_label_map_import
run_quiet "Phase 5D synchronized overlay regression" \
  python -m unittest tests.test_phase5d_synchronized_mpr_segmentation_overlay
run_quiet "Phase 6C browser presentation regression" \
  node scripts/check_phase6c_multi_structure_viewer.mjs
run_quiet "Complete previous automated regression" \
  python scripts/run_phase6d0_previous_regression.py
run_quiet "Phase 6D0 Python compile" \
  python -m py_compile \
    backend/voxelatlas/app.py \
    backend/voxelatlas/config.py \
    backend/voxelatlas/segmentation_workflow.py \
    scripts/check_phase6d0_on_demand_architecture.py \
    scripts/qualify_phase6d0_existing_segmentation_reuse.py \
    scripts/run_phase6d0_previous_regression.py \
    tests/test_phase6d0_on_demand_segmentation_workflow.py
run_quiet "Phase 6D0 JavaScript syntax" \
  bash -c 'node --check web/js/segmentation-workflow-panel.js && node --check web/js/app.js && node --check scripts/check_phase6d0_segmentation_workflow_panel.mjs'
run_quiet "Phase 6D0 shell syntax" bash -n scripts/run_phase6d0_checks.sh
run_quiet "Phase 6A isolated surface runtime regression" \
  python scripts/check_phase6a_surface_environment.py --python "$SURFACE_PYTHON"
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Canonical source-label immutability" check_source_label_immutability
run_quiet "Phase 6A/6B geometry preservation" check_phase6ab_geometry_untouched
run_quiet "Phase 6D0 roadmap boundary" check_phase6d0_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE6D0_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE6D0_AUTOMATED_CHECKS_OK=NO"
fi
echo "INITIAL_MPR_DIRECT_VOLUME_FIRST=REQUIRED"
echo "SEMANTIC_SEGMENTATION=EXPLICIT_USER_ACTION_ONLY"
echo "EXISTING_SEGMENTATION_REUSE=QUALIFY_SEPARATELY"
echo "REAL_NEW_CT_SEGMENTATION=QUALIFY_SEPARATELY"
echo "MRI_SEGMENTATION_PROVIDER=DEFERRED_TO_PHASE7"
echo "PHASE6D1_VOLUME_DERIVED_SURFACE=NOT_ENABLED"
echo "PHASE6D2_VISUALIZATION_MODES=NOT_ENABLED"
echo "PHASE6E_PRESENTATION_PROFILES=NOT_ENABLED"
echo "PHASE6A_ACCURATE_REFERENCE=IMMUTABLE"
echo "PHASE6B_REFINED_GEOMETRY=PRESERVED"
echo "SOURCE_LABEL_MAP=IMMUTABLE"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
