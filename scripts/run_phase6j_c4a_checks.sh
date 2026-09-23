#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PYTHON:=.venv/bin/python}"
test -x "$PYTHON"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/backend" "$PYTHON" -m unittest discover -s tests -p 'test_phase6j_c4a_mri_provider_qualification.py' -v
"$PYTHON" -m py_compile backend/voxelatlas/app.py backend/voxelatlas/config.py backend/voxelatlas/mri_provider_qualification.py tests/test_phase6j_c4a_mri_provider_qualification.py
PYTHON="$PYTHON" bash scripts/run_phase6j_c3b_checks.sh
git diff --check
echo PHASE6J_C4A_CHECKS_OK=YES
