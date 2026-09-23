#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/backend:$PWD/tests" "$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c4b_mri_study_bound_jobs.py' -v
"$PYTHON" -m py_compile backend/voxelatlas/mri_job_binding.py tests/test_phase6j_c4b_mri_study_bound_jobs.py
PYTHON="$PYTHON" bash scripts/run_phase6j_c4a_checks.sh
git diff --check
echo PHASE6J_C4B_CHECKS_OK=YES
