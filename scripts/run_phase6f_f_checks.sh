#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6f-f-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6F_F_CHECK_TIMEOUT_SECONDS:-480}"

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


run_unittest_module_excluding(){
  local module="$1"; shift
  python - "$module" "$@" <<'PYFILTER'
import sys
import unittest

module_name = sys.argv[1]
excluded_methods = set(sys.argv[2:])

suite = unittest.defaultTestLoader.loadTestsFromName(module_name)

def iter_tests(node):
    for item in node:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item

selected = unittest.TestSuite()
excluded_found = set()
for test in iter_tests(suite):
    method = test.id().rsplit(".", 1)[-1]
    if method in excluded_methods:
        excluded_found.add(method)
        continue
    selected.addTest(test)

missing = sorted(excluded_methods - excluded_found)
if missing:
    print("SUPERSEDED_ASSERTION_FILTER=FAIL")
    print("MISSING_SUPERSEDED_ASSERTIONS=" + ",".join(missing))
    raise SystemExit(2)

print("SUPERSEDED_ASSERTION_FILTER=PASS")
print("EXCLUDED_SUPERSEDED_ASSERTIONS=" + ",".join(sorted(excluded_found)))
result = unittest.TextTestRunner(verbosity=2).run(selected)
raise SystemExit(0 if result.wasSuccessful() else 1)
PYFILTER
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
docs/phase_history/PHASE6F_F_FINAL_REAL_STUDY_INTERACTION_QUALIFICATION_AND_CLOSURE.md
scripts/check_phase6f_f_architecture.py
scripts/qualify_phase6f_f_real_study.py
scripts/run_phase6f_f_checks.sh
scripts/run_phase6f_f_previous_regression.py
tests/test_phase6f_f_final_real_study_interaction_qualification.py
EOF
)"
  actual="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | LC_ALL=C sort -u)"
  [[ "$actual" == "$expected" ]]
}

check_qualification_only_delta(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | sort -u)"
  [[ -n "$changed" ]] || return 1
  if printf '%s\n' "$changed" | grep -Ev '^(docs/phase_history/PHASE6F_F_FINAL_REAL_STUDY_INTERACTION_QUALIFICATION_AND_CLOSURE\.md|scripts/(check_phase6f_f_architecture|qualify_phase6f_f_real_study|run_phase6f_f_checks|run_phase6f_f_previous_regression)\.(py|sh)|tests/test_phase6f_f_final_real_study_interaction_qualification\.py)$' | grep -q .; then
    return 1
  fi
}

check_production_tree_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sed '/^$/d' | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^(backend/|requirements/|web/|data/|uploads/|patient_data/|weights/|scripts/phase6a_surface_worker\.py$|scripts/phase6b_surface_worker\.py$)'
}

check_real_study_qualifier_read_only(){
  local q="scripts/qualify_phase6f_f_real_study.py"
  grep -q 'qualify_phase6e_f_real_study.py' "$q" || return 1
  grep -q 'PHASE6F_F_REAL_STUDY_SOURCE_GATE_OK=YES' "$q" || return 1
  if grep -Eq 'write_text\(|write_bytes\(|unlink\(|rmdir\(|shutil\.(rmtree|copy|move)|requests\.|httpx\.' "$q"; then
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
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6f_f|PHASE6F_F')
}

printf '%s\n' '===== PHASE 6F-F FINAL REAL-STUDY INTERACTION QUALIFICATION / PHASE 6F CLOSURE ====='
run_quiet "Phase 6F-F focused closure contracts" python -m unittest -v tests.test_phase6f_f_final_real_study_interaction_qualification
run_quiet "Phase 6F-F qualification-only architecture probe" python scripts/check_phase6f_f_architecture.py
run_quiet "Phase 6F-E focused regression" python -m unittest -v tests.test_phase6f_e_anatomical_group_exploded_presentation
run_quiet "Phase 6F-E exploded behavior regression" node scripts/check_phase6f_e_exploded_presentation.mjs
run_quiet "Phase 6F-D focused regression" run_unittest_module_excluding \
  tests.test_phase6f_d_per_structure_clipping_participation \
  test_phase6f_d_stays_inside_roadmap_boundary
run_quiet "Phase 6F-D clipping behavior regression" node scripts/check_phase6f_d_clipping.mjs
run_quiet "Phase 6F-C transparency unit regression" python -m unittest -v tests.test_phase6f_c_structure_transparency_robustness
run_quiet "Phase 6F-C transparency behavior regression" node scripts/check_phase6f_c_transparency.mjs
run_quiet "Phase 6F-B interaction unit regression" run_unittest_module_excluding \
  tests.test_phase6f_b_non_destructive_visibility_isolation \
  test_6fb_does_not_enable_later_interaction_features
run_quiet "Phase 6F-B interaction behavior regression" node scripts/check_phase6f_b_visibility_isolation.mjs
run_quiet "Phase 6F-A interaction unit regression" run_unittest_module_excluding \
  tests.test_phase6f_a_structure_interaction_state \
  test_phase6f_a_foundation_keeps_later_interaction_features_out_of_scope
run_quiet "Phase 6F-A interaction behavior regression" node scripts/check_phase6f_a_structure_interaction.mjs
run_quiet "Phase 6B fallback regression" python -m unittest -v tests.test_phase6b_refined_surface_accurate_fallback
run_quiet "Phase 6B fallback behavior regression" node scripts/check_phase6b_refined_surface_fallback.mjs
run_quiet "Phase 6E-F closure regression" python -m unittest -v tests.test_phase6e_f_final_real_study_qualification
run_quiet "Complete previous automated regression" python scripts/run_phase6f_f_previous_regression.py
run_quiet "Phase 6F-F Python compile" python -m py_compile scripts/check_phase6f_f_architecture.py scripts/qualify_phase6f_f_real_study.py scripts/run_phase6f_f_previous_regression.py tests/test_phase6f_f_final_real_study_interaction_qualification.py
run_quiet "6F-F shell syntax" bash -n scripts/run_phase6f_f_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Exact Phase 6F-F candidate delta" check_exact_candidate_delta
run_quiet "Qualification-only delta" check_qualification_only_delta
run_quiet "Production rendering/geometry tree untouched" check_production_tree_untouched
run_quiet "Real-study qualifier remains read-only" check_real_study_qualifier_read_only
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6F_F_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6F_F_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=4d589c2a44704d7be9039786d535b670461b8460
QUALIFICATION_ONLY_DELTA=YES
PHASE6F_PRODUCTION_RENDERING_CHANGES=NO
INTERACTION_STACK=PHASE6F_A_THROUGH_E_PRESERVED
SHOW_HIDE_ISOLATE_RESTORE=PRESERVED
USER_STRUCTURE_OPACITY=PRESERVED
PER_STRUCTURE_CLIPPING_PARTICIPATION=PRESERVED
BOUNDED_EXPLODED_PRESENTATION=PRESERVED
FIDELITY_PRESENTATION_ROUNDTRIP=PRESERVED
SURFACE_COMBINED_ROUNDTRIP=PRESERVED
REFINED_TO_ACCURATE_FALLBACK=PRESERVED
REAL_STUDY_SOURCE_GATE=RUN_SEPARATELY
MANUAL_INTERACTION_MATRIX=RUN_SEPARATELY
PHASE6F_CLOSURE=AFTER_REAL_STUDY_AND_MANUAL_PASS
DIRECT_CT_300_HU_SLAB_INVESTIGATION=DEFERRED_POST_PHASE6F
PHASE6G_QUANTITATIVE_SURFACE_TO_MASK_FIDELITY=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
