#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PHASE5A_LOG_DIR="$(mktemp -d -t voxelatlas-phase5a-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$PHASE5A_LOG_DIR/${label// /_}.log"
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

check_dependency_boundary() {
  if grep -Eiq '^(torch|monai|totalsegmentator)(\[|=|<|>|$)' requirements/backend.txt; then
    return 1
  fi
}

echo "===== PHASE 5A PROVIDER-NEUTRAL SEGMENTATION VALIDATION ====="
run_quiet "Phase 5A unit and HTTP contracts" \
  python -m unittest tests.test_phase5a_segmentation_architecture
run_quiet "Phase 5A architecture probe" \
  python scripts/check_phase5a_segmentation_architecture.py
run_quiet "Phase 4 closure and full regression" \
  bash scripts/run_phase4_volume_rendering_closure_checks.sh
run_quiet "Phase 5A Python compile" \
  python -m py_compile \
    backend/voxelatlas/segmentation.py \
    backend/voxelatlas/app.py \
    scripts/check_phase5a_segmentation_architecture.py \
    tests/test_phase5a_segmentation_architecture.py
run_quiet "Phase 5A shell syntax" \
  bash -n scripts/run_phase5a_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy dependency boundary" check_dependency_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$PHASE5A_LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5A_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5A_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_SEGMENTATION_INFERENCE=NOT_ENABLED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
