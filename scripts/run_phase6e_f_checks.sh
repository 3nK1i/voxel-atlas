#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6e-f-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6E_F_CHECK_TIMEOUT_SECONDS:-480}"

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

check_qualification_only_delta(){
  python scripts/check_phase6e_f_architecture.py >/dev/null
}

check_phase6e_production_unchanged(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^(backend/|web/|requirements/|design/)'
}

check_real_qualifier_safety(){
  python - <<'PY'
from pathlib import Path
source = Path('scripts/qualify_phase6e_f_real_study.py').read_text(encoding='utf-8').lower()
for token in ('unlink(', 'rmtree(', 'write_bytes(', 'tofile(', 'np.save(', 'open("w', "open('w"):
    if token in source:
        raise SystemExit(1)
required = (
    'source_volume=immutable',
    'source_label_map=immutable',
    'clinical_validation=not_claimed',
    'fidelity_visual_review=manual_required',
    'presentation_visual_review=manual_required',
    'combined_three_layer_visual_review=manual_required',
)
for token in required:
    if token not in source:
        raise SystemExit(1)
PY
}

check_new_file_whitespace(){
  local path
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    if grep -nE '[[:blank:]]+$' "$path" >/dev/null; then
      return 1
    fi
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6e_f|PHASE6E_F')
}

printf '%s\n' '===== PHASE 6E-F FINAL REAL-STUDY QUALIFICATION / PHASE 6E CLOSURE ====='
run_quiet "Phase 6E-F focused closure contracts" python -m unittest -v tests.test_phase6e_f_final_real_study_qualification
run_quiet "Phase 6E-F qualification-only architecture probe" python scripts/check_phase6e_f_architecture.py
run_quiet "Phase 6E-E focused regression" python -m unittest -v tests.test_phase6e_e_combined_mode_visual_balancing
run_quiet "Phase 6E-E combined presentation behavior regression" node scripts/check_phase6e_e_combined_presentation.mjs
run_quiet "Phase 6E-D focused regression" python -m unittest -v tests.test_phase6e_d_presentation_skull_cavity_polish
run_quiet "Phase 6E-D Presentation behavior regression" node scripts/check_phase6e_d_presentation_polish.mjs
run_quiet "Phase 6E-C focused regression" python -m unittest -v tests.test_phase6e_c_fidelity_profile_qualification
run_quiet "Phase 6E-C Fidelity round-trip regression" node scripts/check_phase6e_c_fidelity_profile.mjs
run_quiet "Phase 6E-B shared lighting/material regression" python -m unittest -v tests.test_phase6e_b_shared_lighting_material_foundation
run_quiet "Phase 6E-B shared presentation behavior regression" node scripts/check_phase6e_b_surface_presentation.mjs
run_quiet "Phase 6E-A profile architecture regression" python -m unittest -v tests.test_phase6e_a_presentation_profile_architecture
run_quiet "Phase 6E-A profile controller regression" node scripts/check_phase6e_a_presentation_profile_controller.mjs
run_quiet "Phase 6D2C combined/source regression" python -m unittest -v tests.test_phase6d2c_combined_visualization
run_quiet "Complete previous automated regression" python scripts/run_phase6e_f_previous_regression.py
run_quiet "Phase 6E-F Python compile" python -m py_compile scripts/check_phase6e_f_architecture.py scripts/qualify_phase6e_f_real_study.py scripts/run_phase6e_f_previous_regression.py tests/test_phase6e_f_final_real_study_qualification.py
run_quiet "Phase 6E-F qualifier CLI" python scripts/qualify_phase6e_f_real_study.py --help
run_quiet "Phase 6E-F shell syntax" bash -n scripts/run_phase6e_f_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Qualification-only delta" check_qualification_only_delta
run_quiet "Production rendering/geometry tree untouched" check_phase6e_production_unchanged
run_quiet "Real-study qualifier remains read-only" check_real_qualifier_safety
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6E_F_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6E_F_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=40937d706a7b54f3f23f882c9195ab5ed4992dc8
QUALIFICATION_ONLY_DELTA=YES
PHASE6E_PRODUCTION_RENDERING_CHANGES=NO
DIRECT_CT_DEFAULT_HU=300
FIDELITY_PRESENTATION_ARCHITECTURE=PRESERVED
COMBINED_PRESENTATION_BALANCE=PRESERVED
REAL_STUDY_QUALIFICATION=RUN_SEPARATELY
MANUAL_PRESENTATION_MATRIX=RUN_SEPARATELY
PHASE6E_CLOSURE=AFTER_REAL_STUDY_AND_MANUAL_PASS
PHASE6F_ADVANCED_INTERACTION=NOT_ENABLED
PHASE6G_QUANTITATIVE_SURFACE_TO_MASK_FIDELITY=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
