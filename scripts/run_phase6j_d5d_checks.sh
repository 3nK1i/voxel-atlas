#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || command -v python)"
fi

SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6j-d5d-checks.XXXXXXXX)" || exit 1
FAIL=0
CHECK_TIMEOUT_SECONDS="${PHASE6J_D5D_CHECK_TIMEOUT_SECONDS:-1200}"

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
    tail -n 220 "$log"
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

  allowed="$(cat <<'EOF'
docs/phase_history/PHASE6J_D5D_INTEGRATED_LIFECYCLE_ACCEPTANCE.md
scripts/run_phase6j_d5d_checks.sh
tests/test_phase6j_d5d_integrated_acceptance.py
EOF
)"

  unexpected="$(comm -23 <(printf '%s\n' "$actual" | sed '/^$/d' | sort -u) <(printf '%s\n' "$allowed" | sort -u))"
  [[ -z "$unexpected" ]]
}

check_patient_data_safety(){
  ! git ls-files --cached --others --exclude-standard \
    | grep -Eiv '(^|/)\.env\.example$' \
    | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2|vxvs)$|(^|/)\.env($|\.)'
}

check_d45d_qualifier_read_only(){
  "$PYTHON" - <<'PY'
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
PY
}

printf '%s\n' '===== PHASE 6J-D5D INTEGRATED MRI / CT LIFECYCLE ACCEPTANCE ====='

run_quiet "D5D focused integrated acceptance contracts" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d5d_integrated_acceptance

run_quiet "D5C full current lifecycle gate" \
  env PYTHON="$PYTHON" VOXELATLAS_SURFACE_PYTHON="$SURFACE_PYTHON" \
  bash scripts/run_phase6j_d5c_checks.sh

run_quiet "D2 canonical MRI import contract" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d2_mri_label_map_import

# Do not call scripts/run_phase6j_d45d_checks.sh here. Its qualification-only
# delta guard is intentionally bound to historical D4.5D base c688507.
run_quiet "D4.5D focused acceptance contract" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d45d_direct_mri_acceptance

run_quiet "D4.5D real-MRI qualifier CLI remains available" \
  "$PYTHON" scripts/qualify_phase6j_d45d_real_mri.py --help

run_quiet "D4.5D real-MRI qualifier remains read-only" \
  check_d45d_qualifier_read_only

run_quiet "D5D Python compile" \
  "$PYTHON" -m py_compile \
    tests/test_phase6j_d5d_integrated_acceptance.py \
    scripts/qualify_phase6j_d45d_real_mri.py

run_quiet "D5D shell syntax" \
  bash -n scripts/run_phase6j_d5d_checks.sh

run_quiet "D5D qualification-only delta" \
  check_qualification_only_delta

run_quiet "Patient-data Git safety" \
  check_patient_data_safety

run_quiet "D5D whitespace" \
  git diff --check

echo "CHECK_LOG_DIR=$LOG_DIR"

if [[ "$FAIL" -ne 0 ]]; then
  echo "PHASE6J_D5D_CHECKS_OK=NO"
  exit 1
fi

cat <<'EOF'
PHASE6J_D5D_CHECKS_OK=YES
D2_CANONICAL_MRI_IMPORT_CONTRACT=PRESERVED
D3_MRI_MPR_OVERLAY_CONTRACT=PRESERVED
D4_SEMANTIC_MRI_SURFACE_CONTRACT=PRESERVED
D45_DIRECT_MR_CONTRACT=PRESERVED
D5B_CROSS_STUDY_LIFECYCLE=PRESERVED
D5C_SAME_STUDY_LIFECYCLE=PRESERVED
DIRECT_CT_BACKWARD_COMPATIBILITY=PRESERVED
D45D_HISTORICAL_DELTA_GUARD=NOT_REPLAYED
D5D_PRODUCTION_IMPLEMENTATION_CHANGES=NO
MRI_INFERENCE=NOT_RUN
PRODUCTION_MRI_IMPORT=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
TEST_RC=0
EOF
