#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
node --check web/js/mri-study-prevolume.js
node --check web/js/app.js
node --check web/js/segmentation-workflow-panel.js
node scripts/check_phase6j_b2b_mri_study_workflows.mjs
PYTHON="${PYTHON:-.venv/bin/python}" bash scripts/run_phase6j_b2a_checks.sh
echo PHASE6J_B2B_CHECKS_OK=YES
