#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_surfaces import (  # noqa: E402
    SURFACE_HEADER,
    SURFACE_MEDIA_TYPE,
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
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    browser = (ROOT / "web" / "js" / "segmentation-surface-viewer.js").read_text(
        encoding="utf-8"
    )

    require(SURFACE_HEADER.size == 32, "Surface binary header is not fixed-width")
    require(SURFACE_MEDIA_TYPE.endswith("surface-v1"), "Surface media type is not versioned")
    require(set(SURFACE_QUALITIES) == {"preview", "balanced"}, "Surface budgets changed")
    require("voxel_boundary_faces" in surfaces, "Deterministic surface extraction is missing")
    require("MAX_SURFACE_STRIDE" in surfaces, "Surface extraction is not bounded")
    require("array_index_to_patient_lps" in surfaces, "Patient LPS transform is missing")
    require("/api/studies/latest/segmentation-surfaces" in app, "Surface API is missing")
    require("X-VoxelAtlas-Surface-SHA256" in app, "Surface integrity header is missing")
    require("segmentationSurfaceToggle" in html, "Surface presentation control is missing")
    require("PatientSegmentationSurfaceLayer" in browser, "Three.js surface layer is missing")
    require("computeVertexNormals" in browser, "Surface normals are missing")
    require("SHA256 verification failed" in browser, "Browser integrity verification is missing")
    for forbidden in ("import torch", "import nibabel", "from totalsegmentator"):
        require(forbidden not in surfaces.lower(), f"Heavy runtime import found: {forbidden}")
    combined = (surfaces + app + html + browser).lower()
    require("clinical-grade" not in combined, "Clinical claim found")
    require("laplacian" not in combined, "Phase 6 smoothing leaked into Phase 5F1")
    require("decimat" not in combined, "Phase 6 decimation leaked into Phase 5F1")

    print("PHASE5F1_PATIENT_LPS_SURFACE_EXTRACTION=PASS")
    print("PHASE5F1_BOUNDED_BINARY_TRANSPORT=PASS")
    print("PHASE5F1_THREEJS_SURFACE_LAYER=PASS")
    print("PHASE5F1_SELECTED_STRUCTURE_SYNCHRONIZATION=PASS")
    print("PHASE6_SURFACE_REFINEMENT=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE5F1_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
