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
    scripts/run_phase4h2_checks.sh
}

run_patient_data() {
  ! git ls-files --cached --others --exclude-standard | grep -E \
    '(^|/)data/(studies|sample_studies)/|\.dcm$|volume\.npy$|volume\.json$|derived/(anatomy|volume_rendering)/.+\.(npz|json|rg8)$|(^|/)preview\.png$'
}

run_h2_display_contract() {
  grep -Fq 'id="transferOpacitySoftness"' web/index.html \
    && grep -Fq 'id="transferEdgeDefinition"' web/index.html \
    && grep -Fq 'id="transferShadingStrength"' web/index.html \
    && grep -Fq 'uTextureTexelSize' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'opacityBoundaryWeight' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'sampleMedicalGradient' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'applyMedicalDepthShading' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'patientSpaceMedicalGradient' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'constrainMedicalIntensityInterval' web/js/app.js \
    && grep -Fq 'Intensity minimum' web/index.html \
    && grep -Fq 'Intensity maximum' web/index.html \
    && grep -Fq 'transferRangeLow.max = String(sourceHigh)' web/js/app.js \
    && grep -Fq 'transferRangeHigh.min = String(sourceLow)' web/js/app.js \
    && grep -Fq 'const minimumInterval = Math.max(step, 0.000001)' web/js/app.js \
    && grep -Fq 'transferWindowWidth.min = String(minimumInterval)' web/js/app.js \
    && grep -Fq 'markTransferCustomized' web/js/app.js \
    && ! grep -Fq 'MR · HU' web/index.html web/js/*.js
}

run_canonical_texture_safety() {
  grep -Fq 'lowByte + highByte * 256.0' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'uDecodeOffset + uDecodeScale' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'uVolume: { value: texture }' web/js/patient-volume-ray-marcher.js \
    && ! grep -Fq 'textureResource.texture.image.data' web/js/app.js \
    && ! grep -Eqi 'marchingCubes|isocontour' web/js/patient-volume-ray-marcher.js
}

run_dash() {
  ! grep -RIn \
    --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' \
    '—' web backend \
    docs/phase_history/PHASE4H2_VOLUME_DEFINITION_AND_SHADING.md
}

echo "===== PHASE 4H2-R1A COMPACT VALIDATION ====="
run_quiet "Phase 4H2-R1A unit/UI contract" python -m unittest \
  tests.test_phase4h2_volume_definition_and_shading
run_quiet "Phase 4H1 and full regression" bash scripts/run_phase4h1_checks.sh
run_quiet "Phase 4H2-R1A volume definition" node scripts/check_phase4h2_volume_definition.mjs
run_quiet "Python compile" python -m py_compile \
  tests/test_phase4h2_volume_definition_and_shading.py
run_quiet "Application JavaScript syntax" node --check web/js/app.js
run_quiet "Ray marcher JavaScript syntax" node --check web/js/patient-volume-ray-marcher.js
run_quiet "H2 probe JavaScript syntax" node --check scripts/check_phase4h2_volume_definition.mjs
run_quiet "Shell syntax" run_shell
run_quiet "Patient-data Git safety" run_patient_data
run_quiet "Professional definition contract" run_h2_display_contract
run_quiet "Canonical texture safety" run_canonical_texture_safety
run_quiet "Em-dash scan" run_dash
run_quiet "Diff whitespace" git diff --check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE4H2_R1A_VOLUME_DEFINITION_AND_SHADING_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE4H2_R1A_VOLUME_DEFINITION_AND_SHADING_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
