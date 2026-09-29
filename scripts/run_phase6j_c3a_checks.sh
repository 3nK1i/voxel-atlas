#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
"$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c3a_mri_bridge.py' -v
"$PYTHON" -m py_compile scripts/phase6j_c3a_mri_nifti_worker.py tests/test_phase6j_c3a_mri_bridge.py
bash scripts/run_phase6j_c2_checks.sh
git diff --check
echo PHASE6J_C3A_CHECKS_OK=YES
