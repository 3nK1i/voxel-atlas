#!/usr/bin/env bash
# Phase 6G3: synthetic-only source-bound report contract; no real-study access.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="${VOXELATLAS_SURFACE_PYTHON:-python3}"
if ! "$PYTHON" -c 'import numpy, scipy, skimage' >/dev/null 2>&1; then
  echo 'PHASE6G3_RUNTIME=FAIL: supply the existing qualified surface Python' >&2
  exit 1
fi
for entry in \
    'PHASE6G3_BOUND_INTEGRATION:test_phase6g3_bound_fidelity_integration.py' \
    'PHASE6G2_REGRESSION:test_phase6g2_three_plane_mpr_agreement.py' \
    'PHASE6G1_REGRESSION:test_phase6g1_bidirectional_surface_distances.py' \
    'PHASE6G0_REGRESSION:test_phase6g0_interface_residual.py'; do
    label="${entry%%:*}"
    pattern="${entry#*:}"
    echo "===== $label ====="
    "$PYTHON" -m unittest discover -s tests -p "$pattern" -q
    echo "${label}_RC=0"
done
printf '===== PHASE6G3_SYNTAX =====\n'
"$PYTHON" -m py_compile \
    backend/voxelatlas/segmentation_surface_fidelity_report.py \
    tests/test_phase6g3_bound_fidelity_integration.py
bash -n scripts/run_phase6g3_fidelity_checks.sh
printf 'PHASE6G3_SYNTAX_RC=0\n'
printf 'PHASE6G3_SYNTHETIC_CHECKS_OK=YES\n'
