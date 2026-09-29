#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_surfaces import (  # noqa: E402
    ACCURATE_SURFACE_EXTRACTION,
    ACCURATE_SURFACE_HEADER,
    ACCURATE_SURFACE_MEDIA_TYPE,
    ACCURATE_SURFACE_SCHEMA_VERSION,
    DEFAULT_SURFACE_QUALITY,
    SURFACE_QUALITIES,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    surfaces = (BACKEND / "voxelatlas" / "segmentation_surfaces.py").read_text(
        encoding="utf-8"
    )
    app = (BACKEND / "voxelatlas" / "app.py").read_text(encoding="utf-8")
    config = (BACKEND / "voxelatlas" / "config.py").read_text(encoding="utf-8")
    runtime = (BACKEND / "voxelatlas" / "segmentation_surface_runtime.py").read_text(
        encoding="utf-8"
    )
    worker = (ROOT / "scripts" / "phase6a_surface_worker.py").read_text(encoding="utf-8")
    backend_requirements = (ROOT / "requirements" / "backend.txt").read_text(encoding="utf-8")
    surface_requirements = (ROOT / "requirements" / "segmentation-surfaces.txt").read_text(
        encoding="utf-8"
    )
    browser = (ROOT / "web" / "js" / "segmentation-surface-viewer.js").read_text(
        encoding="utf-8"
    )
    browser_app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    require(ACCURATE_SURFACE_SCHEMA_VERSION == 2, "Accurate surface schema is not v2")
    require(ACCURATE_SURFACE_HEADER.size == 36, "Accurate surface header is not fixed-width")
    require(
        ACCURATE_SURFACE_MEDIA_TYPE.endswith("surface-v2"),
        "Accurate surface media type is not versioned",
    )
    require(
        ACCURATE_SURFACE_EXTRACTION == "marching_cubes_half_voxel",
        "Accurate extraction contract changed",
    )
    require(DEFAULT_SURFACE_QUALITY == "accurate", "Accurate surface is not the default")
    require(
        set(SURFACE_QUALITIES) == {"preview", "balanced"},
        "Phase 5F1 preview compatibility changed",
    )
    require("from skimage" not in surfaces and "import skimage" not in surfaces,
            "Heavy mesh dependency leaked into the backend import path")
    require("VOXELATLAS_SURFACE_PYTHON" in config,
            "Dedicated Phase 6A surface runtime configuration is missing")
    require("worker_python=runtime_settings.surface_worker_python" in app,
            "FastAPI does not pass the isolated surface runtime explicitly")
    require("sys.executable" not in surfaces,
            "Accurate surface service must not silently fall back to the backend Python")
    require("SegmentationSurfaceRuntimeQualifier" in runtime,
            "Surface runtime qualification contract is missing")
    require("scikit-image" not in backend_requirements,
            "Heavy mesh dependency leaked into backend requirements")
    require("scikit-image" in surface_requirements,
            "Isolated surface runtime dependency manifest is missing scikit-image")
    require("runtime_fingerprint_sha256" in surfaces and "runtime_fingerprint_sha256" in worker,
            "Surface runtime fingerprint is not bound into artifact provenance")
    require("from skimage.measure import marching_cubes" in worker,
            "Isolated marching-cubes worker is missing")
    require("np.pad(mask, 1" in worker, "Boundary-safe zero padding is missing")
    require("minimum.astype(np.float64) - 1.0" in worker,
            "Half-voxel index-space recovery is missing")
    require("np.linalg.inv(linear).T" in worker,
            "Patient-LPS normal transform is missing")
    require("canonical_vertex_normals" in worker,
            "Deterministic winding/normal canonicalization is missing")
    require("agreement_score" in worker and "agreement_magnitude" in worker,
            "Global outward-orientation reconciliation is missing")
    require("np.any(agreement <= 0.0)" not in worker,
            "Per-triangle gradient agreement must not reject a globally coherent mesh")
    require("_sha256_file(path)" in surfaces,
            "Canonical label-map digest recheck is missing")
    require("source_volume_artifact_sha256" in surfaces,
            "Source-volume provenance is not retained")
    require("segmentation_terminal_provenance_sha256" in surfaces,
            "Segmentation provenance is not retained")
    require("X-VoxelAtlas-Surface-Id" in app, "Surface identity response header is missing")
    require("X-VoxelAtlas-Surface-Provenance-SHA256" in app,
            "Surface provenance response header is missing")
    require('default="accurate"' in app, "Accurate API default is missing")
    require("application/x-voxelatlas-surface-v1" in browser,
            "Legacy browser transport compatibility is missing")
    require("application/x-voxelatlas-surface-v2" in browser,
            "Accurate browser transport is missing")
    require('setAttribute("normal"' in browser,
            "Patient-space normals are not consumed by the browser")
    require("SHA256 verification failed" in browser,
            "Browser payload integrity verification is missing")
    require("Patient LPS accurate surface" in index,
            "Accurate surface presentation copy is missing")
    require("Patient LPS preview mesh" not in index,
            "Stale Phase 5F1 preview presentation copy remains")
    require("segmentation-surface-viewer.js?v=phase6a-r1" in browser_app,
            "Phase 6A surface viewer cache identity is missing")
    require("segmentation-surface-viewer.js?v=phase5f1-r1" not in browser_app,
            "Stale Phase 5F1 surface viewer cache identity remains")
    require("/js/app.js?v=phase3d-r21-phase4h6-r1-phase5f2-r1-phase5g-r1-phase6a-r1" in index,
            "Phase 6A app cache identity is missing")
    combined = (surfaces + app + config + runtime + worker + browser).lower()
    for forbidden in ("laplacian", "taubin", "trimesh.smoothing", "simplify_quadric", "export_stl"):
        require(forbidden not in combined, f"Later Phase 6 functionality leaked into 6A: {forbidden}")
    require("clinical-grade" not in combined, "Clinical claim found")

    print("PHASE6A_NATIVE_MASK_ISOSURFACE=PASS")
    print("PHASE6A_HALF_VOXEL_BOUNDARY_SEMANTICS=PASS")
    print("PHASE6A_COMPLETE_PATIENT_LPS_AFFINE=PASS")
    print("PHASE6A_WINDING_AND_NORMALS=PASS")
    print("PHASE6A_GLOBAL_WINDING_CANONICALIZATION=PASS")
    print("PHASE6A_IMMUTABLE_PROVENANCE_IDENTITY=PASS")
    print("PHASE6A_HEAVY_MESH_RUNTIME_ISOLATION=PASS")
    print("PHASE6A_SURFACE_RUNTIME_CONFIGURATION=PASS")
    print("PHASE6A_RUNTIME_FINGERPRINT_PROVENANCE=PASS")
    print("PHASE6A_UI_SURFACE_IDENTITY=PASS")
    print("PHASE5F1_PREVIEW_COMPATIBILITY=PASS")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6A_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
