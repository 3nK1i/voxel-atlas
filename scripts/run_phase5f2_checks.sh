#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
LOG_DIR="$(mktemp -d -t voxelatlas-phase5f2-checks.XXXXXXXX)" || exit 1
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
  if git ls-files | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy)$'; then
    return 1
  fi
}

check_heavy_dependency_boundary() {
  if grep -Eiq '^(torch|monai|nibabel|nnunetv2|totalsegmentator)(\[|=|<|>|$)' requirements/backend.txt; then
    return 1
  fi
  if grep -Eiq '^[[:space:]]*(from|import)[[:space:]]+(torch|nibabel|nnunetv2|totalsegmentator)' \
    backend/voxelatlas/segmentation_corrections.py backend/voxelatlas/app.py; then
    return 1
  fi
}

echo "===== PHASE 5F2 MANUAL CORRECTION FOUNDATION VALIDATION ====="
run_quiet "Phase 5F2 unit and HTTP contracts" python -m unittest tests.test_phase5f2_manual_correction_foundation
run_quiet "Phase 5F2 architecture probe" python scripts/check_phase5f2_correction_architecture.py
run_quiet "Phase 5F2 browser interaction contract" node scripts/check_phase5f2_correction_panel.mjs
run_quiet "Phase 5F1 and full previous regression" python scripts/run_phase5f2_previous_regression.py
run_quiet "Phase 5F2 Python compile" python -m py_compile \
  backend/voxelatlas/segmentation_corrections.py backend/voxelatlas/app.py \
  scripts/check_phase5f2_correction_architecture.py scripts/qualify_phase5f2_real_correction_foundation.py \
  scripts/run_phase5f2_previous_regression.py tests/test_phase5f2_manual_correction_foundation.py
run_quiet "Phase 5F2 JavaScript syntax" bash -c 'node --check web/js/app.js && node --check web/js/segmentation-correction-panel.js && node --check scripts/check_phase5f2_correction_panel.mjs'
run_quiet "Phase 5F2 shell syntax" bash -n scripts/run_phase5f2_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy dependency boundary" check_heavy_dependency_boundary
run_quiet "Canonical label immutability" bash -c '! grep -Eq "(save|write_bytes|tofile)\(.*labels\.npy" backend/voxelatlas/segmentation_corrections.py'
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5F2_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5F2_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_CORRECTION_DRAFT=RUN_SEPARATELY"
echo "MANUAL_APP_REVIEW=RUN_SEPARATELY"
echo "SOURCE_LABEL_MAP=IMMUTABLE"
echo "CORRECTION_MATERIALIZATION=NOT_ENABLED"
echo "PHASE5G_CLOSURE=NOT_STARTED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
