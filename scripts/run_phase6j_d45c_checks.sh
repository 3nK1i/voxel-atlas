#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3 || command -v python)"; fi
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"

printf '%s\n' '===== PHASE 6J-D4.5C TARGETED UI / DIRECT MR ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v \
    tests.test_phase6j_d45c_direct_mri_surface_ui \
    tests.test_phase6j_d45b_direct_mri_surface_backend \
    tests.test_phase6i_a_contextual_help_contract \
    tests.test_phase6i_integrated_ergonomics

node scripts/check_phase6j_d45c_direct_mri_surface_viewer.mjs
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
  "$PYTHON" scripts/check_phase6j_d45c_direct_mri_surface_architecture.py

printf '%s\n' '===== PHASE 6J-D4.5C CT + MODE REGRESSION ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v \
    tests.test_phase6d1_volume_derived_surfaces \
    tests.test_phase6d2b_volume_surface_transitions \
    tests.test_phase6d2c_combined_visualization \
    tests.test_phase6i_b1_automatic_direct_ct_mode
node scripts/check_phase6d1_volume_surface_viewer.mjs
node scripts/check_phase6d2b_nondestructive_visibility.mjs
node scripts/check_phase6d2c_combined_mode.mjs

printf '%s\n' '===== PHASE 6J-D4.5B SCIENTIFIC BACKEND REGRESSION ====='
test -x "$SURFACE_PYTHON"
PYTHONPATH="$ROOT/backend" "$PYTHON" scripts/check_phase6a_surface_environment.py --python "$SURFACE_PYTHON"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
  "$PYTHON" scripts/check_phase6j_d45b_direct_mri_surface_runtime.py --python "$SURFACE_PYTHON"

printf '%s\n' '===== PHASE 6J-D4.5C STATIC VALIDATION ====='
"$PYTHON" -m py_compile \
  backend/voxelatlas/volume_surfaces.py \
  scripts/check_phase6j_d45c_direct_mri_surface_architecture.py \
  tests/test_phase6j_d45c_direct_mri_surface_ui.py \
  tests/test_phase6j_d45b_direct_mri_surface_backend.py \
  tests/test_phase6i_a_contextual_help_contract.py \
  tests/test_phase6i_integrated_ergonomics.py
node --check web/js/app.js
node --check web/js/volume-surface-viewer.js
node --check web/js/parameter-help.js
node --check scripts/check_phase6j_d45c_direct_mri_surface_viewer.mjs
git diff --check

echo 'PHASE6J_D45C_CHECKS_OK=YES'
echo 'DIRECT_MR_UI=ENABLED'
echo 'DIRECT_MR_SURFACE_AND_COMBINED=ENABLED'
echo 'DIRECT_MR_SEGMENTATION_REQUIRED=NO'
echo 'DIRECT_MR_SIGNAL_BASIS=NORMALIZED'
echo 'DIRECT_CT_BEHAVIOR=PRESERVED'
echo 'MODE_QUESTION_MARK_HELP=REMOVED'
echo 'MRI_INFERENCE=NOT_RUN'
echo 'CLINICAL_VALIDATION=NOT_CLAIMED'
