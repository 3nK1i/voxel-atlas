#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
LOG_DIR="$(mktemp -d -t voxelatlas-phase5f2-identity-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-48s PASS\n' "$label"
  else
    printf '%-48s FAIL\n' "$label"
    tail -n 100 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  ! git ls-files | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy)$'
}

echo "===== PHASE 5F2 SAMPLE STUDY IDENTITY CORRECTION VALIDATION ====="
run_quiet "Phase 5F2 identity unit contracts" python -m unittest tests.test_phase5f2_sample_study_identity_correction
run_quiet "Phase 4G catalog regression" python -m unittest tests.test_phase4g_sample_study_catalog
run_quiet "Phase 5F2 live sample switch contract" node scripts/check_phase5f2_sample_study_switch.mjs
run_quiet "Phase 5F2 complete regression" bash scripts/run_phase5f2_checks.sh
run_quiet "Phase 5F2 identity architecture probe" python scripts/check_phase5f2_sample_study_identity_architecture.py
run_quiet "Phase 5F2 identity Python compile" python -m py_compile \
  backend/voxelatlas/dicom_ingestion.py backend/voxelatlas/sample_catalog.py backend/voxelatlas/app.py \
  scripts/check_phase5f2_sample_study_identity_architecture.py \
  scripts/qualify_phase5f2_sample_study_identity.py \
  tests/test_phase5f2_sample_study_identity_correction.py
run_quiet "Phase 5F2 identity shell syntax" bash -n scripts/run_phase5f2_sample_study_identity_correction_checks.sh
run_quiet "Phase 5F2 identity JavaScript syntax" bash -c \
  'node --check web/js/app.js && node --check web/js/sample-study-activation.js && node --check scripts/check_phase5f2_sample_study_switch.mjs'
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5F2_SAMPLE_IDENTITY_CORRECTION_CHECKS_OK=YES"
else
  echo "PHASE5F2_SAMPLE_IDENTITY_CORRECTION_CHECKS_OK=NO"
fi
echo "REAL_SAMPLE_REACTIVATION=RUN_SEPARATELY"
echo "LIVE_SAMPLE_SWITCH=RUN_SEPARATELY"
echo "CROSS_STUDY_LABEL_REUSE=NOT_ENABLED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
