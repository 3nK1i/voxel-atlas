#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
    structures = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
    app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
    index = (ROOT / "web/index.html").read_text(encoding="utf-8")
    styles = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
    surfaces = (ROOT / "backend/voxelatlas/segmentation_surfaces.py").read_text(encoding="utf-8")

    require("this.items = new Map()" in viewer,
            "Phase 6C surface residency is not multi-structure")
    require("MAX_CONCURRENT_SURFACE_LOADS = 2" in viewer,
            "Phase 6C bounded browser surface concurrency changed")
    require("surfaceVisible" in viewer and "surfaceVisible" in structures,
            "Phase 6C independent 3D surface visibility is missing")
    require("activateSurfaceForStructure" in structures,
            "Selecting additional structures does not activate their 3D surfaces")
    require("structure.surfaceVisible = visible" in structures,
            "Show/hide-all does not control 3D surface presentation")
    require("structure.surfaceVisible = visibility.checked" in structures,
            "Structure visibility does not synchronize 3D surface visibility")
    require("MeshStandardMaterial" in viewer and "MeshPhongMaterial" not in viewer,
            "Phase 6C polished standard material is not selected")
    require("roughness: 0.58" in viewer and "metalness: 0.0" in viewer,
            "Phase 6C matte anatomical material contract changed")
    require("flatShading: false" in viewer,
            "Phase 6C smooth shading is not explicit")
    require("segmentationSurfaceFillLight" in app and "segmentationSurfaceRimLight" in app,
            "Phase 6C presentation lighting is incomplete")
    require("3D Segmentation Surfaces" in index,
            "Phase 6C multi-structure UI identity is missing")
    require("Patient LPS refined surfaces" in index,
            "Phase 6B refined geometry identity was lost")
    require("polished multi-structure presentation" in index,
            "Phase 6C presentation identity is missing")
    require("phase6a-r1-phase6b-r1-phase6c-r2" in app,
            "Phase 6C surface module cache identity is missing")
    require("phase6a-r1-phase6b-r1-phase6c-r2" in index,
            "Phase 6C application cache identity is missing")
    require("_surfaceStatusSnapshot" in viewer and 'return "building"' in viewer
            and 'return "queued"' in viewer,
            "Phase 6C real surface build state tracking is incomplete")
    require("Building ${selected.displayName} surface…" in viewer,
            "Phase 6C selected-structure build feedback is missing")
    require("setSurfaceStatusSnapshot" in structures and "structure-surface-state" in structures,
            "Phase 6C per-structure surface state feedback is missing")
    require("segmentation-surface-spin" in styles
            and 'data-surface-state="building"' in styles,
            "Phase 6C surface build activity indicator is missing")
    require('aria-live' in app,
            "Phase 6C asynchronous surface status is not announced")

    # Presentation-only check; geometry and provenance remain unchanged.
    require("this.descriptor.presentation_quality" in viewer,
            "Phase 6B refined presentation quality was bypassed")
    require("requestedQuality === \"refined\"" in viewer,
            "Phase 6B refined response binding was removed")
    require("derived_from_accurate_surface" in surfaces,
            "Phase 6A/6B immutable reference chain is missing")
    lowered_viewer = viewer.lower()
    for forbidden in ("marching_cubes", "smooth_bounded", "cluster_candidate"):
        require(forbidden not in lowered_viewer,
                f"Phase 6C browser presentation mutates geometry: {forbidden}")

    combined = (viewer + structures + app + index).lower()
    for forbidden in (
        "start segmentation",
        "volume-derived surface",
        "custom hu",
        "presentation profile",
        "fidelity profile",
        "exploded view",
        "export stl",
        "export obj",
        "hausdorff",
    ):
        require(forbidden not in combined,
                f"Later Phase 6 functionality leaked into 6C: {forbidden}")
    require("clinical-grade" not in combined and "diagnostic accuracy" not in combined,
            "Clinical claim found")

    print("PHASE6C_MULTI_STRUCTURE_RESIDENCY=PASS")
    print("PHASE6C_PROGRESSIVE_STRUCTURE_ACTIVATION=PASS")
    print("PHASE6C_BOUNDED_BROWSER_CONCURRENCY=PASS")
    print("PHASE6C_POLISHED_STANDARD_MATERIAL=PASS")
    print("PHASE6C_SMOOTH_SHADING=PASS")
    print("PHASE6C_PRESENTATION_LIGHTING=PASS")
    print("PHASE6C_SURFACE_BUILD_FEEDBACK=PASS")
    print("PHASE6C_PER_STRUCTURE_BUILD_STATE=PASS")
    print("PHASE6C_REFINED_GEOMETRY_PRESERVED=PASS")
    print("PHASE6C_PATIENT_LPS_PROVENANCE_PRESERVED=PASS")
    print("PHASE6C_ROADMAP_BOUNDARY=PASS")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6C_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
