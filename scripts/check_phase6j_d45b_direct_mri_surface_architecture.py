#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"{label}=FAIL")
    print(f"{label}=PASS")


backend = (ROOT / "backend/voxelatlas/volume_surfaces.py").read_text(encoding="utf-8")
worker = (ROOT / "scripts/phase6d1_volume_surface_worker.py").read_text(encoding="utf-8")
regions = (ROOT / "backend/voxelatlas/direct_ct_surface_regions.py").read_text(encoding="utf-8")
app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
index = (ROOT / "web/index.html").read_text(encoding="utf-8")

require('MRI_SURFACE_INTENSITY_UNITS = "normalized_signal"' in backend, "D45B_MR_NORMALIZED_SIGNAL_UNITS")
require('MRI_NORMALIZATION_PROFILE = "robust_percentile_v1"' in backend, "D45B_MR_NORMALIZATION_PROFILE")
require('MRI_NORMALIZATION_LOW_PERCENTILE = 2.0' in backend and 'MRI_NORMALIZATION_HIGH_PERCENTILE = 98.0' in backend, "D45B_MR_ROBUST_PERCENTILE_POLICY")
require('MRI_PRESENTATION_GAUSSIAN_SIGMA_MM = 0.75' in backend, "D45B_MR_PHYSICAL_SMOOTHING_POLICY")
require('source.modality == "MR" and source.intensity_units == "modality"' in backend, "D45B_MR_CANONICAL_SOURCE_GATE")
require('"backend_available": bool(backend_available)' in backend and '"available": available' in backend, "D45B_BACKEND_UI_SEPARATION")
require('"ui_activation": "enabled" if backend_available else "unavailable"' in backend, "D45B_UI_ACTIVATION_CONSUMED_BY_D45C")
require('"segmentation_required": False' in backend, "D45B_NO_SEGMENTATION_DEPENDENCY")
require('"semantic_identity": "none"' in backend, "D45B_NO_ANATOMICAL_IDENTITY_CLAIM")
require('modality == "MR"' in worker and 'MRI_NORMALIZATION_PROFILE' in worker, "D45B_WORKER_MR_CONTRACT")
require('np.percentile' in worker and 'gaussian(' in worker, "D45B_ROBUST_NORMALIZATION_AND_SMOOTHING")
require('sigma_mm / step' in worker, "D45B_PHYSICAL_SPACE_SIGMA")
require('marching_cubes(' in worker and 'positions = vertices @ linear.T + affine[:3, 3]' in worker, "D45B_PATIENT_LPS_MESH_CHAIN")
require('source_volume") != "immutable"' in worker and 'expected_volume_sha256' in worker, "D45B_IMMUTABLE_SOURCE_BINDING")
require('body_threshold: float = -500.0' in regions and 'Direct-CT' in regions, "D45B_CT_REGION_CLASSIFIER_UNCHANGED")
require('Direct MR' in index or 'Direct MR' in app, "D45B_DIRECT_MR_UI_ACTIVATED_BY_D45C")
require('Direct CT' in index and 'CT isovalue' in index, "D45B_CT_UI_UNCHANGED")
require('clinical_validation": "not_claimed"' in backend and 'clinical_validation") != "not_claimed"' in worker, "D45B_NO_CLINICAL_CLAIM")

print("PHASE6J_D45B_ARCHITECTURE_OK=YES")
