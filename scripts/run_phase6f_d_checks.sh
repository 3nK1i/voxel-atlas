#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6f-d-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6F_D_CHECK_TIMEOUT_SECONDS:-480}"

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
docs/phase_history/PHASE6F_D_PER_STRUCTURE_CLIPPING_PARTICIPATION.md
scripts/check_phase6f_d_architecture.py
scripts/check_phase6f_d_clipping.mjs
scripts/run_phase6f_d_checks.sh
scripts/run_phase6f_d_previous_regression.py
tests/test_phase6f_d_per_structure_clipping_participation.py
web/css/styles.css
web/index.html
web/js/app.js
web/js/reconstruction-surface-clipping.js
web/js/segmentation-structure-panel.js
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
  if printf '%s\n' "$changed" | grep -Eq '^(backend/|requirements/|data/|uploads/|patient_data/|weights/|web/js/patient-volume-ray-marcher\.js$|web/js/segmentation-overlay\.js$|scripts/phase6a_surface_worker\.py$|scripts/phase6b_surface_worker\.py$)'; then
    return 1
  fi
}

check_clipping_changes_geometry_io_free(){
  local added
  added="$(git diff --unified=0 -- web/js/reconstruction-surface-clipping.js web/js/segmentation-structure-panel.js web/js/segmentation-surface-viewer.js web/js/volume-surface-viewer.js web/js/app.js | grep '^+' | grep -v '^+++' || true)"
  if printf '%s\n' "$added" | grep -Eiq 'fetch\(|xmlhttprequest|marching_cubes|setattribute\("position"|setindex\(|geometry\.applymatrix4|vertices|indices|/api/'; then
    return 1
  fi
}

check_single_directional_cut_system(){
  local helper panel html
  helper="$(cat web/js/reconstruction-surface-clipping.js)"
  panel="$(cat web/js/segmentation-structure-panel.js)"
  html="$(cat web/index.html)"
  [[ "$helper" == *"resolvePatientSurfaceClippingDescriptors"* ]] || return 1
  [[ "$panel" == *"clippingEnabled"* ]] || return 1
  [[ "$html" == *"Follow Directional Cut"* ]] || return 1
  [[ "$html" != *"segmentationStructureExplode"* ]] || return 1
}

check_new_file_whitespace(){
  local path
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    if grep -nE '[[:blank:]]+$' "$path" >/dev/null; then
      return 1
    fi
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6f_d|PHASE6F_D|reconstruction-surface-clipping')
}

printf '%s\n' '===== PHASE 6F-D PER-STRUCTURE CLIPPING PARTICIPATION ====='
run_quiet "Phase 6F-D focused contracts" python -m unittest -v tests.test_phase6f_d_per_structure_clipping_participation
run_quiet "Phase 6F-D clipping behavior" node scripts/check_phase6f_d_clipping.mjs
run_quiet "Phase 6F-D architecture probe" python scripts/check_phase6f_d_architecture.py
run_quiet "Phase 6F-C transparency unit regression" python -m unittest -v tests.test_phase6f_c_structure_transparency_robustness
run_quiet "Phase 6F-C transparency behavior regression" node scripts/check_phase6f_c_transparency.mjs
run_quiet "Phase 6F-B interaction behavior regression" node scripts/check_phase6f_b_visibility_isolation.mjs
run_quiet "Phase 6F-A interaction behavior regression" node scripts/check_phase6f_a_structure_interaction.mjs
run_quiet "Phase 4E Patient-LPS clipping regression" python -m unittest -v tests.test_phase4e_multiplane_patient_space_clipping
run_quiet "Phase 4E clipping behavior regression" node scripts/check_phase4e_patient_clipping.mjs
run_quiet "Phase 6B fallback regression" python -m unittest -v tests.test_phase6b_refined_surface_accurate_fallback
run_quiet "Phase 6B fallback behavior regression" node scripts/check_phase6b_refined_surface_fallback.mjs
run_quiet "Phase 6E-F closure regression" python -m unittest -v tests.test_phase6e_f_final_real_study_qualification
run_quiet "Complete previous automated regression" python scripts/run_phase6f_d_previous_regression.py
run_quiet "Phase 6F-D Python compile" python -m py_compile scripts/check_phase6f_d_architecture.py scripts/run_phase6f_d_previous_regression.py tests/test_phase6f_d_per_structure_clipping_participation.py
run_quiet "Surface clipping JavaScript syntax" node --check web/js/reconstruction-surface-clipping.js
run_quiet "Structure panel JavaScript syntax" node --check web/js/segmentation-structure-panel.js
run_quiet "Segmentation surface viewer syntax" node --check web/js/segmentation-surface-viewer.js
run_quiet "Direct CT surface viewer syntax" node --check web/js/volume-surface-viewer.js
run_quiet "App JavaScript syntax" node --check web/js/app.js
run_quiet "6F-D behavior probe syntax" node --check scripts/check_phase6f_d_clipping.mjs
run_quiet "6F-D shell syntax" bash -n scripts/run_phase6f_d_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Exact Phase 6F-D candidate delta" check_exact_candidate_delta
run_quiet "Production boundary preservation" check_production_boundary
run_quiet "Clipping changes remain geometry/I-O free" check_clipping_changes_geometry_io_free
run_quiet "Directional Cut remains the only clipping system" check_single_directional_cut_system
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6F_D_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6F_D_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=6f036c7cf53ad05edad2f988d4c6280d510b69ca
DIRECTIONAL_CUT_SYSTEM=REUSED
PATIENT_LPS_CLIPPING_BOUNDS=SHARED_WITH_VOLUME
DIRECT_CT_SURFACE_FOLLOWS_DIRECTIONAL_CUT=YES
SEGMENTATION_CLIPPING_PARTICIPATION=PER_STRUCTURE
STRUCTURE_CLIPPING_DEFAULT=ENABLED
STRUCTURE_CLIP_IGNORE=PRESERVES_RESIDENT_GEOMETRY
CLIPPING_CHANGES_FETCH_GEOMETRY=NO
CLIPPING_CHANGES_MUTATE_GEOMETRY=NO
PATIENT_SPACE_GEOMETRY_MUTATION=NO
SOURCE_LABEL_MAP_MUTATION=NO
USER_STRUCTURE_OPACITY=PRESERVED
ISOLATION_STATE=PRESERVED
PHASE6F_E_EXPLODED_PRESENTATION=NOT_ENABLED
PHASE6F_F_FINAL_QUALIFICATION=NOT_CLOSED
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
