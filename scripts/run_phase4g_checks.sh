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
  bash -n scripts/run_phase4g_checks.sh
}

run_patient_data() {
  ! git ls-files --cached --others --exclude-standard | grep -E \
    '(^|/)data/(studies|sample_studies)/|\.dcm$|volume\.npy$|volume\.json$|derived/(anatomy|volume_rendering)/.+\.(npz|json|rg8)$|(^|/)preview\.png$'
}

run_volume_only_runtime() {
  local combined
  combined="$(cat web/index.html web/js/app.js)"
  [[ "$(grep -o 'data-layer=' web/index.html | wc -l)" -eq 1 ]] \
    && ! grep -Eqi \
      'GLTFLoader|SKULL_URL|loadSkull|prepareSkull|MeshPhysicalMaterial|data-layer="(skull|brain|combined)"|data-future-layer=|/assets/models/' \
      <<<"$combined"
}

run_sample_catalog_runtime() {
  grep -Fq 'SampleStudyCatalogClient' web/js/app.js \
    && grep -Fq 'compute_sample_payload_digest' backend/voxelatlas/sample_catalog.py \
    && grep -Fq 'DicomIngestionService.ingest' docs/phase_history/PHASE4G_CURATED_SAMPLE_STUDY_CATALOG.md \
    && ! grep -Eqi 'sample_studies/.+\.(dcm|npy|npz|rg8|png)' web/index.html web/js/*.js
}

run_patient_clipping() {
  [[ "$(grep -o 'data-clip-enabled=' web/index.html | wc -l)" -eq 3 ]] \
    && grep -Fq 'clipPatientRayInterval' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'uLocalToPatientLps' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'volumeRayMarcher.setClippingPlanes' web/js/app.js
}

run_adaptive_quality() {
  grep -Fq 'createAdaptiveRenderingProfile' web/js/volume-rendering-quality.js \
    && grep -Fq 'recordFrameDuration' web/js/volume-rendering-quality.js \
    && grep -Fq 'controls.addEventListener("start"' web/js/app.js \
    && grep -Fq 'viewerRenderRequested' web/js/app.js \
    && grep -Fq 'if (shouldRender)' web/js/app.js \
    && grep -Fq 'setSamplingRate' web/js/patient-volume-ray-marcher.js \
    && [[ "$(grep -Fc 'renderer.render(scene, camera);' web/js/app.js)" -eq 1 ]]
}

run_rg8_safety() {
  grep -Fq 'lowByte + highByte * 256.0' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'uDecodeOffset + uDecodeScale' web/js/patient-volume-ray-marcher.js
}

run_dash() {
  ! grep -RIn \
    --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' \
    '—' web backend \
    docs/phase_history/PHASE4G_CURATED_SAMPLE_STUDY_CATALOG.md
}

echo "===== PHASE 4G COMPACT VALIDATION ====="
run_quiet "Phase 4G unit/UI contract" python -m unittest \
  tests.test_phase4g_sample_study_catalog
run_quiet "Phase 4F regression" python -m unittest \
  tests.test_phase4f_adaptive_rendering_quality
run_quiet "Phase 4E regression" python -m unittest \
  tests.test_phase4e_multiplane_patient_space_clipping
run_quiet "Phase 4D2 regression" python -m unittest \
  tests.test_phase4d2_medical_transfer_functions
run_quiet "Phase 4D1 regression" python -m unittest \
  tests.test_phase4d1_volume_only_workspace
run_quiet "Phase 4C2 regression" python -m unittest \
  tests.test_phase4c2_true_volume_ray_marching
run_quiet "Phase 4C1 regression" python -m unittest \
  tests.test_phase4c1_volume_texture_transport
run_quiet "Phase 4B regression" python -m unittest \
  tests.test_phase4b_direct_volume_rendering_foundation
run_quiet "Phase 3 volume/MPR regression" python -m unittest \
  tests.test_phase3c_canonical_volume_construction \
  tests.test_phase3d_real_mpr_integration \
  tests.test_phase3d_r21_crosshair_cta_polish
run_quiet "Phase 4A regression" python -m unittest \
  tests.test_phase4a_anatomical_reconstruction_foundation
run_quiet "Full unit regression" python -m unittest discover -s tests -p 'test_*.py'
run_quiet "Phase 4B artifact probe" python scripts/check_phase4b_direct_volume_rendering.py
run_quiet "Phase 4C1 texture lifecycle" node scripts/check_phase4c1_volume_texture_manager.mjs
run_quiet "Phase 4C2 ray marcher" node scripts/check_phase4c2_volume_ray_marcher.mjs
run_quiet "Phase 4D1 volume-only probe" node scripts/check_phase4d1_volume_only_workspace.mjs
run_quiet "Phase 4D2 transfer functions" node scripts/check_phase4d2_transfer_functions.mjs
run_quiet "Phase 4E patient clipping" node scripts/check_phase4e_patient_clipping.mjs
run_quiet "Phase 4F adaptive quality" node scripts/check_phase4f_adaptive_quality.mjs
run_quiet "Phase 4G sample catalog" node scripts/check_phase4g_sample_catalog.mjs
run_quiet "Python compile" python -m py_compile \
  backend/voxelatlas/sample_catalog.py \
  scripts/install_phase4g_sample_study.py \
  tests/test_phase4g_sample_study_catalog.py
run_quiet "Application JavaScript syntax" node --check web/js/app.js
run_quiet "Sample catalog JavaScript syntax" node --check web/js/sample-study-catalog.js
run_quiet "G probe JavaScript syntax" node --check scripts/check_phase4g_sample_catalog.mjs
run_quiet "Browser capability regression" node scripts/check_phase4b_browser_capabilities.mjs
run_quiet "Shell syntax" run_shell
run_quiet "Patient-data Git safety" run_patient_data
run_quiet "Volume-only runtime contract" run_volume_only_runtime
run_quiet "Patient-space clipping contract" run_patient_clipping
run_quiet "Adaptive rendering contract" run_adaptive_quality
run_quiet "Sample catalog runtime contract" run_sample_catalog_runtime
run_quiet "RG8 sampling safety" run_rg8_safety
run_quiet "Em-dash scan" run_dash
run_quiet "Diff whitespace" git diff --check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE4G_CURATED_SAMPLE_STUDY_CATALOG_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE4G_CURATED_SAMPLE_STUDY_CATALOG_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
