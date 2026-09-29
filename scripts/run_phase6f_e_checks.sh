#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6f-e-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6F_E_CHECK_TIMEOUT_SECONDS:-480}"

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
docs/phase_history/PHASE6F_E_ANATOMICAL_GROUP_EXPLODED_PRESENTATION.md
scripts/check_phase6f_e_architecture.py
scripts/check_phase6f_e_exploded_presentation.mjs
scripts/run_phase6f_e_checks.sh
scripts/run_phase6f_e_previous_regression.py
tests/test_phase6f_e_anatomical_group_exploded_presentation.py
web/css/styles.css
web/index.html
web/js/app.js
web/js/reconstruction-surface-clipping.js
web/js/segmentation-exploded-presentation.js
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
  if printf '%s\n' "$changed" | grep -Eq '^(backend/|requirements/|data/|uploads/|patient_data/|weights/|web/js/patient-volume-ray-marcher\.js$|web/js/segmentation-overlay\.js$|web/js/volume-surface-viewer\.js$|scripts/phase6a_surface_worker\.py$|scripts/phase6b_surface_worker\.py$)'; then
    return 1
  fi
}

check_explosion_geometry_io_free(){
  local added
  added="$(git diff --unified=0 -- web/js/segmentation-exploded-presentation.js web/js/segmentation-structure-interaction.js web/js/segmentation-structure-panel.js web/js/segmentation-surface-viewer.js web/js/reconstruction-surface-clipping.js web/js/app.js | grep '^+' | grep -v '^+++' || true)"
  if printf '%s\n' "$added" | grep -Eiq 'fetch\(|xmlhttprequest|marching_cubes|setattribute\("position"|setindex\(|geometry\.applymatrix4|/api/'; then
    return 1
  fi
}

check_display_transform_only(){
  grep -q 'item.mesh.position.set' web/js/segmentation-surface-viewer.js || return 1
  grep -q 'MAX_ANATOMICAL_GROUP_EXPLODE_MM = 40' web/js/segmentation-exploded-presentation.js || return 1
  grep -q 'descriptor.constant - normalDotOffset' web/js/reconstruction-surface-clipping.js || return 1
  ! grep -q 'segmentation-exploded-presentation' web/js/volume-surface-viewer.js
}

check_new_file_whitespace(){
  local path
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    if grep -nE '[[:blank:]]+$' "$path" >/dev/null; then
      return 1
    fi
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6f_e|PHASE6F_E|segmentation-exploded-presentation')
}

printf '%s\n' '===== PHASE 6F-E ANATOMICAL GROUP / BOUNDED EXPLODED PRESENTATION ====='
run_quiet "Phase 6F-E focused contracts" python -m unittest -v tests.test_phase6f_e_anatomical_group_exploded_presentation
run_quiet "Phase 6F-E exploded behavior" node scripts/check_phase6f_e_exploded_presentation.mjs
run_quiet "Phase 6F-E architecture probe" python scripts/check_phase6f_e_architecture.py
run_quiet "Phase 6F-D clipping behavior regression" node scripts/check_phase6f_d_clipping.mjs
run_quiet "Phase 6F-C transparency unit regression" python -m unittest -v tests.test_phase6f_c_structure_transparency_robustness
run_quiet "Phase 6F-C transparency behavior regression" node scripts/check_phase6f_c_transparency.mjs
run_quiet "Phase 6F-B interaction behavior regression" node scripts/check_phase6f_b_visibility_isolation.mjs
run_quiet "Phase 6F-A interaction behavior regression" node scripts/check_phase6f_a_structure_interaction.mjs
run_quiet "Phase 4E Patient-LPS clipping regression" python -m unittest -v tests.test_phase4e_multiplane_patient_space_clipping
run_quiet "Phase 4E clipping behavior regression" node scripts/check_phase4e_patient_clipping.mjs
run_quiet "Phase 6B fallback regression" python -m unittest -v tests.test_phase6b_refined_surface_accurate_fallback
run_quiet "Phase 6B fallback behavior regression" node scripts/check_phase6b_refined_surface_fallback.mjs
run_quiet "Phase 6E-F closure regression" python -m unittest -v tests.test_phase6e_f_final_real_study_qualification
run_quiet "Complete previous automated regression" python scripts/run_phase6f_e_previous_regression.py
run_quiet "Phase 6F-E Python compile" python -m py_compile scripts/check_phase6f_e_architecture.py scripts/run_phase6f_e_previous_regression.py tests/test_phase6f_e_anatomical_group_exploded_presentation.py
run_quiet "Exploded presentation JavaScript syntax" node --check web/js/segmentation-exploded-presentation.js
run_quiet "Surface clipping JavaScript syntax" node --check web/js/reconstruction-surface-clipping.js
run_quiet "Structure interaction JavaScript syntax" node --check web/js/segmentation-structure-interaction.js
run_quiet "Structure panel JavaScript syntax" node --check web/js/segmentation-structure-panel.js
run_quiet "Segmentation surface viewer syntax" node --check web/js/segmentation-surface-viewer.js
run_quiet "App JavaScript syntax" node --check web/js/app.js
run_quiet "6F-E behavior probe syntax" node --check scripts/check_phase6f_e_exploded_presentation.mjs
run_quiet "6F-E shell syntax" bash -n scripts/run_phase6f_e_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Exact Phase 6F-E candidate delta" check_exact_candidate_delta
run_quiet "Production boundary preservation" check_production_boundary
run_quiet "Explosion changes remain geometry/I-O free" check_explosion_geometry_io_free
run_quiet "Display transform remains bounded and segmentation-only" check_display_transform_only
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6F_E_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6F_E_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=6a3be6106a5f921058fbdc90a43428a1f6395dc6
ANATOMICAL_GROUP_MEMBERSHIP=CATALOG_AUTHORITATIVE
EXPLODED_PRESENTATION=BOUNDED_DISPLAY_TRANSFORM
MAX_ANATOMICAL_GROUP_EXPLODE_MM=40
GROUP_INTERNAL_RELATIONSHIPS=PRESERVED
MPR_PATIENT_LPS_PRESENTATION=UNCHANGED
DIRECT_CT_EXPLOSION=NO
EXPLOSION_CHANGES_FETCH_GEOMETRY=NO
EXPLOSION_CHANGES_MUTATE_GEOMETRY=NO
PATIENT_SPACE_GEOMETRY_MUTATION=NO
SOURCE_LABEL_MAP_MUTATION=NO
USER_STRUCTURE_OPACITY=PRESERVED
ISOLATION_STATE=PRESERVED
CLIPPING_PARTICIPATION=PRESERVED
DIRECTIONAL_CUT_FOLLOWS_EXPLODED_DISPLAY_OFFSET=YES
PHASE6F_F_FINAL_QUALIFICATION=NOT_CLOSED
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
