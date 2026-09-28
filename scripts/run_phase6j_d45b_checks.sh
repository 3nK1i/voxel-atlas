#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3 || command -v python)"; fi
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"

printf '%s\n' '===== PHASE 6J-D4.5B TARGETED BACKEND ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v \
    tests.test_phase6j_d45b_direct_mri_surface_backend \
    tests.test_phase6d1_volume_derived_surfaces

printf '%s\n' '===== PHASE 6J-D4.5B ISOLATED SCIENTIFIC RUNTIME ====='
test -x "$SURFACE_PYTHON"
PYTHONPATH="$ROOT/backend" "$PYTHON" scripts/check_phase6a_surface_environment.py --python "$SURFACE_PYTHON"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
  "$PYTHON" scripts/check_phase6j_d45b_direct_mri_surface_runtime.py --python "$SURFACE_PYTHON"

printf '%s\n' '===== PHASE 6J-D4.5B ARCHITECTURE ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
  "$PYTHON" scripts/check_phase6j_d45b_direct_mri_surface_architecture.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
  "$PYTHON" scripts/check_phase6d1_volume_surface_architecture.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
  "$PYTHON" scripts/check_phase6d1_volume_surface_worker.py --python "$SURFACE_PYTHON"

printf '%s\n' '===== PHASE 6J-D4 REGRESSION ====='
if [[ -x scripts/run_phase6j_d4_checks.sh ]]; then
  PYTHON="$PYTHON" VOXELATLAS_SURFACE_PYTHON="$SURFACE_PYTHON" \
    bash scripts/run_phase6j_d4_checks.sh
else
  echo 'PHASE6J_D4_REGRESSION=SKIPPED_SCRIPT_MISSING'
fi

printf '%s\n' '===== PHASE 6J-D4.5B STATIC VALIDATION ====='
"$PYTHON" -m py_compile \
  backend/voxelatlas/volume_surfaces.py \
  scripts/phase6d1_volume_surface_worker.py \
  scripts/check_phase6d1_volume_surface_architecture.py \
  scripts/check_phase6d1_volume_surface_worker.py \
  scripts/check_phase6j_d45b_direct_mri_surface_runtime.py \
  scripts/check_phase6j_d45b_direct_mri_surface_architecture.py \
  tests/test_phase6d1_volume_derived_surfaces.py \
  tests/test_phase6j_d45b_direct_mri_surface_backend.py

git diff --check

echo 'PHASE6J_D45B_CHECKS_OK=YES'
echo 'DIRECT_MR_BACKEND=QUALIFIED'
echo 'DIRECT_MR_UI_ACTIVATION=DEFERRED_TO_D45C'
echo 'DIRECT_MR_SEGMENTATION_REQUIRED=NO'
echo 'DIRECT_CT_BEHAVIOR=PRESERVED'
echo 'MRI_INFERENCE=NOT_RUN'
echo 'CLINICAL_VALIDATION=NOT_CLAIMED'
