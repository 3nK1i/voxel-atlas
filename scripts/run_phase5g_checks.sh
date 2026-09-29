#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase5g-checks.XXXXXXXX)" || exit 1
FAIL=0

run_quiet() {
  local label="$1"
  shift
  local log="$LOG_DIR/${label// /_}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-49s PASS\n' "$label"
  else
    printf '%-49s FAIL\n' "$label"
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
    backend/voxelatlas/segmentation_qualification.py; then
    return 1
  fi
}

echo "===== PHASE 5G REAL-STUDY QUALIFICATION AND PHASE 5 CLOSURE ====="
run_quiet "Phase 5G closure unit contracts" python -m unittest tests.test_phase5g_segmentation_closure
run_quiet "Phase 5G architecture probe" python scripts/check_phase5g_architecture.py
run_quiet "Phase 5G ergonomic UI contract" node scripts/check_phase5g_ui.mjs
run_quiet "Phase 5F2 and full previous regression" python scripts/run_phase5g_previous_regression.py
run_quiet "Phase 5G Python compile" python -m py_compile \
  backend/voxelatlas/segmentation_qualification.py scripts/check_phase5g_architecture.py \
  scripts/qualify_phase5g_real_study.py scripts/run_phase5g_previous_regression.py \
  tests/test_phase5g_segmentation_closure.py
run_quiet "Phase 5G JavaScript syntax" bash -c 'node --check web/js/app.js && node --check scripts/check_phase5g_ui.mjs'
run_quiet "Phase 5G shell syntax" bash -n scripts/run_phase5g_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Heavy runtime isolation" check_heavy_dependency_boundary
run_quiet "Canonical label immutability" bash -c '! grep -Eq "(save|write_bytes|tofile)\(.*labels\.npy" backend/voxelatlas/segmentation_qualification.py'
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'

printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE5G_AUTOMATED_CHECKS_OK=YES"
else
  echo "PHASE5G_AUTOMATED_CHECKS_OK=NO"
fi
echo "REAL_STUDY_QUALIFICATION=RUN_SEPARATELY"
echo "ERGONOMIC_UI_REVIEW=RUN_SEPARATELY"
echo "MODEL_COMPARISON_RANKING=NOT_CLAIMED"
echo "SOURCE_LABEL_MAP=IMMUTABLE"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
