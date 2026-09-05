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
    scripts/run_phase4h3a_checks.sh \
    scripts/run_phase4h3b_checks.sh \
    scripts/run_phase4h4_checks.sh
}

run_patient_data() {
  ! git ls-files --cached --others --exclude-standard | grep -E \
    '(^|/)data/(studies|sample_studies)/|\.dcm$|volume\.npy$|volume\.json$|derived/(anatomy|volume_rendering)/.+\.(npz|json|rg8)$|(^|/)preview\.png$'
}

run_dual_clipping_contract() {
  grep -Fq 'data-clip-start="axial"' web/index.html \
    && grep -Fq 'data-clip-end="axial"' web/index.html \
    && grep -Fq 'data-clip-start="coronal"' web/index.html \
    && grep -Fq 'data-clip-end="coronal"' web/index.html \
    && grep -Fq 'data-clip-start="sagittal"' web/index.html \
    && grep -Fq 'data-clip-end="sagittal"' web/index.html \
    && ! grep -Fq 'data-clip-side' web/index.html \
    && grep -Fq 'uClipBoundsMinimum' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'uClipBoundsMaximum' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'clipAgainstPatientRange' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'clippingBoundaryLpsMm' web/js/app.js \
    && grep -Fq 'reversed: true' web/js/app.js
}

run_canonical_texture_safety() {
  grep -Fq 'uVolume: { value: texture }' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'uLocalToPatientLps' web/js/patient-volume-ray-marcher.js \
    && grep -Fq 'clipPatientRayInterval' web/js/patient-volume-ray-marcher.js \
    && ! grep -Fq 'textureResource.texture.image.data' web/js/app.js \
    && ! grep -Eqi 'marchingCubes|isocontour' web/js/patient-volume-ray-marcher.js
}

run_crosshair_independence() {
  local request update
  request="$(sed -n '/^function clippingRequest()/,/^function applyPatientClipping()/p' web/js/app.js)"
  update="$(sed -n '/^function updateClippingBoundaryFromControl/,/^function resetPatientClipping/p' web/js/app.js)"
  ! grep -Fq 'crosshairLpsMm' <<<"$request" \
    && ! grep -Fq 'retainedSide' <<<"$request" \
    && ! grep -Fq 'crosshairLpsMm' <<<"$update" \
    && ! grep -Fq 'scheduleMprRender' <<<"$update"
}

run_dash() {
  ! grep -RIn \
    --exclude='*.png' --exclude='*.glb' --exclude-dir='__pycache__' \
    '—' web backend \
    docs/phase_history/PHASE4H4_DUAL_SIDED_PATIENT_LPS_CLIPPING.md
}

echo "===== PHASE 4H4 COMPACT VALIDATION ====="
run_quiet "Phase 4H4 unit/UI contract" python -m unittest \
  tests.test_phase4h4_dual_sided_patient_lps_clipping
run_quiet "Phase 4H3B and full regression" bash scripts/run_phase4h3b_checks.sh
run_quiet "Phase 4H4 six-plane clipping probe" node scripts/check_phase4h4_dual_clipping.mjs
run_quiet "Python compile" python -m py_compile \
  tests/test_phase4h4_dual_sided_patient_lps_clipping.py
run_quiet "Application JavaScript syntax" node --check web/js/app.js
run_quiet "Ray marcher JavaScript syntax" node --check web/js/patient-volume-ray-marcher.js
run_quiet "H4 probe JavaScript syntax" node --check scripts/check_phase4h4_dual_clipping.mjs
run_quiet "Shell syntax" run_shell
run_quiet "Patient-data Git safety" run_patient_data
run_quiet "Dual-sided Patient LPS contract" run_dual_clipping_contract
run_quiet "MPR crosshair independence" run_crosshair_independence
run_quiet "Canonical texture safety" run_canonical_texture_safety
run_quiet "Em-dash scan" run_dash
run_quiet "Diff whitespace" git diff --check

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "PHASE4H4_DUAL_SIDED_PATIENT_LPS_CLIPPING_CHECKS_OK=YES"
  echo "TEST_RC=0"
  exit 0
fi

echo "PHASE4H4_DUAL_SIDED_PATIENT_LPS_CLIPPING_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
