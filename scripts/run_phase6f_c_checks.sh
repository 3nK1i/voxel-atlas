#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6f-c-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6F_C_CHECK_TIMEOUT_SECONDS:-480}"

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
docs/phase_history/PHASE6F_C_STRUCTURE_TRANSPARENCY_ROBUSTNESS.md
scripts/check_phase6f_c_architecture.py
scripts/check_phase6f_c_transparency.mjs
scripts/run_phase6f_c_checks.sh
scripts/run_phase6f_c_previous_regression.py
tests/test_phase6f_c_structure_transparency_robustness.py
web/index.html
web/js/app.js
web/js/reconstruction-surface-presentation.js
web/js/segmentation-surface-viewer.js
web/js/volume-surface-viewer.js
EOF
)"
  actual="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | LC_ALL=C sort -u)"
  [[ "$actual" == "$expected" ]]
}

check_production_boundary(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | sort -u)"
  if printf '%s\n' "$changed" | grep -Eq '^(backend/|requirements/|web/js/patient-volume-ray-marcher\.js$|web/js/segmentation-overlay\.js$|web/js/segmentation-structure-panel\.js$|web/js/segmentation-structure-interaction\.js$)'; then
    return 1
  fi
}

check_no_geometry_io(){
  local added
  added="$(git diff --unified=0 -- web/js/reconstruction-surface-presentation.js web/js/segmentation-surface-viewer.js web/js/volume-surface-viewer.js web/js/app.js | grep '^+' | grep -v '^+++' || true)"
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
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6f_c|PHASE6F_C')
}

printf '%s\n' '===== PHASE 6F-C PER-STRUCTURE TRANSPARENCY ROBUSTNESS ====='
run_quiet "Phase 6F-C focused contracts" python -m unittest -v tests.test_phase6f_c_structure_transparency_robustness
run_quiet "Phase 6F-C opacity behavior" node scripts/check_phase6f_c_transparency.mjs
run_quiet "Phase 6F-C architecture probe" python scripts/check_phase6f_c_architecture.py
run_quiet "Phase 6F-B interaction unit regression" python -m unittest -v tests.test_phase6f_b_non_destructive_visibility_isolation
run_quiet "Phase 6F-B interaction behavior regression" node scripts/check_phase6f_b_visibility_isolation.mjs
run_quiet "Phase 6B fallback regression" python -m unittest -v tests.test_phase6b_refined_surface_accurate_fallback
run_quiet "Phase 6B fallback behavior regression" node scripts/check_phase6b_refined_surface_fallback.mjs
run_quiet "Phase 6E-B shared material regression" node scripts/check_phase6e_b_surface_presentation.mjs
run_quiet "Phase 6E-C Fidelity material regression" node scripts/check_phase6e_c_fidelity_profile.mjs
run_quiet "Phase 6E-F closure regression" python -m unittest -v tests.test_phase6e_f_final_real_study_qualification
run_quiet "Complete previous automated regression" python scripts/run_phase6f_c_previous_regression.py
run_quiet "Phase 6F-C Python compile" python -m py_compile scripts/check_phase6f_c_architecture.py scripts/run_phase6f_c_previous_regression.py tests/test_phase6f_c_structure_transparency_robustness.py
run_quiet "Surface presentation JavaScript syntax" node --check web/js/reconstruction-surface-presentation.js
run_quiet "Surface viewer JavaScript syntax" node --check web/js/segmentation-surface-viewer.js
run_quiet "Direct CT surface viewer JavaScript syntax" node --check web/js/volume-surface-viewer.js
run_quiet "App JavaScript syntax" node --check web/js/app.js
run_quiet "6F-C behavior probe syntax" node --check scripts/check_phase6f_c_transparency.mjs
run_quiet "6F-C shell syntax" bash -n scripts/run_phase6f_c_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Exact Phase 6F-C candidate delta" check_exact_candidate_delta
run_quiet "Production boundary preservation" check_production_boundary
run_quiet "Opacity change remains geometry/I-O free" check_no_geometry_io
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6F_C_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6F_C_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=8002277477116ef7d02a6cd1d0e2fe5f76d84cb3
USER_STRUCTURE_OPACITY=AUTHORITATIVE_EXACT
NEAR_OPAQUE_MAGIC_THRESHOLD=REMOVED
TRANSPARENT_BELOW_100_PERCENT=YES
DEPTH_WRITE_BELOW_100_PERCENT=NO
FULL_ALPHA_AT_100_PERCENT=YES
TRANSPARENT_RENDER_LANE_AT_100_PERCENT=YES
DEPTH_WRITE_AT_100_PERCENT=YES
SEMANTIC_OVERLAY_ORDER_STABLE_AT_100_PERCENT=YES
SURFACE_MODE_DIRECT_CT_SEMANTIC_COEXISTENCE=YES
DIRECT_CT_ONLY_SURFACE_MODE_UNCHANGED=YES
PROFILE_SWITCH_MUTATES_USER_OPACITY=NO
MODE_SWITCH_MUTATES_USER_OPACITY=NO
ISOLATE_RESTORE_MUTATES_USER_OPACITY=NO
SHOW_HIDE_MUTATES_USER_OPACITY=NO
GEOMETRY_OR_LABEL_MAP_MUTATION=NO
PHASE6F_D_PER_STRUCTURE_CLIPPING=NOT_ENABLED
PHASE6F_E_EXPLODED_PRESENTATION=NOT_ENABLED
PHASE6F_F_FINAL_QUALIFICATION=NOT_CLOSED
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
