#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6b-refined-fallback.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6B_FALLBACK_CHECK_TIMEOUT_SECONDS:-480}"

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
docs/phase_history/PHASE6B_REFINED_SURFACE_ACCURATE_FALLBACK_CORRECTION.md
scripts/check_phase6b_refined_surface_fallback.mjs
scripts/run_phase6b_refined_surface_fallback_checks.sh
scripts/run_phase6b_refined_surface_fallback_previous_regression.py
tests/test_phase6b_refined_surface_accurate_fallback.py
web/index.html
web/js/app.js
web/js/segmentation-surface-viewer.js
EOF
)"
  actual="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | LC_ALL=C sort -u)"
  [[ "$actual" == "$expected" ]]
}

check_refinement_policy_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | LC_ALL=C sort -u)"
  if printf '%s\n' "$changed" | grep -Eq '^(backend/|scripts/phase6a_surface_worker\.py$|scripts/phase6b_surface_worker\.py$|requirements/)'; then
    return 1
  fi
  grep -Fq 'accurate reference topology cannot be repaired within bounded local face-only policy' scripts/phase6b_surface_worker.py \
    && grep -Fq 'REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES = 12' backend/voxelatlas/segmentation_surfaces.py \
    && grep -Fq 'REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES = 6' backend/voxelatlas/segmentation_surfaces.py
}

check_fallback_scope(){
  grep -Fq 'requestedQuality === "refined"' web/js/segmentation-surface-viewer.js \
    && grep -Fq 'fallbackQuality === "accurate"' web/js/segmentation-surface-viewer.js \
    && grep -Fq 'result.response.status === 422' web/js/segmentation-surface-viewer.js \
    && grep -Fq 'presentationFallback' web/js/segmentation-surface-viewer.js \
    && grep -Fq 'accurate fallback' web/js/segmentation-surface-viewer.js
}

check_new_file_whitespace(){
  local path
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    if grep -nE '[[:blank:]]+$' "$path" >/dev/null; then
      return 1
    fi
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6b_refined|PHASE6B_REFINED')
}

printf '%s\n' '===== PHASE 6B REFINED -> ACCURATE PRESENTATION FALLBACK CORRECTION ====='
run_quiet "Focused fallback contracts" python -m unittest -v tests.test_phase6b_refined_surface_accurate_fallback
run_quiet "Refined-to-accurate browser behavior" node scripts/check_phase6b_refined_surface_fallback.mjs
run_quiet "Phase 6B bounded refinement regression" python -m unittest -v tests.test_phase6b_bounded_surface_refinement
run_quiet "Phase 6F-B interaction regression" python -m unittest -v tests.test_phase6f_b_non_destructive_visibility_isolation
run_quiet "Phase 6F-B browser behavior regression" node scripts/check_phase6f_b_visibility_isolation.mjs
run_quiet "Phase 6C multi-structure viewer regression" node scripts/check_phase6c_multi_structure_viewer.mjs
run_quiet "Phase 6E-F closure regression" python -m unittest -v tests.test_phase6e_f_final_real_study_qualification
run_quiet "Complete previous automated regression" python scripts/run_phase6b_refined_surface_fallback_previous_regression.py
run_quiet "Python compile" python -m py_compile tests/test_phase6b_refined_surface_accurate_fallback.py scripts/run_phase6b_refined_surface_fallback_previous_regression.py
run_quiet "Surface viewer JavaScript syntax" node --check web/js/segmentation-surface-viewer.js
run_quiet "App JavaScript syntax" node --check web/js/app.js
run_quiet "Fallback behavior probe syntax" node --check scripts/check_phase6b_refined_surface_fallback.mjs
run_quiet "Shell syntax" bash -n scripts/run_phase6b_refined_surface_fallback_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Exact correction candidate delta" check_exact_candidate_delta
run_quiet "Refinement policy untouched" check_refinement_policy_untouched
run_quiet "Fallback scope is narrow and explicit" check_fallback_scope
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6B_REFINED_SURFACE_FALLBACK_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6B_REFINED_SURFACE_FALLBACK_CHECKS_OK=YES
EXPECTED_BASE=96d590a1367c1fa93f3be4ab8f9dcce9d7bf17ad
PRESENTATION_PRIMARY_QUALITY=REFINED
REFINED_HTTP_422_FALLBACK=ACCURATE
NON_422_REFINEMENT_FAILURE_FALLBACK=NO
FALLBACK_STATUS=EXPLICIT_ACCURATE_FALLBACK
REFINEMENT_POLICY_RELAXED=NO
PHASE6B_WORKER_CHANGED=NO
PATIENT_SPACE_GEOMETRY_MUTATION=NO
SOURCE_LABEL_MAP_MUTATION=NO
PHASE6F_C_TRANSPARENCY_QUALIFICATION=NOT_ENABLED
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
