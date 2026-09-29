#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD/backend:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c5b_mri_provider_report_json.py' -v
"$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c3b_mri_worker_execution.py' -v
"$PYTHON" -m py_compile backend/voxelatlas/mri_worker_execution.py tests/test_phase6j_c5b_mri_provider_report_json.py tests/test_phase6j_c3b_mri_worker_execution.py
PYTHON="$PYTHON" bash scripts/run_phase6j_c4c_checks.sh
git diff --check
printf 'PHASE6J_C5B_REPORT_JSON_CHECKS_OK=YES\n'
