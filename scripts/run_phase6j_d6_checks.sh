#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || command -v python)"
fi
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6j-d6-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6J_D6_CHECK_TIMEOUT_SECONDS:-1500}"

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
    tail -n 240 "$log"
    FAIL=1
  fi
}

check_qualification_only_delta(){
  local actual allowed unexpected
  actual="$({
    git diff --name-only
    git diff --cached --name-only
    git ls-files --others --exclude-standard
  } | sort -u)"

  allowed="$(cat <<'ALLOWEND'
docs/phase_history/PHASE6J_D6_FINAL_PHASE_D_ACCEPTANCE.md
scripts/run_phase6j_d6_checks.sh
tests/test_phase6j_d6_final_phase_d_acceptance.py
ALLOWEND
)"

  unexpected="$(comm -23 \
    <(printf '%s\n' "$actual" | sed '/^$/d' | sort -u) \
    <(printf '%s\n' "$allowed" | sort -u))"
  [[ -z "$unexpected" ]]
}

check_patient_data_safety(){
  ! git ls-files --cached --others --exclude-standard \
    | grep -Eiv '(^|/)\.env\.example$' \
    | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2|vxvs)$|(^|/)\.env($|\.)'
}

check_real_qualifier_read_only(){
  "$PYTHON" - <<'PYBLOCK'
from pathlib import Path
source = Path("scripts/qualify_phase6j_d45d_real_mri.py").read_text(encoding="utf-8").lower()
for token in ("unlink(", "rmtree(", "write_bytes(", "write_text(", "np.save(", "tofile(", 'open("w', "open('w"):
    if token in source:
        raise SystemExit(1)
for token in (
    "source_volume=immutable",
    "geometry_chain=patient_lps",
    "direct_mr_segmentation_required=no",
    "mri_inference=not_run",
    "clinical_validation=not_claimed",
):
    if token not in source:
        raise SystemExit(1)
PYBLOCK
}

printf '%s\n' '===== PHASE 6J-D6 FINAL PHASE-D ACCEPTANCE ====='

run_quiet "D6 focused final Phase-D contracts" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d6_final_phase_d_acceptance

# D5D's whole runner is intentionally not replayed here because its exact-delta
# guard belongs to the already-closed D5D three-file qualification step.
run_quiet "D5D focused integrated acceptance contract" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d5d_integrated_acceptance

# D5C is the current production lifecycle chain and safely nests D5B + D4.5C + D4.
run_quiet "D5C full current production lifecycle gate" \
  env PYTHON="$PYTHON" VOXELATLAS_SURFACE_PYTHON="$SURFACE_PYTHON" \
  bash scripts/run_phase6j_d5c_checks.sh

# D2 stage reporting is not part of the D5D focused canonical-import invocation;
# include it explicitly in the final Phase-D gate.
run_quiet "D2 import-stage reporting regression" \
  env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest discover -s tests -p 'test_phase6j_d2_import_stage_reporting.py' -v

# Do not call scripts/run_phase6j_d45d_checks.sh as a whole: its historical
# qualification-only delta guard is bound to the old D4.5D base.
run_quiet "D4.5D focused acceptance contract" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d45d_direct_mri_acceptance

run_quiet "D4.5D real-MRI qualifier CLI remains available" \
  "$PYTHON" scripts/qualify_phase6j_d45d_real_mri.py --help

run_quiet "D4.5D real-MRI qualifier remains read-only" \
  check_real_qualifier_read_only

run_quiet "D6 Python compile" \
  "$PYTHON" -m py_compile \
    tests/test_phase6j_d6_final_phase_d_acceptance.py \
    tests/test_phase6j_d5d_integrated_acceptance.py \
    tests/test_phase6j_d2_import_stage_reporting.py \
    scripts/qualify_phase6j_d45d_real_mri.py

run_quiet "D6 shell syntax" \
  bash -n scripts/run_phase6j_d6_checks.sh

run_quiet "D6 qualification-only delta" \
  check_qualification_only_delta

run_quiet "Patient-data Git safety" \
  check_patient_data_safety

run_quiet "D6 whitespace" \
  git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"

if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6J_D6_CHECKS_OK=NO"
  exit 1
fi

cat <<'RESULTEND'
PHASE6J_D6_CHECKS_OK=YES
PHASE_D_D2_CANONICAL_IMPORT=ACCEPTED_AND_PRESERVED
PHASE_D_D3_MPR_OVERLAYS=PRESERVED
PHASE_D_D4_SEMANTIC_SURFACES=PRESERVED
PHASE_D_D45_DIRECT_MR=PRESERVED
PHASE_D_D5_LIFECYCLE=PRESERVED
PATIENT_LPS_PROVENANCE=PRESERVED
DIRECT_CT_300HU_COMPATIBILITY=PRESERVED
D45D_HISTORICAL_DELTA_GUARD=NOT_REPLAYED
D5D_PREVIOUS_STEP_DELTA_GUARD=NOT_REPLAYED
D6_PRODUCTION_IMPLEMENTATION_CHANGES=NO
MRI_INFERENCE=NOT_RUN
PRODUCTION_MRI_IMPORT=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
RESULTEND
