#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6d1-checks.XXXXXXXX)" || exit 1
FAIL=0
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-}"
CHECK_TIMEOUT_SECONDS="${PHASE6D1_CHECK_TIMEOUT_SECONDS:-360}"
run_quiet(){ local label="$1"; shift; local safe log rc; safe="$(printf '%s' "$label"|tr -cs '[:alnum:]_.-' '_')"; log="$LOG_DIR/${safe}.log"; if declare -F "$1" >/dev/null 2>&1; then "$@" >"$log" 2>&1; rc=$?; else timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1; rc=$?; fi; if [[ "$rc" -eq 0 ]]; then printf '%-68s PASS\n' "$label"; else printf '%-68s FAIL\n' "$label"; [[ "$rc" -eq 124 ]] && printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"; tail -n 180 "$log"; FAIL=1; fi; }
check_patient_data_safety(){ if git ls-files --cached --others --exclude-standard | grep -Eiv '(^|/)\.env\.example$' | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2|vxvs)$|(^|/)\.env($|\.)'; then return 1; fi; }
check_source_volume_immutability(){ grep -Eq 'source_volume": "immutable"' backend/voxelatlas/volume_surfaces.py && grep -Eq 'source_volume") != "immutable"' scripts/phase6d1_volume_surface_worker.py && ! grep -Eiq '(save|write_bytes|tofile).*volume\.npy' backend/voxelatlas/volume_surfaces.py scripts/phase6d1_volume_surface_worker.py; }
check_phase6ab_geometry_untouched(){ local changed; changed="$({ git diff --name-only; git diff --cached --name-only; }|sort -u)"; ! printf '%s\n' "$changed" | grep -Eq '^backend/voxelatlas/segmentation_surfaces\.py$|^scripts/phase6[ab]_surface_worker\.py$'; }
check_phase6d1_boundary(){ ! grep -Eiq 'surface source selector|presentation profile|fidelity profile|exploded view|export stl|export obj|hausdorff' backend/voxelatlas/volume_surfaces.py web/js/volume-surface-viewer.js web/index.html; }

echo "===== PHASE 6D1 DIRECT VOLUME-DERIVED SURFACE VALIDATION ====="
run_quiet "Phase 6D1 focused unit contracts" python -m unittest tests.test_phase6d1_volume_derived_surfaces
run_quiet "Phase 6D1 degenerate-face cleanup correction" python -m unittest tests.test_phase6d1_degenerate_face_cleanup_correction
run_quiet "Phase 6D1 surface-only preview correction" python -m unittest tests.test_phase6d1_surface_only_preview_correction
run_quiet "Phase 6D1 architecture probe" python scripts/check_phase6d1_volume_surface_architecture.py
run_quiet "Phase 6D1 browser surface contract" node scripts/check_phase6d1_volume_surface_viewer.mjs
run_quiet "Phase 6D1 isolated worker smoke" python scripts/check_phase6d1_volume_surface_worker.py --python "$SURFACE_PYTHON"
run_quiet "Phase 6D0 on-demand workflow regression" python -m unittest tests.test_phase6d0_on_demand_segmentation_workflow
run_quiet "Phase 6D0 explicit surface-selection regression" python -m unittest tests.test_phase6d0_explicit_surface_selection_correction
run_quiet "Phase 6C browser presentation regression" node scripts/check_phase6c_multi_structure_viewer.mjs
run_quiet "Complete previous automated regression" python scripts/run_phase6d1_previous_regression.py
run_quiet "Phase 6D1 Python compile" python -m py_compile backend/voxelatlas/app.py backend/voxelatlas/volume_rendering.py backend/voxelatlas/volume_surfaces.py scripts/phase6d1_volume_surface_worker.py scripts/check_phase6d1_volume_surface_architecture.py scripts/check_phase6d1_volume_surface_worker.py scripts/qualify_phase6d1_real_ct_volume_surface.py scripts/run_phase6d1_previous_regression.py tests/test_phase6d1_volume_derived_surfaces.py tests/test_phase6d1_degenerate_face_cleanup_correction.py tests/test_phase6d1_surface_only_preview_correction.py
run_quiet "Phase 6D1 JavaScript syntax" bash -c 'node --check web/js/volume-surface-viewer.js && node --check web/js/app.js && node --check scripts/check_phase6d1_volume_surface_viewer.mjs'
run_quiet "Phase 6D1 shell syntax" bash -n scripts/run_phase6d1_checks.sh
run_quiet "Phase 6A isolated surface runtime regression" python scripts/check_phase6a_surface_environment.py --python "$SURFACE_PYTHON"
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Canonical source-volume immutability contract" check_source_volume_immutability
run_quiet "Phase 6A/6B segmentation geometry preservation" check_phase6ab_geometry_untouched
run_quiet "Phase 6D1 roadmap boundary" check_phase6d1_boundary
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'
printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then echo "PHASE6D1_AUTOMATED_CHECKS_OK=YES"; else echo "PHASE6D1_AUTOMATED_CHECKS_OK=NO"; fi
echo "SOURCE_TYPE=CANONICAL_VOLUME"
echo "SEGMENTATION_REQUIRED=NO"
echo "CT_HU_ISOSURFACE=QUALIFIED_BASELINE"
echo "DEGENERATE_FACE_CLEANUP=BOUNDED_POST_LPS_FILTER"
echo "MAX_DEGENERATE_TRIANGLE_FRACTION=0.0001"
echo "WORKER_FAILURE_REASON=BOUNDED_SANITIZED_CODE"
echo "MRI_VOLUME_SURFACE=NOT_SILENTLY_ENABLED"
echo "SURFACE_BUILD=EXPLICIT_USER_ACTION_ONLY"
echo "SURFACE_PREVIEW=SURFACE_ONLY_UNTIL_PHASE6D2"
echo "PHASE6D2_VISUALIZATION_MODES=NOT_ENABLED"
echo "PHASE6E_PRESENTATION_PROFILES=NOT_ENABLED"
echo "PHASE6A_ACCURATE_REFERENCE=IMMUTABLE"
echo "PHASE6B_REFINED_GEOMETRY=PRESERVED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
