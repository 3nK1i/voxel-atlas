#!/usr/bin/env bash
# Narrow synthetic-only Phase 6G0 foundation check. No studies, no API, no deployment.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '===== PHASE6G0_SYNTHETIC_INTERFACE =====\n'
python3 -m unittest discover -s tests -p 'test_phase6g0_interface_residual.py' -q
printf 'PHASE6G0_SYNTHETIC_INTERFACE_RC=0\n'
printf '===== PHASE6G0_COMPILE =====\n'
python3 -m py_compile backend/voxelatlas/segmentation_surface_fidelity.py tests/test_phase6g0_interface_residual.py
printf 'PHASE6G0_COMPILE_RC=0\n'
printf 'PHASE6G0_FOUNDATION_CHECKS_OK=YES\n'
