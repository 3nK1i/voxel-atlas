#!/usr/bin/env bash
# Phase 6I-D: presentation-only normal UI and readable Direct CT visibility.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${VOXELATLAS_APP_PYTHON:-.venv/bin/python}"
test -x "$PY"
command -v node >/dev/null 2>&1
printf '%s\n' '===== 6I-D TARGETED CONTRACT ====='
"$PY" -m unittest discover -s tests -p 'test_phase6i_d_presentation_visibility.py' -v
node scripts/check_phase6i_d_presentation.mjs
for file in web/js/app.js web/js/parameter-help.js web/js/reconstruction-presentation-profile.js web/js/reconstruction-surface-presentation.js scripts/check_phase6i_d_presentation.mjs; do node --check "$file"; done
"$PY" -m py_compile tests/test_phase6i_d_presentation_visibility.py
bash -n scripts/run_phase6i_d_checks.sh
printf '%s\n' '===== 6I-C + PRIOR SCIENTIFIC REGRESSIONS ====='
bash scripts/run_phase6i_c_checks.sh
git diff --check
git diff --cached --check
printf '%s\n' 'PHASE6I_D_CHECKS_OK=YES'
