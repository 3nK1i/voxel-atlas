#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$(mktemp -d -t voxelatlas-phase6d2b-checks.XXXXXXXX)" || exit 1
FAIL=0
SURFACE_PYTHON="${VOXELATLAS_SURFACE_PYTHON:-}"
CHECK_TIMEOUT_SECONDS="${PHASE6D2B_CHECK_TIMEOUT_SECONDS:-420}"
run_quiet(){ local label="$1"; shift; local safe log rc; safe="$(printf '%s' "$label"|tr -cs '[:alnum:]_.-' '_')"; log="$LOG_DIR/${safe}.log"; if declare -F "$1" >/dev/null 2>&1; then "$@" >"$log" 2>&1; rc=$?; else timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1; rc=$?; fi; if [[ "$rc" -eq 0 ]]; then printf '%-76s PASS\n' "$label"; else printf '%-76s FAIL\n' "$label"; [[ "$rc" -eq 124 ]] && printf 'TIMEOUT_AFTER_SECONDS=%s\n' "$CHECK_TIMEOUT_SECONDS"; tail -n 180 "$log"; FAIL=1; fi; }
check_patient_data_safety(){ if git ls-files --cached --others --exclude-standard | grep -Eiv '(^|/)\.env\.example$' | grep -Eiq '(^|/)(data|uploads?|sample_studies|patients?)(/|$)|(^|/)segmentation/(jobs|providers|label-maps|correction-sessions|surface-tmp|workflow-status)(/|$)|\.(dcm|nii|nii\.gz|nrrd|pth|npy|vxsf2|vxvs)$|(^|/)\.env($|\.)'; then return 1; fi; }
check_geometry_implementation_untouched(){ local changed; changed="$({ git diff --name-only; git diff --cached --name-only; }|sort -u)"; ! printf '%s\n' "$changed" | grep -Eq '^(backend/voxelatlas/(volume_surfaces|segmentation_surfaces|volume_rendering)\.py|scripts/(phase6d1_volume_surface_worker|phase6a_surface_worker|phase6b_surface_worker)\.py)$'; }
check_no_auto_surface_build(){ python - <<'PY'
from pathlib import Path
s=Path('web/js/app.js').read_text()
block=s[s.index('function requestReconstructionVisualizationMode('):s.index('function setVolumeAvailability(')]
raise SystemExit(1 if any(token in block for token in ('fetch(', '.build(', '.clear(', 'segmentation-workflow')) else 0)
PY
}
check_phase6d1_backend_contracts(){ python -m unittest \
  tests.test_phase6d1_volume_derived_surfaces.Phase6D1VolumeDerivedSurfaceTests.test_descriptor_exposes_ct_hu_surface_without_segmentation_dependency \
  tests.test_phase6d1_volume_derived_surfaces.Phase6D1VolumeDerivedSurfaceTests.test_ct_isovalue_must_be_finite_and_strictly_inside_source_range \
  tests.test_phase6d1_volume_derived_surfaces.Phase6D1VolumeDerivedSurfaceTests.test_mri_is_not_silently_given_a_ct_hu_surface \
  tests.test_phase6d1_volume_derived_surfaces.Phase6D1VolumeDerivedSurfaceTests.test_worker_boundary_is_patient_lps_source_immutable_and_uses_dedicated_transport \
  tests.test_phase6d1_volume_derived_surfaces.Phase6D1VolumeDerivedSurfaceTests.test_http_contract_is_authenticated_no_store_and_surface_source_is_explicit \
  tests.test_phase6d1_degenerate_face_cleanup_correction; }

echo "===== PHASE 6D2B NON-DESTRUCTIVE VOLUME / SURFACE TRANSITIONS ====="
run_quiet "Phase 6D2B focused unit contracts" python -m unittest tests.test_phase6d2b_volume_surface_transitions
run_quiet "Phase 6D2B non-destructive visibility behavior" node scripts/check_phase6d2b_nondestructive_visibility.mjs
run_quiet "Phase 6D2B architecture probe" python scripts/check_phase6d2b_architecture.py
run_quiet "Phase 6D2A controller unit regression" python -m unittest tests.test_phase6d2a_visualization_mode_controller
run_quiet "Phase 6D2A controller behavior regression" node scripts/check_phase6d2a_visualization_mode_controller.mjs
run_quiet "Phase 6D2A architecture regression" python scripts/check_phase6d2a_architecture.py
run_quiet "Phase 6D1 backend/extraction preservation" check_phase6d1_backend_contracts
run_quiet "Phase 6D1 volume-surface browser transport regression" node scripts/check_phase6d1_volume_surface_viewer.mjs
run_quiet "Phase 6C segmentation-surface browser regression" node scripts/check_phase6c_multi_structure_viewer.mjs
run_quiet "Phase 6D0 explicit surface-selection regression" python -m unittest tests.test_phase6d0_explicit_surface_selection_correction
run_quiet "Complete previous automated regression" python scripts/run_phase6d2b_previous_regression.py
run_quiet "Phase 6D2B Python compile" python -m py_compile scripts/check_phase6d2b_architecture.py scripts/run_phase6d2b_previous_regression.py tests/test_phase6d2b_volume_surface_transitions.py
run_quiet "Phase 6D2B JavaScript syntax" bash -c 'node --check web/js/app.js && node --check web/js/reconstruction-visualization-mode.js && node --check web/js/volume-surface-viewer.js && node --check web/js/segmentation-surface-viewer.js && node --check scripts/check_phase6d2b_nondestructive_visibility.mjs'
run_quiet "Phase 6D2B shell syntax" bash -n scripts/run_phase6d2b_checks.sh
run_quiet "Patient-data Git safety" check_patient_data_safety
run_quiet "Validated geometry implementation preservation" check_geometry_implementation_untouched
run_quiet "Mode switching performs no geometry build/fetch" check_no_auto_surface_build
run_quiet "Diff whitespace" bash -c 'git diff --check && git diff --cached --check'
printf 'CHECK_LOG_DIR=%s\n' "$LOG_DIR"
if [[ "$FAIL" -eq 0 ]]; then echo "PHASE6D2B_AUTOMATED_CHECKS_OK=YES"; else echo "PHASE6D2B_AUTOMATED_CHECKS_OK=NO"; fi
echo "EXPECTED_BASE=e96f0138bbfe55963b7069680d8ead3d641d64d7"
echo "WORKTREE_BASE=PHASE6D2A_APPLIED_UNSTAGED"
echo "VISUALIZATION_MODES_ACTIVE=VOLUME,SURFACE"
echo "COMBINED_MODE=VISIBLE_BUT_DISABLED_UNTIL_6D2C"
echo "MODE_SWITCH_BUILDS_GEOMETRY=NO"
echo "MODE_SWITCH_ABORTS_PENDING_SEGMENTATION_SURFACES=NO"
echo "RESIDENT_SURFACES=PRESERVED_ACROSS_MODE_SWITCH"
echo "PHASE6D1_DEFAULT_CT_ISOVALUE_HU=300"
echo "PHASE6D1_SURFACE_ONLY_PREVIEW=SUPERSEDED_BY_EXPLICIT_6D2B_MODES"
echo "PHASE6E_PRESENTATION_PROFILES=NOT_ENABLED"
echo "PHASE6F_ADVANCED_INTERACTION=NOT_ENABLED"
echo "CLINICAL_VALIDATION=NOT_CLAIMED"
printf 'TEST_RC=%s\n' "$FAIL"
exit "$FAIL"
