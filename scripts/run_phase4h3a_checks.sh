#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FAIL=0

run_quiet() {
  local label="$1"; shift
  local safe="${label// /_}"; safe="${safe//\//_}"
  local log="$TMP/${safe}.log"
  if "$@" >"$log" 2>&1; then
    printf '%-46s PASS\n' "$label"
  else
    printf '%-46s FAIL\n' "$label"
    cat "$log"
    FAIL=1
  fi
}

run_shell() {
  bash -n scripts/run_phase4h1_checks.sh \
    scripts/run_phase4h2_checks.sh \
    scripts/run_phase4h3a_checks.sh
}

run_patient_data() {
  ! git ls-files --cached --others --exclude-standard | grep -E \
    '(^|/)data/(studies|sample_studies)/|\.dcm$|volume\.npy$|volume\.json$|derived/(anatomy|volume_rendering)/.+\.(npz|json|rg8)$|(^|/)preview\.png$'
}

run_projection_contract() {
  grep -Fq 'id="renderingModeSelect"' web/index.html \
    && grep -Fq '<option value="mip">MIP</option>' web/index.html \
    && grep -Fq '<option value="minip">MinIP</option>' web/index.html \
    && grep -Fq '<option value="average">Average Intensity</option>' web/index.html \
    && grep -Fq 'uRenderingMode' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'aggregateMedicalProjection' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'windowMedicalIntensity(projectedIntensity)' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'setMedicalRenderingMode' web/js/app.js \
    && grep -Fq 'setDvrOnlyControlsEnabled' web/js/app.js
}

run_canonical_texture_safety() {
  grep -Fq 'uVolume: { value: texture }' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'uLocalToPatientLps' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'clipPatientRayInterval' web/js/patient-volume-ray-marcher.js \
    && ! grep -Fq 'textureResource.texture.image.data' web/js/app.js \
    && ! grep -Eqi 'marchingCubes|isocontour' web/js/patient-volume-ray-marcher.js
}

run_dash() {
  ! grep -RIn \
    --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' \
    '—' web backend \
    docs/phase_history/PHASE4H3A_MEDICAL_PROJECTION_RENDERING_MODES.md
}

echo "===== PHASE 4H3A COMPACT VALIDATION ====="
run_quiet "Phase 4H3A unit/UI contract" python -m unittest \
  tests.test_phase4h3a_medical_projection_modes
run_quiet "Phase 4H2-R1A and full regression" bash scripts/run_phase4h2_checks.sh
run_quiet "Phase 4H3A projection probe" node scripts/check_phase4h3a_projection_modes.mjs
run_quiet "Python compile" python -m py_compile \
  tests/test_phase4h3a_medical_projection_modes.py
run_quiet "Application JavaScript syntax" node --check web/js/app.js
run_quiet "Ray marcher JavaScript syntax" node --check web/js/patient-volume-ray-marcher.js
run_quiet "H3A probe JavaScript syntax" node --check scripts/check_phase4h3a_projection_modes.mjs
run_quiet "Shell syntax" run_shell
run_quiet "Patient-data Git safety" run_patient_data
run_quiet "Medical projection contract" run_projection_contract
run_quiet "Canonical texture safety" run_canonical_texture_safety
run_quiet "Em-dash scan" run_dash
run_quiet "Diff whitespace" git diff --check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE4H3A_MEDICAL_PROJECTION_RENDERING_MODES_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE4H3A_MEDICAL_PROJECTION_RENDERING_MODES_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
