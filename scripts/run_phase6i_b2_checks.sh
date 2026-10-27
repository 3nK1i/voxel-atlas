#!/usr/bin/env bash
# Verify the existing activated segmentation-surface mode and UI regression.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${VOXELATLAS_APP_PYTHON:-.venv/bin/python}"
test -x "$PY" || { echo 'Development app Python is unavailable' >&2; false; }
command -v node >/dev/null 2>&1 || { echo 'Node.js is required for async mode tests' >&2; false; }
echo '===== 6I-B2 TARGETED SOURCE + ASYNC MODE ====='
"$PY" -m unittest discover -s tests -p 'test_phase6i_b2_existing_segmentation_mode.py' -v
node --check web/js/app.js
node --check web/js/existing-segmentation-mode.js
node --check web/js/automatic-surface-mode.js
node --check web/js/segmentation-surface-viewer.js
node --check web/js/segmentation-workflow-panel.js
node --check web/js/parameter-help.js
bash -n scripts/run_phase6i_b2_checks.sh
echo '===== 6I-B1 + 6I-A + SCIENTIFIC REGRESSION ====='
bash scripts/run_phase6i_b1_checks.sh
echo '===== B2 ACCURATE/REFINED FALLBACK SOURCE CONTRACT ====='
"$PY" -m unittest discover -s tests -p 'test_phase6b_refined_surface_accurate_fallback.py' -q
"$PY" -m py_compile tests/test_phase6i_b2_existing_segmentation_mode.py
git diff --check
printf 'PHASE6I_B2_CHECKS_OK=YES\n'
