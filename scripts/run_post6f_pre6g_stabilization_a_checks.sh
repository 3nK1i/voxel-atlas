#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-post6f-pre6g-a.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${POST6F_PRE6G_A_CHECK_TIMEOUT_SECONDS:-480}"

run_quiet(){
  local label="$1"; shift
  local safe log rc
  safe="$(printf '%s' "$label" | tr -cs '[:alnum:]_.-' '_')"
  log="$LOG_DIR/${safe}.log"
  if declare -F "$1" >/dev/null 2>&1; then
    "$@" >"$log" 2>&1
    rc=$?
  else
    timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1
    rc=$?
  fi
  if [[ "$rc" -eq 0 ]]; then
    printf '%-96s PASS\n' "$label"
  else
    printf '%-96s FAIL\n' "$label"
    [[ "$rc" -eq 124 ]] && printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"
    tail -n 180 "$log"
    FAIL=1
  fi
}

check_patient_data_safety(){
  if git ls-files --cached --others --exclude-standard \
    | grep -Eiv '(^|/)\.env\.example$' \
    | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2|vxvs)$|(^|/)\.env($|\.)'; then
    return 1
  fi
}

check_exact_candidate_delta(){
  local expected actual
  expected="$(cat <<'LIST' | LC_ALL=C sort
docs/phase_history/POST6F_PRE6G_STABILIZATION_A_DIAGNOSTICS_LOADING_SIDEBAR.md
scripts/check_post6f_pre6g_stabilization_a.py
scripts/diagnose_post6f_direct_ct_surface.py
scripts/diagnose_post6f_study_loading.py
scripts/run_post6f_pre6g_stabilization_a_checks.sh
tests/test_post6f_pre6g_stabilization_a.py
web/css/styles.css
web/index.html
web/js/app.js
LIST
)"
  actual="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | LC_ALL=C sort -u)"
  [[ "$actual" == "$expected" ]]
}

check_scope_boundary(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^(backend/|requirements/|data/|uploads/|patient_data/|weights/|scripts/phase6[a-zA-Z0-9_]*_worker\.py$)'
}

check_diagnostics_read_only(){
  ! grep -Eq 'np\.save\(|write_bytes\(|write_text\(|unlink\(|rmdir\(|shutil\.(rmtree|copy|move)' \
    scripts/diagnose_post6f_direct_ct_surface.py scripts/diagnose_post6f_study_loading.py
}

printf '%s\n' '===== POST-6F / PRE-6G STABILIZATION A ====='
run_quiet "Stabilization A focused contracts" python -m unittest -v tests.test_post6f_pre6g_stabilization_a
run_quiet "Stabilization A architecture probe" python scripts/check_post6f_pre6g_stabilization_a.py
run_quiet "Phase 6F-F focused closure regression" python -m unittest -v tests.test_phase6f_f_final_real_study_interaction_qualification
run_quiet "Phase 6F-E focused regression" python -m unittest -v tests.test_phase6f_e_anatomical_group_exploded_presentation
run_quiet "Phase 6D1 Direct-CT surface regression" python -m unittest -v tests.test_phase6d1_volume_derived_surfaces
run_quiet "Phase 5F2 sample identity regression" python -m unittest -v tests.test_phase5f2_sample_study_identity_correction
run_quiet "Complete previous automated regression" python scripts/run_phase6f_f_previous_regression.py
run_quiet "Python compile" python -m py_compile scripts/check_post6f_pre6g_stabilization_a.py scripts/diagnose_post6f_direct_ct_surface.py scripts/diagnose_post6f_study_loading.py tests/test_post6f_pre6g_stabilization_a.py
run_quiet "App JavaScript syntax" node --check web/js/app.js
run_quiet "Shell syntax" bash -n scripts/run_post6f_pre6g_stabilization_a_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Exact candidate delta" check_exact_candidate_delta
run_quiet "Scope boundary" check_scope_boundary
run_quiet "Diagnostics remain read-only" check_diagnostics_read_only
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "POST6F_PRE6G_STABILIZATION_A_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'MARKERS'
POST6F_PRE6G_STABILIZATION_A_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=f47e984c8cc4dd0e04544dba4e1d6782ffb499b0
CANDIDATE_FILE_COUNT=9
RIGHT_SIDEBAR_ORDER=GLOBAL_TO_SPECIFIC
VOLUME_RENDERING_QUALITY_FIRST=YES
DIRECT_CT_ACTION_ERGONOMICS=SHARED_BUTTON_SYSTEM
READY_STUDY_MPR_GPU_PRESTART=PARALLEL
SAMPLE_INTEGRITY_CONTRACT=UNCHANGED
DIRECT_CT_DIAGNOSTIC=READ_ONLY_COMPONENT_EVIDENCE
LOADING_DIAGNOSTIC=READ_ONLY_TIMING_EVIDENCE
CANONICAL_CT_MUTATION=NO
PATIENT_LPS_MUTATION=NO
SEGMENTATION_MUTATION=NO
ARBITRARY_LARGEST_COMPONENT_REMOVAL=NO
DIRECT_CT_SURFACE_CORRECTION=DEFERRED_UNTIL_REAL_STUDY_DIAGNOSTIC
PHASE6G=NOT_STARTED
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
MARKERS
