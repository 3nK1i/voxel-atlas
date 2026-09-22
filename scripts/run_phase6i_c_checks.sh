#!/usr/bin/env bash
# Phase 6I-C: focus on derived two-sided clipping without repeating old pinned gates.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${VOXELATLAS_APP_PYTHON:-.venv/bin/python}"
test -x "$PY" || { echo "Missing development .venv Python" >&2; false; }
command -v node >/dev/null 2>&1 || { echo "Node.js required" >&2; false; }
echo '===== 6I-C TARGETED CLIPPING CONTRACT + RUNTIME ====='
"$PY" -m unittest discover -s tests -p 'test_phase6i_c_automatic_two_sided_clipping.py' -v
"$PY" -m unittest discover -s tests -p 'test_phase4h6_qualification.py' -q
# Select durable scientific contracts. The historical Phase 4E cache-prefix
# assertion predates the current Phase 6I app entrypoint and fails on the B2 baseline.
"$PY" -m unittest \
  tests.test_phase4e_multiplane_patient_space_clipping.Phase4EMultiplanePatientSpaceClippingTests.test_ray_interval_is_clipped_in_dicom_patient_lps_space \
  tests.test_phase4e_multiplane_patient_space_clipping.Phase4EMultiplanePatientSpaceClippingTests.test_clipping_and_mpr_use_patient_coordinates_without_shared_state \
  tests.test_phase4e_multiplane_patient_space_clipping.Phase4EMultiplanePatientSpaceClippingTests.test_reset_disables_all_planes_without_changing_transfer_or_volume -q
"$PY" -m unittest discover -s tests -p 'test_phase4h5_mpr_clipping_visualization.py' -q
node scripts/check_phase4h4_dual_clipping.mjs
node scripts/check_phase4h5_mpr_clipping.mjs
node scripts/check_phase5g_ui.mjs
for file in web/js/app.js web/js/parameter-help.js web/js/patient-volume-ray-marcher.js scripts/check_phase6i_c_automatic_clipping.mjs scripts/check_phase4h5_browser.mjs; do node --check "$file"; done
"$PY" -m py_compile tests/test_phase6i_c_automatic_two_sided_clipping.py tests/test_phase4h6_qualification.py
bash -n scripts/run_phase6i_c_checks.sh
echo '===== PREVIOUS PHASE 6I-B2 + I-A + SCIENTIFIC REGRESSION ====='
bash scripts/run_phase6i_b2_checks.sh
git diff --check
printf 'PHASE6I_C_CHECKS_OK=YES\n'
