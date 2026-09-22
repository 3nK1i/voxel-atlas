#!/usr/bin/env bash
# Phase 6I-B1: focused scheduling, historical visualization contracts, 6I-A gate.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${VOXELATLAS_APP_PYTHON:-.venv/bin/python}"
test -x "$PY" || { echo "Development .venv Python is unavailable" >&2; false; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required for B1 async tests" >&2; false; }
echo '===== 6I-B1 TARGETED ====='
"$PY" -m unittest discover -s tests -p 'test_phase6i_b1_automatic_direct_ct_mode.py' -v
node --check web/js/app.js
node --check web/js/automatic-surface-mode.js
node --check web/js/volume-surface-viewer.js
node --check web/js/parameter-help.js
for pattern in \
  test_phase6d2a_visualization_mode_controller.py \
  test_phase6d2b_volume_surface_transitions.py \
  test_phase6d2c_combined_visualization.py \
  test_phase6d2d_reset_study_error_closure.py \
  test_phase6d0_explicit_surface_selection_correction.py \
  test_post6f_pre6g_stabilization_a.py; do
  "$PY" -m unittest discover -s tests -p "$pattern" -q
done
echo '===== 6I-A + SCIENTIFIC REGRESSION ====='
bash scripts/run_phase6i_a_checks.sh
"$PY" -m py_compile tests/test_phase6i_b1_automatic_direct_ct_mode.py
git diff --check
printf 'PHASE6I_B1_CHECKS_OK=YES\n'
