#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3 || command -v python)"; fi

echo '===== PHASE 6J-D3 TARGETED PYTHON ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d3_mri_mpr_overlays

echo '===== PHASE 6J-D3 TARGETED BROWSER ====='
node scripts/check_phase6j_d3_mri_mpr_overlay.mjs

echo '===== PHASE 6J-D3 PRIOR MRI C4C + D2 ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v \
    tests.test_phase6j_c4c_mri_workflow_presentation \
    tests.test_phase6j_d2_mri_label_map_import
node scripts/check_phase6j_b1_mri_workflow.mjs
node scripts/check_phase6j_b2b_mri_study_workflows.mjs
node scripts/check_phase6j_c4c_mri_workflow.mjs

echo '===== PHASE 6J-D3 EXISTING MPR + STRUCTURE REGRESSION ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v \
    tests.test_phase5d_synchronized_mpr_segmentation_overlay \
    tests.test_phase5e_anatomical_structure_panel \
    tests.test_phase6i_b2_existing_segmentation_mode
node scripts/check_phase5e_structure_panel.mjs
node scripts/check_phase6d0_explicit_surface_selection.mjs

echo '===== PHASE 6J-D3 STATIC VALIDATION ====='
"$PYTHON" -m py_compile \
  backend/voxelatlas/mri_workflow_presentation.py \
  backend/voxelatlas/segmentation_workflow.py \
  tests/test_phase6j_d3_mri_mpr_overlays.py
node --check web/js/app.js
node --check web/js/segmentation-workflow-panel.js
node --check scripts/check_phase6j_d3_mri_mpr_overlay.mjs
git diff --check

echo 'PHASE6J_D3_CHECKS_OK=YES'
echo 'MRI_INFERENCE=NOT_RUN'
echo 'PRODUCTION_MRI_IMPORT=NOT_RUN'
echo 'MRI_3D_SURFACE_INTEGRATION=NOT_ENABLED'
