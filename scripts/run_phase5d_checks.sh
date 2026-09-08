#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PHASE5D_LOG_DIR="$(mktemp -d -t voxelatlas-phase5d-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$PHASE5D_LOG_DIR/${label// /_}.log"
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
    backend/voxelatlas/segmentation_overlays.py backend/voxelatlas/app.py; then
    return 1
  fi
}

echo "===== PHASE 5D SYNCHRONIZED MPR SEGMENTATION OVERLAY VALIDATION ====="
run_quiet "Phase 5D unit and HTTP contracts" \
  python -m unittest tests.test_phase5d_synchronized_mpr_segmentation_overlay
run_quiet "Phase 5D architecture probe" \
  python scripts/check_phase5d_segmentation_overlay_architecture.py
run_quiet "Phase 5D browser overlay contract" \
  node scripts/check_phase5d_segmentation_overlay.mjs
run_quiet "Phase 5D qualification CLI contract" \
  python scripts/qualify_phase5d_real_segmentation_overlay.py --help
run_quiet "Forward-compatible full regression" \
  python scripts/run_phase5d_previous_regression.py
run_quiet "Phase 5D Python compile" \
  python -m py_compile \
    backend/voxelatlas/app.py \
    backend/voxelatlas/segmentation_overlays.py \
    scripts/check_phase5d_segmentation_overlay_architecture.py \
    scripts/qualify_phase5d_real_segmentation_overlay.py \
    scripts/run_phase5d_previous_regression.py \
    tests/test_phase5d_synchronized_mpr_segmentation_overlay.py
run_quiet "Phase 5D JavaScript syntax" \
  bash -c 'node --check web/js/app.js && node --check web/js/segmentation-overlay.js && node --check scripts/check_phase5d_segmentation_overlay.mjs'
run_quiet "Phase 5D shell syntax" bash -n scripts/run_phase5d_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy dependency boundary" check_heavy_dependency_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$PHASE5D_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5D_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5D_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_LABEL_MAP_OVERLAY=RUN_SEPARATELY"
echo "ACTUAL_APP_VISUALIZATION=READY_FOR_MANUAL_QUALIFICATION"
echo "PHASE5E_STRUCTURE_PANEL=NOT_ENABLED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
