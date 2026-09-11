#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6f-a-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6F_A_CHECK_TIMEOUT_SECONDS:-480}"

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
  expected="$(cat <<'EOF' | LC_ALL=C sort
/docs/phase_history/PHASE6F_A_STRUCTURE_INTERACTION_STATE_ARCHITECTURE.md
/scripts/check_phase6f_a_architecture.py
/scripts/check_phase6f_a_structure_interaction.mjs
/scripts/run_phase6f_a_checks.sh
/scripts/run_phase6f_a_previous_regression.py
/tests/test_phase6f_a_structure_interaction_state.py
/web/index.html
/web/js/app.js
/web/js/segmentation-structure-interaction.js
/web/js/segmentation-structure-panel.js
EOF
)"
  expected="$(printf '%s\n' "$expected" | sed 's#^/##')"
  actual="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | LC_ALL=C sort -u)"
  [[ "$actual" == "$expected" ]]
}

check_production_boundary(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | sort -u)"
  if printf '%s\n' "$changed" | grep -Eq '^(backend/|requirements/|web/css/|web/js/segmentation-overlay\.js$|web/js/segmentation-surface-viewer\.js$|web/js/reconstruction-|web/js/volume-surface-viewer\.js$)'; then
    return 1
  fi
}

check_interaction_purity(){
  local source="web/js/segmentation-structure-interaction.js"
  ! grep -Eiq 'fetch\(|xmlhttprequest|/api/|marching_cubes|new[[:space:]]+three|geometry\.dispose|vertices|indices' "$source"
}

check_new_file_whitespace(){
  local path
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    if grep -nE '[[:blank:]]+$' "$path" >/dev/null; then
      return 1
    fi
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6f_a|PHASE6F_A|segmentation-structure-interaction')
}

printf '%s\n' '===== PHASE 6F-A STRUCTURE INTERACTION STATE ARCHITECTURE ====='
run_quiet "Phase 6F-A focused contracts" python -m unittest -v tests.test_phase6f_a_structure_interaction_state
run_quiet "Phase 6F-A interaction behavior" node scripts/check_phase6f_a_structure_interaction.mjs
run_quiet "Phase 6F-A architecture probe" python scripts/check_phase6f_a_architecture.py
run_quiet "Phase 5E structure panel regression" python -m unittest -v tests.test_phase5e_anatomical_structure_panel
run_quiet "Phase 5E structure behavior regression" node scripts/check_phase5e_structure_panel.mjs
run_quiet "Phase 6E-F closure regression" python -m unittest -v tests.test_phase6e_f_final_real_study_qualification
run_quiet "Complete previous automated regression" python scripts/run_phase6f_a_previous_regression.py
run_quiet "Phase 6F-A Python compile" python -m py_compile scripts/check_phase6f_a_architecture.py scripts/run_phase6f_a_previous_regression.py tests/test_phase6f_a_structure_interaction_state.py
run_quiet "Phase 6F-A JavaScript syntax" node --check web/js/segmentation-structure-interaction.js
run_quiet "Phase 6F-A structure panel syntax" node --check web/js/segmentation-structure-panel.js
run_quiet "Phase 6F-A app JavaScript syntax" node --check web/js/app.js
run_quiet "Phase 6F-A probe JavaScript syntax" node --check scripts/check_phase6f_a_structure_interaction.mjs
run_quiet "Phase 6F-A shell syntax" bash -n scripts/run_phase6f_a_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Exact Phase 6F-A candidate delta" check_exact_candidate_delta
run_quiet "Production boundary preservation" check_production_boundary
run_quiet "Interaction state remains geometry/I-O free" check_interaction_purity
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6F_A_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6F_A_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=b6e39b4f8813a9e6c48596a16323d426801530fb
INTERACTION_STATE=NON_DESTRUCTIVE_DISPLAY_FOUNDATION
USER_VISIBILITY=AUTHORITATIVE_BASE_STATE
USER_STRUCTURE_OPACITY=AUTHORITATIVE
ISOLATION=TRANSIENT_EFFECTIVE_VISIBILITY_GATE
SURFACE_REQUEST_STATE=INDEPENDENT_PRESERVED
CLIPPING_PARTICIPATION=STATE_ONLY_NOT_APPLIED
EXPLODED_OFFSET=PATIENT_LPS_DISPLAY_STATE_ONLY_NOT_APPLIED
MODE_PROFILE_CHANGES_BUILD_GEOMETRY=NO
INTERACTION_STATE_FETCHES_GEOMETRY=NO
PATIENT_SPACE_GEOMETRY_MUTATION=NO
PHASE6F_B_SHOW_HIDE_ISOLATE_RESTORE=NOT_ENABLED
PHASE6F_C_TRANSPARENCY_QUALIFICATION=NOT_ENABLED
PHASE6F_D_PER_STRUCTURE_CLIPPING=NOT_ENABLED
PHASE6F_E_EXPLODED_PRESENTATION=NOT_ENABLED
PHASE6F_F_FINAL_QUALIFICATION=NOT_CLOSED
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
