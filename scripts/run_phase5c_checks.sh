#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PHASE5C_LOG_DIR="$(mktemp -d -t voxelatlas-phase5c-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$PHASE5C_LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-46s PASS\n' "$label"
  else
    printf '%-46s FAIL\n' "$label"
    tail -n 100 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  if git ls-files | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth)$'; then
    return 1
  fi
}

check_heavy_worker_boundary() {
  if grep -Eiq '^(torch|monai|nibabel|nnunetv2|totalsegmentator)(\[|=|<|>|$)' requirements/backend.txt; then
    return 1
  fi
  if grep -Eiq '^[[:space:]]*(from|import)[[:space:]]+(torch|nibabel|nnunetv2|totalsegmentator)' \
    backend/voxelatlas/segmentation_label_maps.py backend/voxelatlas/app.py; then
    return 1
  fi
  grep -Eq '^[[:space:]]*import[[:space:]]+nibabel[[:space:]]+as[[:space:]]+nib' \
    scripts/phase5c_label_map_worker.py
}

check_no_phase5d_ui() {
  test -z "$(git diff --name-only HEAD -- web)" &&
    test -z "$(git ls-files --others --exclude-standard -- web)"
}

echo "===== PHASE 5C CANONICAL LABEL-MAP VALIDATION ====="
run_quiet "Phase 5C unit and HTTP contracts" \
  python -m unittest tests.test_phase5c_canonical_label_map_import
run_quiet "Phase 5C architecture probe" \
  python scripts/check_phase5c_canonical_label_map_architecture.py
run_quiet "Phase 5C import CLI contract" \
  python scripts/import_phase5c_segmentation_label_map.py --help
run_quiet "Phase 5C worker CLI contract" \
  python scripts/phase5c_label_map_worker.py --help
run_quiet "Phase 5B2 and full previous regression" \
  bash scripts/run_phase5b2_checks.sh
run_quiet "Phase 5C Python compile" \
  python -m py_compile \
    backend/voxelatlas/app.py \
    backend/voxelatlas/segmentation_label_maps.py \
    scripts/check_phase5c_canonical_label_map_architecture.py \
    scripts/import_phase5c_segmentation_label_map.py \
    scripts/phase5c_label_map_worker.py \
    tests/test_phase5c_canonical_label_map_import.py
run_quiet "Phase 5C shell syntax" bash -n scripts/run_phase5c_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy NIfTI worker isolation" check_heavy_worker_boundary
run_quiet "Phase 5D web UI unchanged" check_no_phase5d_ui
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$PHASE5C_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5C_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5C_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_LABEL_MAP_IMPORT=RUN_SEPARATELY"
echo "MPR_OVERLAY=NOT_ENABLED_UNTIL_PHASE5D"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
