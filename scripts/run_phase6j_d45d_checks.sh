#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3 || command -v python)"; fi
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6j-d45d-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6J_D45D_CHECK_TIMEOUT_SECONDS:-900}"

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
  "$PYTHON" scripts/check_phase6j_d45d_architecture.py >/dev/null
}

check_production_tree_untouched(){
  local changed
  changed="$({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sort -u)"
  ! printf '%s\n' "$changed" | grep -Eq '^(backend/|web/|requirements/|design/)'
}

check_real_qualifier_safety(){
  "$PYTHON" - <<'PY'
from pathlib import Path
source = Path('scripts/qualify_phase6j_d45d_real_mri.py').read_text(encoding='utf-8').lower()
for token in ('unlink(', 'rmtree(', 'write_bytes(', 'write_text(', 'np.save(', 'tofile(', 'open("w', "open('w"):
    if token in source:
        raise SystemExit(1)
for token in (
    'source_volume=immutable',
    'geometry_chain=patient_lps',
    'direct_mr_segmentation_required=no',
    'direct_mr_visual_review=manual_required',
    'direct_ct_backward_sanity=manual_required',
    'mri_inference=not_run',
    'clinical_validation=not_claimed',
):
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
  done < <(git ls-files --others --exclude-standard | grep -E 'phase6j_d45d|PHASE6J_D45D')
}

printf '%s\n' '===== PHASE 6J-D4.5D DIRECT MRI FINAL ACCEPTANCE ====='
run_quiet "D4.5D focused acceptance contracts" "$PYTHON" -m unittest -v tests.test_phase6j_d45d_direct_mri_acceptance
run_quiet "D4.5D qualification-only architecture probe" "$PYTHON" scripts/check_phase6j_d45d_architecture.py
run_quiet "D4.5C complete UI/CT/mode regression" env PYTHON="$PYTHON" VOXELATLAS_SURFACE_PYTHON="$SURFACE_PYTHON" bash scripts/run_phase6j_d45c_checks.sh
run_quiet "D4 semantic MRI surface regression" env PYTHON="$PYTHON" VOXELATLAS_SURFACE_PYTHON="$SURFACE_PYTHON" bash scripts/run_phase6j_d4_checks.sh
run_quiet "D4.5D Python compile" "$PYTHON" -m py_compile scripts/check_phase6j_d45d_architecture.py scripts/qualify_phase6j_d45d_real_mri.py tests/test_phase6j_d45d_direct_mri_acceptance.py
run_quiet "D4.5D qualifier CLI" "$PYTHON" scripts/qualify_phase6j_d45d_real_mri.py --help
run_quiet "D4.5D shell syntax" bash -n scripts/run_phase6j_d45d_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Qualification-only delta" check_qualification_only_delta
run_quiet "Production tree untouched" check_production_tree_untouched
run_quiet "Real MRI qualifier remains read-only" check_real_qualifier_safety
run_quiet "New-file whitespace" check_new_file_whitespace
run_quiet "Tracked diff whitespace" git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6J_D45D_AUTOMATED_CHECKS_OK=NO"
  exit 1
fi
cat <<'EOF'
PHASE6J_D45D_AUTOMATED_CHECKS_OK=YES
EXPECTED_BASE=c688507
QUALIFICATION_ONLY_DELTA=YES
PRODUCTION_IMPLEMENTATION_CHANGES=NO
DIRECT_MR_DEFAULT_ISOVALUE=0.50
SAMPLE_MANUAL_PREFERRED_ISOVALUE=0.35
DIRECT_MR_SIGNAL_BASIS=NORMALIZED
DIRECT_MR_SEGMENTATION_REQUIRED=NO
DIRECT_CT_DEFAULT_HU=300
DIRECT_CT_BEHAVIOR=PRESERVED
MODE_QUESTION_MARK_HELP=REMOVED
REAL_MRI_QUALIFICATION=RUN_SEPARATELY
MANUAL_MRI_CT_ACCEPTANCE=RUN_SEPARATELY
MRI_INFERENCE=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
