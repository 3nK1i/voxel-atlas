#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-.venv/bin/python}"
[[ -x "$PYTHON" ]]
CHECK_TIMEOUT_SECONDS="${POST_D6_UI_CHECK_TIMEOUT_SECONDS:-1200}"
LOG_DIR="$(mktemp -d /tmp/voxelatlas-post-d6-ui-checks.XXXXXXXX)"
trap 'rm -rf "$LOG_DIR"' EXIT
FAIL=0

run_quiet(){
  local label="$1"; shift
  local slug
  slug="$(printf '%s' "$label" | tr ' /' '__' | tr -cd '[:alnum:]_.-')"
  local log="$LOG_DIR/$slug.log"
  if [[ "$#" -gt 0 ]] && declare -F "$1" >/dev/null 2>&1; then
    if "$@" >"$log" 2>&1; then
      printf '%-96s PASS\n' "$label"
    else
      printf '%-96s FAIL\n' "$label"
      cat "$log"
      FAIL=1
    fi
  elif timeout "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1; then
    printf '%-96s PASS\n' "$label"
  else
    printf '%-96s FAIL\n' "$label"
    cat "$log"
    FAIL=1
  fi
}

check_expected_delta(){
  local actual expected
  actual="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | sort -u)"
  expected="$(cat <<'EOF' | sort
web/assets/sample-study-ct.svg
web/assets/sample-study-mr.svg
web/css/styles.css
web/index.html
web/js/app.js
docs/phase_history/POST_D6_SAMPLE_UI_POLISH.md
scripts/check_phase6j_b2b_mri_study_workflows.mjs
scripts/run_post_d6_ui_polish_checks.sh
tests/test_phase4g_sample_study_catalog.py
tests/test_post_d6_sample_ui_polish.py
EOF
)"
  [[ "$actual" == "$expected" ]]
}

check_no_backend_delta(){
  ! { git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } \
    | grep -Eq '^backend/'
}

check_patient_data_safety(){
  ! git ls-files --cached --others --exclude-standard \
    | grep -Eiv '(^|/)\.env\.example$' \
    | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2|vxvs)$|(^|/)\.env($|\.)'
}

check_new_file_whitespace(){
  local path
  for path in \
    web/assets/sample-study-ct.svg \
    web/assets/sample-study-mr.svg \
    docs/phase_history/POST_D6_SAMPLE_UI_POLISH.md \
    scripts/run_post_d6_ui_polish_checks.sh \
    tests/test_post_d6_sample_ui_polish.py
  do
    if grep -nE '[[:blank:]]+$' "$path"; then
      return 1
    fi
  done
}

printf '%s\n' '===== POST-D6 SAMPLE UI POLISH + MRI 0.35 INITIALIZATION ====='

run_quiet "Post-D6 focused UI contracts" \
  "$PYTHON" -m unittest -v tests.test_post_d6_sample_ui_polish
run_quiet "Phase 4G sample-catalog regression" \
  "$PYTHON" -m unittest -v tests.test_phase4g_sample_study_catalog
run_quiet "D4.5C Direct-MR UI regression" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d45c_direct_mri_surface_ui
run_quiet "D4.5D backend/default acceptance contract" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d45d_direct_mri_acceptance
run_quiet "B2B sample/upload browser contract" \
  node scripts/check_phase6j_b2b_mri_study_workflows.mjs
run_quiet "D4.5C current architecture contract" \
  "$PYTHON" scripts/check_phase6j_d45c_direct_mri_surface_architecture.py
run_quiet "Application JavaScript syntax" node --check web/js/app.js
run_quiet "B2B probe JavaScript syntax" node --check scripts/check_phase6j_b2b_mri_study_workflows.mjs
run_quiet "Focused Python compile" \
  "$PYTHON" -m py_compile tests/test_phase4g_sample_study_catalog.py tests/test_post_d6_sample_ui_polish.py
run_quiet "Exact post-D6 delta" check_expected_delta
run_quiet "Backend implementation untouched" check_no_backend_delta
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "POST_D6_UI_POLISH_CHECKS_OK=NO"
  exit 1
fi

cat <<'EOF'
POST_D6_UI_POLISH_CHECKS_OK=YES
SAMPLE_CT_SVG=INTEGRATED
SAMPLE_MR_SVG=INTEGRATED
SAMPLE_OPEN_LABEL=OPEN
SAMPLE_REPLACEMENT_CONFIRMATION=REMOVED
SAMPLE_LOAD=IMMEDIATE_VERIFIED_PATH
MRI_PRESENTATION_INITIAL_ISOVALUE=0.35
MRI_BACKEND_DEFAULT_ISOVALUE=0.50
DIRECT_CT_DEFAULT_HU=300
BACKEND_IMPLEMENTATION_CHANGES=NO
MRI_INFERENCE=NOT_RUN
PRODUCTION_MRI_IMPORT=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
D45D_HISTORICAL_DELTA_GUARD=NOT_REPLAYED
TEST_RC=0
EOF
