#!/usr/bin/env bash
# Phase 6G2: synthetic-only, read-only geometric MPR agreement checks.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="${VOXELATLAS_SURFACE_PYTHON:-python3}"
test -x "$(command -v "$PYTHON")"
for entry in \
    'PHASE6G2_THREE_PLANE:test_phase6g2_three_plane_mpr_agreement.py' \
    'PHASE6G1_REGRESSION:test_phase6g1_bidirectional_surface_distances.py' \
    'PHASE6G0_REGRESSION:test_phase6g0_interface_residual.py'; do
    label="${entry%%:*}"
    pattern="${entry#*:}"
    echo "===== $label ====="
    "$PYTHON" -m unittest discover -s tests -p "$pattern" -q
    echo "${label}_RC=0"
done
echo '===== PHASE6G2_SYNTAX ====='
"$PYTHON" -m py_compile \
    backend/voxelatlas/segmentation_surface_mpr_agreement.py \
    tests/test_phase6g2_three_plane_mpr_agreement.py
bash -n scripts/run_phase6g2_mpr_checks.sh
echo 'PHASE6G2_SYNTAX_RC=0'
echo 'PHASE6G2_SYNTHETIC_CHECKS_OK=YES'
