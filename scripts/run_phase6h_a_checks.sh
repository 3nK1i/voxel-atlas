#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="${VOXELATLAS_SURFACE_PYTHON:-python3}"
"$PYTHON" -c 'import numpy, scipy, skimage' >/dev/null
printf '===== PHASE6H_A_LOCAL_HARNESS =====\n'
"$PYTHON" -m unittest discover -s tests -p test_phase6h_a_real_study_harness.py -q
printf 'PHASE6H_A_LOCAL_HARNESS_RC=0\n'
VOXELATLAS_SURFACE_PYTHON="$PYTHON" bash scripts/run_phase6g3_fidelity_checks.sh
"$PYTHON" -m py_compile backend/voxelatlas/segmentation_surface_real_study_qualification.py scripts/qualify_phase6h_a_real_study.py tests/test_phase6h_a_real_study_harness.py
bash -n scripts/run_phase6h_a_checks.sh
printf 'PHASE6H_A_SYNTHETIC_CHECKS_OK=YES\n'
