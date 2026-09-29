#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PHASE5B1_LOG_DIR="$(mktemp -d -t voxelatlas-phase5b1-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$PHASE5B1_LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-46s PASS\n' "$label"
  else
    printf '%-46s FAIL\n' "$label"
    tail -n 80 "$log"
    FAIL=1
  fi
}

check_patient_data_safety() {
  if git ls-files | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/jobs(/|$)|\.(dcm|nii|nii\.gz|nrrd)$'; then
    return 1
  fi
}

check_runtime_isolation() {
  if grep -Eiq '^(torch|monai|totalsegmentator)(\[|=|<|>|$)' requirements/backend.txt; then
    return 1
  fi
  if grep -Eq '(^|[[:space:]])(from|import)[[:space:]]+(torch|totalsegmentator)' \
    backend/voxelatlas/totalsegmentator_runtime.py; then
    return 1
  fi
  if grep -Eiq 'totalsegmentator_runtime|TotalSegmentatorRuntimeQualifier' \
    backend/voxelatlas/app.py; then
    return 1
  fi
}

echo "===== PHASE 5B1 TOTALSEGMENTATOR QUALIFICATION VALIDATION ====="
run_quiet "Phase 5B1 unit contracts" \
  python -m unittest tests.test_phase5b1_totalsegmentator_runtime_qualification
run_quiet "Phase 5B1 probe CLI contract" \
  python scripts/check_phase5b1_totalsegmentator_environment.py --help
run_quiet "Phase 5A and full previous regression" \
  bash scripts/run_phase5a_checks.sh
run_quiet "Phase 5B1 Python compile" \
  python -m py_compile \
    backend/voxelatlas/totalsegmentator_runtime.py \
    scripts/check_phase5b1_totalsegmentator_environment.py \
    tests/test_phase5b1_totalsegmentator_runtime_qualification.py
run_quiet "Phase 5B1 shell syntax" \
  bash -n scripts/run_phase5b1_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy runtime isolation" check_runtime_isolation
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$PHASE5B1_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5B1_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5B1_AUTOMATED_CHECKS_OK=NO"
fi
echo "TARGET_RUNTIME_QUALIFICATION=RUN_SEPARATELY"
echo "MODEL_WEIGHTS=NOT_DOWNLOADED"
echo "REAL_SEGMENTATION_INFERENCE=NOT_RUN"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
