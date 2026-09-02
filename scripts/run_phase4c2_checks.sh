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
  bash -n scripts/run_phase4c2_checks.sh
}

run_patient_data() {
  ! git ls-files --cached --others --exclude-standard | grep -E \
    '(^|/)data/studies/|\.dcm$|volume\.npy$|volume\.json$|derived/(anatomy|volume_rendering)/.+\.(npz|json|rg8)$'
}

run_no_surface_first() {
  ! grep -EIn \
    'marching[_ -]?cubes|marchingCubes|isosurface|skull reconstruction|brain reconstruction' \
    web/js/patient-volume-ray-marcher.js
}

run_rg8_sampling_safety() {
  grep -q 'texture.minFilter = THREE.NearestFilter' web/js/patient-volume-ray-marcher.js \
    && grep -q 'decodeMedicalIntensity' web/js/patient-volume-ray-marcher.js \
    && ! grep -q 'THREE.LinearFilter' web/js/patient-volume-ray-marcher.js
}

run_dash() {
  ! grep -RIn \
    --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' \
    '—' web backend \
    docs/phase_history/PHASE4C2_TRUE_PATIENT_VOLUME_RAY_MARCHING.md
}

echo "===== PHASE 4C2 COMPACT VALIDATION ====="
run_quiet "Phase 4C2 unit/UI contract" python -m unittest \
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
run_quiet "Python compile" python -m py_compile \
  tests/test_phase4c2_true_volume_ray_marching.py
run_quiet "Application JavaScript syntax" node --check web/js/app.js
run_quiet "Capability JavaScript syntax" node --check web/js/volume-rendering-capabilities.js
run_quiet "Texture manager JavaScript syntax" node --check web/js/volume-texture-manager.js
run_quiet "Ray marcher JavaScript syntax" node --check web/js/patient-volume-ray-marcher.js
run_quiet "C2 probe JavaScript syntax" node --check scripts/check_phase4c2_volume_ray_marcher.mjs
run_quiet "Browser capability regression" node scripts/check_phase4b_browser_capabilities.mjs
run_quiet "Shell syntax" run_shell
run_quiet "Patient-data Git safety" run_patient_data
run_quiet "No surface-first implementation" run_no_surface_first
run_quiet "RG8 sampling safety" run_rg8_sampling_safety
run_quiet "Em-dash scan" run_dash
run_quiet "Diff whitespace" git diff --check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE4C2_TRUE_VOLUME_RAY_MARCHING_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE4C2_TRUE_VOLUME_RAY_MARCHING_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
