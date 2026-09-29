#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
"$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c1_mri_runtime_qualification.py' -v
"$PYTHON" -m py_compile backend/voxelatlas/mri_runtime_qualification.py tests/test_phase6j_c1_mri_runtime_qualification.py
bash scripts/run_phase6j_b2b_checks.sh
echo PHASE6J_C1_CHECKS_OK=YES
