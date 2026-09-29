#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def require(condition, label):
    if not condition:
        raise SystemExit(f"{label}=FAIL")
    print(f"{label}=PASS")

backend = (ROOT / "backend/voxelatlas/volume_surfaces.py").read_text(encoding="utf-8")
worker = (ROOT / "scripts/phase6d1_volume_surface_worker.py").read_text(encoding="utf-8")
app = (ROOT / "backend/voxelatlas/app.py").read_text(encoding="utf-8")
frontend = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")
doc = (ROOT / "docs/phase_history/PHASE6D1_VOLUME_DERIVED_SURFACES.md").read_text(encoding="utf-8")

require('source_type": "canonical_volume"' in backend, "PHASE6D1_CANONICAL_VOLUME_SOURCE")
require('VOLUME_SURFACE_MAGIC = b"VXVS"' in backend and 'VOLUME_SURFACE_MAGIC = "VXVS"' in viewer and 'VXSF' not in viewer, "PHASE6D1_DEDICATED_TRANSPORT")
require('VOLUME_SURFACE_MAGIC = "VXVS"' in viewer, "PHASE6D1_BROWSER_TRANSPORT")
require("segmentation_label_maps" not in backend and "totalsegmentator" not in backend.lower(), "PHASE6D1_NO_SEMANTIC_SEGMENTATION_DEPENDENCY")
require('modality == "CT"' in worker and 'source_units != "HU"' in worker and 'surface_units != "HU"' in worker, "PHASE6D1_CT_HU_CONTRACT_PRESERVED")
require('array_index_to_patient_lps' in worker and 'normal_matrix = np.linalg.inv(linear).T' in worker, "PHASE6D1_FULL_PATIENT_LPS_AFFINE")
require('MAX_DEGENERATE_TRIANGLE_FRACTION = 1e-4' in worker and 'bounded_degenerate_face_cleanup' in worker, "PHASE6D1_BOUNDED_DEGENERATE_FACE_CLEANUP")
require('degenerate_triangle_count' in worker and 'unreferenced_vertex_count' in backend, "PHASE6D1_CLEANUP_PROVENANCE")
require('_worker_failure_reason' in backend and 'WORKER_FAILURE_CODES' in backend and 'error_code' in worker, "PHASE6D1_SANITIZED_WORKER_FAILURE_REASON")
require('source_volume") != "immutable"' in worker and '_sha256_file(source.volume_path) != source_sha' in backend, "PHASE6D1_SOURCE_VOLUME_IMMUTABLE")
require('@app.post("/api/studies/latest/volume-surface")' in app, "PHASE6D1_AUTHENTICATED_HTTP_SURFACE")
require('volumeSurfaceLayer.build(level)' in frontend, "PHASE6D1_EXPLICIT_BROWSER_BUILD")
visibility = frontend[frontend.index("function applyVolumeVisibility()"):frontend.index("function updateVolumeBounds()")]
request_build = frontend[frontend.index("async function requestVolumeSurfaceBuild()"):frontend.index("function clearVolumeDerivedSurface()")]
clear_surface = frontend[frontend.index("function clearVolumeDerivedSurface()"):frontend.index("function clearSegmentationWorkflowPoll()")]
require('snapshot.visibility.volume' in visibility and 'volumeLayer.available && state.opacity > 0.001 && modeAllowsVolume' in visibility, "PHASE6D1_VOLUME_VISIBILITY_DELEGATED_TO_MODE_CONTROLLER")
require(request_build.index('await volumeSurfaceLayer.build(level)') < request_build.index('syncReconstructionVisualizationResources()'), "PHASE6D1_EXPLICIT_BUILD_SYNC_ORDER")
require(clear_surface.index('volumeSurfaceLayer.clearSurface()') < clear_surface.index('syncReconstructionVisualizationResources()'), "PHASE6D1_REMOVE_RESYNCS_VISIBILITY_POLICY")
activate = frontend[frontend.index("async function activatePatientVolumeRendering"):frontend.index("function resetWorkspace")]
require('volumeSurfaceLayer.build(' not in activate, "PHASE6D1_NO_AUTOMATIC_SURFACE_BUILD")
require("Phase 6D2" in doc and "not enabled" in doc.lower(), "PHASE6D1_6D2_BOUNDARY")
require("Phase 6E" in doc and "not enabled" in doc.lower(), "PHASE6D1_6E_BOUNDARY")
require("Clinical validation is not claimed" in doc, "CLINICAL_VALIDATION_NOT_CLAIMED")
print("PHASE6D1_ARCHITECTURE_OK=YES")
