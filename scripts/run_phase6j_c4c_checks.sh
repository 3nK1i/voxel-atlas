#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD/backend:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c4c_mri_workflow_presentation.py' -v
"$PYTHON" -m unittest discover -s tests -p 'test_phase6d0_on_demand_segmentation_workflow.py' -v
"$PYTHON" -m py_compile \
  backend/voxelatlas/app.py \
  backend/voxelatlas/mri_workflow_presentation.py \
  backend/voxelatlas/segmentation_workflow.py \
  tests/test_phase6j_c4c_mri_workflow_presentation.py
node --check web/js/mri-workflow-display.js
node --check web/js/segmentation-workflow-panel.js
node --check web/js/app.js
node --check scripts/check_phase6j_c4c_mri_workflow.mjs
node scripts/check_phase6j_c4c_mri_workflow.mjs
PYTHON="$PYTHON" bash scripts/run_phase6j_c4b_checks.sh
git diff --check
printf 'PHASE6J_C4C_CHECKS_OK=YES\n'
