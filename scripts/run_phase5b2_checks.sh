#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PHASE5B2_LOG_DIR="$(mktemp -d -t voxelatlas-phase5b2-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$PHASE5B2_LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-46s PASS\n' "$label"
  else
    printf '%-46s FAIL\n' "$label"
    tail -n 80 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  if git ls-files | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth)$'; then
    return 1
  fi
}

check_runtime_isolation() {
  if grep -Eiq '^(torch|monai|nibabel|nnunetv2|totalsegmentator)(\[|=|<|>|$)' requirements/backend.txt; then
    return 1
  fi
  if grep -Eq '^[[:space:]]*(from|import)[[:space:]]+(torch|nibabel|nnunetv2|totalsegmentator)' \
    backend/voxelatlas/totalsegmentator_execution.py; then
    return 1
  fi
  if grep -Eiq 'totalsegmentator_execution|TotalSegmentatorProvider' backend/voxelatlas/app.py; then
    return 1
  fi
}

echo "===== PHASE 5B2 TOTALSEGMENTATOR EXECUTION VALIDATION ====="
run_quiet "Phase 5B2 unit contracts" \
  python -m unittest tests.test_phase5b2_totalsegmentator_execution
run_quiet "Phase 5B2 weight CLI contract" \
  python scripts/prepare_phase5b2_totalsegmentator_weights.py --help
run_quiet "Phase 5B2 execution CLI contract" \
  python scripts/run_phase5b2_totalsegmentator_qualification.py --help
run_quiet "Phase 5B1 and full previous regression" \
  bash scripts/run_phase5b1_checks.sh
run_quiet "Phase 5B2 Python compile" \
  python -m py_compile \
    backend/voxelatlas/segmentation.py \
    backend/voxelatlas/totalsegmentator_runtime.py \
    backend/voxelatlas/totalsegmentator_execution.py \
    scripts/phase5b2_nifti_worker.py \
    scripts/prepare_phase5b2_totalsegmentator_weights.py \
    scripts/run_phase5b2_totalsegmentator_qualification.py \
    tests/test_phase5b2_totalsegmentator_execution.py
run_quiet "Phase 5B2 shell syntax" bash -n scripts/run_phase5b2_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy runtime isolation" check_runtime_isolation
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$PHASE5B2_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5B2_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5B2_AUTOMATED_CHECKS_OK=NO"
fi
echo "WEIGHT_ACQUISITION=RUN_SEPARATELY"
echo "REAL_CT_INFERENCE=RUN_SEPARATELY"
echo "FULL_RESOLUTION=REQUIRED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
