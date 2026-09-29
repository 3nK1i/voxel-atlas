#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6f-b-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6F_B_CHECK_TIMEOUT_SECONDS:-480}"

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
docs/phase_history/PHASE6F_B_NON_DESTRUCTIVE_VISIBILITY_ISOLATION.md
scripts/check_phase5e_structure_panel.mjs
scripts/check_phase6c_multi_structure_viewer.mjs
scripts/check_phase6f_a_architecture.py
scripts/check_phase6f_b_architecture.py
scripts/check_phase6f_b_visibility_isolation.mjs
scripts/run_phase6f_b_checks.sh
scripts/run_phase6f_b_previous_regression.py
tests/test_phase6f_a_structure_interaction_state.py
tests/test_phase6f_b_non_destructive_visibility_isolation.py
web/css/styles.css
web/index.html
web/js/app.js
web/js/segmentation-overlay.js
web/js/segmentation-structure-interaction.js
web/js/segmentation-structure-panel.js
web/js/segmentation-surface-viewer.js
EOF
)"
  actual="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | LC_ALL=C sort -u)"
  [[ "$actual" == "$expected" ]]
}

check_production_boundary(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | sort -u)"
  if printf '%s\n' "$changed" | grep -Eq '^(backend/|requirements/|web/js/reconstruction-|web/js/volume-surface-viewer\.js$|web/js/patient-volume-ray-marcher\.js$)'; then
    return 1
  fi
}

check_interaction_purity(){
  local source="web/js/segmentation-structure-interaction.js"
  ! grep -Eiq 'fetch\(|xmlhttprequest|/api/|marching_cubes|new[[:space:]]+three|geometry\.dispose|vertices|indices' "$source"
}

check_added_interaction_has_no_geometry_io(){
  local added
  added="$(git diff --unified=0 -- \
    web/js/segmentation-structure-interaction.js \
    web/js/segmentation-structure-panel.js \
    web/js/segmentation-overlay.js \
    web/js/segmentation-surface-viewer.js \
    | grep '^+' | grep -v '^+++' || true)"
  if printf '%s\n' "$added" | grep -Eiq 'fetch\(|xmlhttprequest|/api/|marching_cubes|setattribute\("position"|setindex\(|geometry\.apply|computevertexnormals|vertices|indices'; then
    return 1
  fi
}

check_new_file_whitespace(){
  local path
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    if grep -nE '[[:blank:]]+$' "$path" >/dev/null; then
      return 1
    fi
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6f_b|PHASE6F_B')
}

printf '%s\n' '===== PHASE 6F-B NON-DESTRUCTIVE SHOW / HIDE / ISOLATE / RESTORE ====='
run_quiet "Phase 6F-B focused contracts" python -m unittest -v tests.test_phase6f_b_non_destructive_visibility_isolation
run_quiet "Phase 6F-B interaction behavior" node scripts/check_phase6f_b_visibility_isolation.mjs
run_quiet "Phase 6F-B architecture probe" python scripts/check_phase6f_b_architecture.py
run_quiet "Phase 6F-A foundation unit regression" python -m unittest -v tests.test_phase6f_a_structure_interaction_state
run_quiet "Phase 6F-A behavior regression" node scripts/check_phase6f_a_structure_interaction.mjs
run_quiet "Phase 6F-A architecture regression" python scripts/check_phase6f_a_architecture.py
run_quiet "Phase 5E structure unit regression" python -m unittest -v tests.test_phase5e_anatomical_structure_panel
run_quiet "Phase 5E structure behavior regression" node scripts/check_phase5e_structure_panel.mjs
run_quiet "Phase 6C multi-structure behavior regression" node scripts/check_phase6c_multi_structure_viewer.mjs
run_quiet "Phase 6E-F closure regression" python -m unittest -v tests.test_phase6e_f_final_real_study_qualification
run_quiet "Complete previous automated regression" python scripts/run_phase6f_b_previous_regression.py
run_quiet "Phase 6F-B Python compile" python -m py_compile scripts/check_phase6f_b_architecture.py scripts/run_phase6f_b_previous_regression.py tests/test_phase6f_b_non_destructive_visibility_isolation.py
run_quiet "Phase 6F-B interaction JavaScript syntax" node --check web/js/segmentation-structure-interaction.js
run_quiet "Phase 6F-B structure panel syntax" node --check web/js/segmentation-structure-panel.js
run_quiet "Phase 6F-B overlay syntax" node --check web/js/segmentation-overlay.js
run_quiet "Phase 6F-B surface viewer syntax" node --check web/js/segmentation-surface-viewer.js
run_quiet "Phase 6F-B app syntax" node --check web/js/app.js
run_quiet "Phase 6F-B behavior probe syntax" node --check scripts/check_phase6f_b_visibility_isolation.mjs
run_quiet "Phase 6F-B shell syntax" bash -n scripts/run_phase6f_b_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Exact Phase 6F-B candidate delta" check_exact_candidate_delta
run_quiet "Production boundary preservation" check_production_boundary
run_quiet "Interaction state remains geometry/I-O free" check_interaction_purity
run_quiet "6F-B added interaction logic has no geometry/I-O" check_added_interaction_has_no_geometry_io
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6F_B_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6F_B_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=78b6f4cec3087baf59a47feff8989fcf39262fde
SHOW_HIDE=AUTHORITATIVE_BASE_VISIBILITY
ISOLATION=TRANSIENT_NON_DESTRUCTIVE_GATE
RESTORE=RECOVERS_PRE_ISOLATION_VISIBILITY
MPR_OVERLAY=EFFECTIVE_VISIBILITY
SEGMENTATION_3D=EFFECTIVE_VISIBILITY
SURFACE_REQUEST_STATE=PRESERVED
ISOLATE_RESTORE_FETCH_GEOMETRY=NO
PATIENT_SPACE_GEOMETRY_MUTATION=NO
SOURCE_LABEL_MAP_MUTATION=NO
PHASE6F_C_TRANSPARENCY_QUALIFICATION=NOT_ENABLED
PHASE6F_D_PER_STRUCTURE_CLIPPING=NOT_ENABLED
PHASE6F_E_EXPLODED_PRESENTATION=NOT_ENABLED
PHASE6F_F_FINAL_QUALIFICATION=NOT_CLOSED
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
