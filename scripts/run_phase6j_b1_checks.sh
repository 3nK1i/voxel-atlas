#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  echo "REQUIRED_APP_PYTHON_UNAVAILABLE=$PYTHON" >&2
  exit 1
fi
"$PYTHON" -m unittest discover -s tests -p 'test_phase6j_b1_mri_task_selection.py' -v
node --check web/js/segmentation-workflow-panel.js
node --check web/js/app.js
node scripts/check_phase6j_b1_mri_workflow.mjs
# Retain the prior CT scientific/anatomical presentation acceptance runner.
if [[ ! -f scripts/run_ct_b3a_checks.sh ]]; then
  echo 'REQUIRED_CT_B3A_REGRESSION_RUNNER_MISSING' >&2
  exit 1
fi
bash scripts/run_ct_b3a_checks.sh
echo PHASE6J_B1_CHECKS_OK=YES
