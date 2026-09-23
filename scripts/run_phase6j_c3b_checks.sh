#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
PYTHONPATH="$PWD/backend" "$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c3b_mri_worker_execution.py' -v
"$PYTHON" -m py_compile backend/voxelatlas/mri_worker_execution.py tests/test_phase6j_c3b_mri_worker_execution.py
PYTHON="$PYTHON" bash scripts/run_phase6j_c3a_checks.sh
git diff --check
echo PHASE6J_C3B_CHECKS_OK=YES
