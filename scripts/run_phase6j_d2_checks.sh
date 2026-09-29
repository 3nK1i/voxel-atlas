#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="${PYTHON:-.venv/bin/python}"
test -x "$PYTHON"
echo '===== PHASE 6J-D2 SYNTHETIC MRI IMPORT CONTRACT ====='
PYTHONPATH="$PWD/backend:$PWD/tests" "$PYTHON" -m unittest discover \
  -s tests -p 'test_phase6j_d2_mri_label_map_import.py' -v
echo '===== PHASE 6J-D2 EXISTING PROVIDER-NEUTRAL IMPORT REGRESSION ====='
PYTHONPATH="$PWD/backend:$PWD/tests" "$PYTHON" -m unittest discover \
  -s tests -p 'test_phase5c_canonical_label_map_import.py' -v
echo '===== PHASE 6J-D2 PRIOR CT/MRI REGRESSION ====='
PYTHON="$PYTHON" bash scripts/run_phase6j_c5d_checks.sh
"$PYTHON" -m py_compile \
  backend/voxelatlas/mri_label_map_import.py \
  backend/voxelatlas/segmentation_label_maps.py \
  scripts/phase6j_d2_import_mri_label_map.py \
  tests/test_phase6j_d2_mri_label_map_import.py
git diff --check
echo PHASE6J_D2_SYNTHETIC_AND_PRIOR_CHECKS_OK=YES
echo MRI_INFERENCE=NOT_RUN
