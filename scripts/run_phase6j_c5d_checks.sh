#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-.venv/bin/python}"
MRI_PYTHON="$HOME/anaconda3/envs/voxelatlas-totalseg-2.18/bin/python"
test -x "$PYTHON"
test -x "$MRI_PYTHON"

echo '===== PHASE 6J-C5D ONE-OFF RUNNER: SYNTHETIC ONLY ====='
PYTHONPATH="$PWD/backend:$PWD/tests" "$PYTHON" -m unittest discover \
  -s tests -p 'test_phase6j_c5d_single_trial.py' -v

echo '===== PHASE 6J-C5D PARSER AND SUPERVISOR REGRESSIONS ====='
PYTHONPATH="$PWD/backend:$PWD/tests" "$PYTHON" -m unittest discover \
  -s tests -p 'test_phase6j_c5b_mri_provider_report_json.py' -v
PYTHONPATH="$PWD/backend:$PWD/tests" "$PYTHON" -m unittest discover \
  -s tests -p 'test_phase6j_c3b_mri_worker_execution.py' -v

echo '===== PHASE 6J-C5D MRI INTERPRETER GEOMETRY ====='
PYTHONPATH="$PWD/backend:$PWD/tests" "$MRI_PYTHON" -m unittest discover \
  -s tests -p 'test_phase6j_c3a_mri_bridge.py' -v

echo '===== PHASE 6J-C5D FULL PRIOR CT/MRI REGRESSION ====='
PYTHON="$PYTHON" bash scripts/run_phase6j_c5b_checks.sh

echo '===== PHASE 6J-C5D STATIC VALIDATION ====='
"$PYTHON" -m py_compile scripts/phase6j_c5d_single_trial.py tests/test_phase6j_c5d_single_trial.py
git diff --check
echo 'PHASE6J_C5D_SYNTHETIC_AND_PRIOR_CHECKS_OK=YES'
echo 'MRI_INFERENCE=NOT_RUN'
