#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
"$PYTHON" -m unittest discover -s tests -p 'test_phase6j_b2a_mri_source_series.py' -v
"$PYTHON" -m compileall -q backend/voxelatlas/mri_source_qualification.py backend/voxelatlas/segmentation_workflow.py
bash scripts/run_phase6j_b1_checks.sh
echo PHASE6J_B2A_CHECKS_OK=YES
