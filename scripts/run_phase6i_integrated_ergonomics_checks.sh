#!/usr/bin/env bash
# Validate integrated layout polish and durable presentation contracts.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${VOXELATLAS_APP_PYTHON:-.venv/bin/python}"
test -x "$PY"
command -v node >/dev/null 2>&1
printf '%s\n' '===== 6I INTEGRATED ERGONOMICS ====='
"$PY" -m unittest discover -s tests -p 'test_phase6i_integrated_ergonomics.py' -v
node --check web/js/parameter-help.js
node --check web/js/app.js
"$PY" -m py_compile tests/test_phase6i_integrated_ergonomics.py
bash -n scripts/run_phase6i_integrated_ergonomics_checks.sh
printf '%s\n' '===== PRIOR 6I-D/C/B/A AND SCIENTIFIC REGRESSIONS ====='
bash scripts/run_phase6i_d_checks.sh
git diff --check
git diff --cached --check
printf '%s\n' 'PHASE6I_INTEGRATED_ERGONOMICS_CHECKS_OK=YES'
