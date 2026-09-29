#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3 || command -v python)"; fi
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
if [[ ! -x "$SURFACE_PYTHON" ]]; then
  echo 'PHASE6J_D4_SURFACE_RUNTIME=UNAVAILABLE'
  exit 1
fi

echo '===== PHASE 6J-D4 TARGETED MRI 3D ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v tests.test_phase6j_d4_mri_segmentation_surfaces

echo '===== PHASE 6J-D4 ISOLATED SCIENTIFIC RUNTIME ====='
PYTHONDONTWRITEBYTECODE=1 \
  "$SURFACE_PYTHON" -I scripts/check_phase6j_d4_mri_presentation_runtime.py

node scripts/check_phase6j_d4_mri_3d_surfaces.mjs
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" scripts/check_phase6b_surface_architecture.py

echo '===== PHASE 6J-D4 PRIOR MRI D3 / D2 / C4C ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v \
    tests.test_phase6j_d3_mri_mpr_overlays \
    tests.test_phase6j_d2_mri_label_map_import \
    tests.test_phase6j_c4c_mri_workflow_presentation
node scripts/check_phase6j_d3_mri_mpr_overlay.mjs
node scripts/check_phase6j_c4c_mri_workflow.mjs
node scripts/check_phase6j_b1_mri_workflow.mjs
node scripts/check_phase6j_b2b_mri_study_workflows.mjs

echo '===== PHASE 6J-D4 EXISTING 3D SURFACE + MODE REGRESSION ====='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend:$ROOT/tests" \
  "$PYTHON" -m unittest -v \
    tests.test_phase5f1_segmentation_derived_3d_surfaces \
    tests.test_phase6d2a_visualization_mode_controller \
    tests.test_phase6d2b_volume_surface_transitions \
    tests.test_phase6d2c_combined_visualization \
    tests.test_phase6i_b2_existing_segmentation_mode
node scripts/check_phase6a_surface_viewer.mjs
node scripts/check_phase6b_surface_viewer.mjs
node scripts/check_phase6d2a_visualization_mode_controller.mjs
node scripts/check_phase6d2b_nondestructive_visibility.mjs
node scripts/check_phase6d2c_combined_mode.mjs
node scripts/check_phase6d0_explicit_surface_selection.mjs

echo '===== PHASE 6J-D4 STATIC VALIDATION ====='
"$PYTHON" -m py_compile \
  backend/voxelatlas/segmentation_surfaces.py \
  scripts/phase6b_surface_worker.py \
  scripts/check_phase6j_d4_mri_presentation_runtime.py \
  scripts/check_phase6b_surface_architecture.py \
  tests/test_phase6j_d4_mri_segmentation_surfaces.py
node --check web/js/app.js
node --check scripts/check_phase6j_d4_mri_3d_surfaces.mjs
node --check scripts/check_phase6j_d3_mri_mpr_overlay.mjs
git diff --check

echo 'PHASE6J_D4_CHECKS_OK=YES'
echo 'MRI_INFERENCE=NOT_RUN'
echo 'PRODUCTION_MRI_IMPORT=NOT_RUN'
echo 'MRI_INTENSITY_THRESHOLD_SURFACE=NOT_USED'
echo 'PHASE6J_D4_MRI_3D_PRESENTATION_PROFILE=PASS'
echo 'MRI_REFERENCE_SURFACE=UNCHANGED'
echo 'MRI_PRESENTATION_RECONSTRUCTION=GAUSSIAN_LABEL_MAP_ISOSURFACE'
echo 'MRI_PRESENTATION_RECONSTRUCTION_APPLIED=PASS'
echo 'MRI_PRESENTATION_MAX_DISPLACEMENT_MM=3.0'
echo 'CLINICAL_VALIDATION=NOT_CLAIMED'
