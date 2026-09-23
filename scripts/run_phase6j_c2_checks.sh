#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
"$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c2_mri_weights_qualification.py' -v
"$PYTHON" -m py_compile backend/voxelatlas/mri_weights_qualification.py scripts/prepare_phase6j_c2_mri_weights.py tests/test_phase6j_c2_mri_weights_qualification.py
bash scripts/run_phase6j_c1_checks.sh
git diff --check
echo PHASE6J_C2_CHECKS_OK=YES
