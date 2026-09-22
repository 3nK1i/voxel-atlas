#!/usr/bin/env bash
# Additive Phase 6G1 synthetic-only distance checks; no patient records or service startup.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="${VOXELATLAS_SURFACE_PYTHON:-python3}"
if ! "$PYTHON" -c 'import numpy, scipy, skimage' >/dev/null 2>&1; then
  echo 'PHASE6G1_RUNTIME=FAIL: set VOXELATLAS_SURFACE_PYTHON to the existing qualified surface runtime' >&2
  exit 1
fi
printf '===== PHASE6G1_SYNTHETIC_BIDIRECTIONAL =====\n'
"$PYTHON" -m unittest discover -s tests -p 'test_phase6g1_bidirectional_surface_distances.py' -q
printf 'PHASE6G1_SYNTHETIC_RC=0\n'
printf '===== PHASE6G0_REGRESSION =====\n'
"$PYTHON" -m unittest discover -s tests -p 'test_phase6g0_interface_residual.py' -q
printf 'PHASE6G0_REGRESSION_RC=0\n'
"$PYTHON" -m py_compile backend/voxelatlas/segmentation_surface_distances.py tests/test_phase6g1_bidirectional_surface_distances.py
bash -n scripts/run_phase6g1_distance_checks.sh
printf 'PHASE6G1_SYNTAX_RC=0\n'
printf 'PHASE6G1_SYNTHETIC_CHECKS_OK=YES\n'
