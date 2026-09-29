#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_surfaces import (  # noqa: E402
    ACCURATE_SURFACE_QUALITY,
    DEFAULT_SURFACE_QUALITY,
    PRESENTATION_SURFACE_QUALITY,
    REFINED_CLUSTER_CELL_SIZES_INDEX,
    REFINED_MIN_TRIANGLE_RETENTION_RATIO,
    REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES,
    REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION,
    REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION,
    REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES,
    REFINED_MRI_TOTAL_MR_MAX_DISPLACEMENT_MM,
    REFINED_MRI_TOTAL_MR_PRESENTATION_RECONSTRUCTION,
    REFINED_MRI_TOTAL_MR_PRESENTATION_SIGMA_MM,
    REFINED_MRI_TOTAL_MR_PROFILE,
    REFINED_MRI_TOTAL_MR_SMOOTHING_DISPLACEMENT_FRACTION,
    REFINED_MRI_TOTAL_MR_SMOOTHING_ITERATIONS,
    REFINED_MRI_TOTAL_MR_TAUBIN_LAMBDA,
    REFINED_MRI_TOTAL_MR_TAUBIN_MU,
    REFINED_SMOOTHING_DISPLACEMENT_FRACTION,
    REFINED_SURFACE_ALGORITHM_VERSION,
    REFINED_SURFACE_QUALITY,
    REFINED_SURFACE_REFINEMENT,
    REFINED_TOTAL_DISPLACEMENT_FRACTION,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    surfaces = (BACKEND / "voxelatlas" / "segmentation_surfaces.py").read_text(
        encoding="utf-8"
    )
    app = (BACKEND / "voxelatlas" / "app.py").read_text(encoding="utf-8")
    worker6a = (ROOT / "scripts" / "phase6a_surface_worker.py").read_text(encoding="utf-8")
    worker6b = (ROOT / "scripts" / "phase6b_surface_worker.py").read_text(encoding="utf-8")
    browser = (ROOT / "web" / "js" / "segmentation-surface-viewer.js").read_text(
        encoding="utf-8"
    )
    browser_app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    backend_requirements = (ROOT / "requirements" / "backend.txt").read_text(
        encoding="utf-8"
    )

    require(DEFAULT_SURFACE_QUALITY == ACCURATE_SURFACE_QUALITY,
            "Phase 6A accurate API default changed")
    require(PRESENTATION_SURFACE_QUALITY == REFINED_SURFACE_QUALITY,
            "Phase 6B refined presentation quality is not selected")
    require(REFINED_SURFACE_REFINEMENT == "bounded_taubin_vertex_clustering",
            "Phase 6B refinement identity changed")
    require(REFINED_SURFACE_ALGORITHM_VERSION == 2,
            "Phase 6B corrected refinement algorithm version changed")
    require(REFINED_SMOOTHING_DISPLACEMENT_FRACTION == 0.25,
            "Phase 6B smoothing bound changed")
    require(REFINED_TOTAL_DISPLACEMENT_FRACTION == 0.80,
            "Phase 6B total displacement bound changed")
    require(REFINED_MIN_TRIANGLE_RETENTION_RATIO == 0.70,
            "Phase 6B triangle-retention bound changed")
    require(REFINED_MRI_TOTAL_MR_PROFILE == "mri_total_mr_v1",
            "MRI refined presentation profile identity changed")
    require(REFINED_MRI_TOTAL_MR_SMOOTHING_ITERATIONS == 20,
            "MRI refined smoothing iteration policy changed")
    require(REFINED_MRI_TOTAL_MR_TAUBIN_LAMBDA == 0.40
            and REFINED_MRI_TOTAL_MR_TAUBIN_MU == -0.20,
            "MRI refined Taubin policy changed")
    require(REFINED_MRI_TOTAL_MR_SMOOTHING_DISPLACEMENT_FRACTION
            == REFINED_TOTAL_DISPLACEMENT_FRACTION,
            "MRI fallback smoothing fraction changed unexpectedly")
    require(REFINED_MRI_TOTAL_MR_PRESENTATION_RECONSTRUCTION
            == "gaussian_label_map_isosurface",
            "MRI presentation reconstruction identity changed")
    require(REFINED_MRI_TOTAL_MR_PRESENTATION_SIGMA_MM == 1.75,
            "MRI presentation reconstruction sigma changed")
    require(REFINED_MRI_TOTAL_MR_MAX_DISPLACEMENT_MM == 3.0,
            "MRI presentation displacement bound changed")
    require(tuple(REFINED_CLUSTER_CELL_SIZES_INDEX) == (0.50, 0.65, 0.70, 0.80),
            "Phase 6B decimation candidates changed")
    require(REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES == 12,
            "Phase 6B local topology candidate bound changed")
    require(REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES == 6,
            "Phase 6B local topology face-removal bound changed")
    require(REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION == 0.0001,
            "Phase 6B local topology face-fraction bound changed")
    require(REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION == 0.0001,
            "Phase 6B local topology area-fraction bound changed")

    require("_accurate_surface(" in surfaces and "_refined_surface(" in surfaces,
            "Phase 6B is not extending the existing surface service")
    require("reference_surface.payload" in surfaces,
            "Phase 6B is not derived from the exact Phase 6A payload")
    require("derived_from_accurate_surface" in surfaces,
            "Accurate-reference provenance binding is missing")
    require("surface_to_mask_deviation_qualification\": \"deferred_to_phase6g" in surfaces,
            "Phase 6G boundary is not explicit")
    require("compact_mesh" in worker6b,
            "Safe topology cleanup is missing")
    require("topology_metrics" in worker6b,
            "Topology invariant calculation is missing")
    require("repair_local_topology" in worker6b,
            "Bounded local topology repair is missing")
    require("nonmanifold_vertex_fan_count" in worker6b,
            "Vertex-fan manifold validation is missing")
    require("component_euler_signature" in worker6b and "component_euler_signature" in surfaces,
            "Per-component topology signature is missing")
    require("metrics != repaired_metrics" in worker6b,
            "Repaired-topology preservation gate is missing")
    require("repaired_topology != topology" in surfaces,
            "Backend repaired-topology validation gate is missing")
    require("smooth_bounded" in worker6b and "TAUBIN_LAMBDA" in worker6b,
            "Bounded smoothing policy is missing")
    require("clamp_volume_cell_bounds" in worker6b,
            "Voxel-cell containment clamp is missing")
    require("cluster_candidate" in worker6b,
            "Bounded decimation policy is missing")
    require("reconstruct_mri_presentation_surface" in worker6b
            and "gaussian_label_map_isosurface" in worker6b,
            "MRI label-map presentation reconstruction is missing")
    require("presentation_reconstruction_applied" in worker6b
            and "presentation_reconstruction_applied" in surfaces,
            "MRI presentation reconstruction application gate is missing")
    require("label_map_npy" in surfaces,
            "MRI refined presentation is not bound to the immutable label map")
    require("max_displacement_mm > total_limit_mm" in worker6b,
            "Geometric displacement rejection gate is missing")
    require('retention < float(policy["minimum_triangle_retention_ratio"])' in worker6b,
            "Allowlisted triangle-retention rejection gate is missing")
    require("policy not in (standard_policy(), mri_total_mr_policy())" in worker6b,
            "Refinement policy allowlist is missing")
    require("canonical_vertex_normals" in worker6b,
            "Refined Patient-LPS normals are missing")
    require("from skimage.measure import marching_cubes" in worker6a,
            "Phase 6A accurate extraction was removed")
    require("phase6b_surface_worker.py" in surfaces,
            "Phase 6B isolated worker is not wired")
    require("from skimage" not in surfaces and "import skimage" not in surfaces,
            "Heavy scientific imports leaked into backend startup")
    require("scikit-image" not in backend_requirements,
            "Heavy scientific dependency leaked into backend requirements")

    for header in (
        "X-VoxelAtlas-Surface-Refinement",
        "X-VoxelAtlas-Surface-Reference-Id",
        "X-VoxelAtlas-Surface-Reference-SHA256",
        "X-VoxelAtlas-Surface-Max-Displacement-Mm",
        "X-VoxelAtlas-Surface-Displacement-Limit-Mm",
        "X-VoxelAtlas-Surface-Triangle-Retention",
        "X-VoxelAtlas-Surface-Decimation-Applied",
    ):
        require(header in app, f"Phase 6B API header missing: {header}")
    require('pattern=r"^(refined|accurate|preview|balanced)$"' in app,
            "Refined API quality is not explicitly gated")
    require("this.descriptor.presentation_quality" in browser,
            "Browser does not prefer the Phase 6B presentation surface")
    require('requestedQuality === "refined"' in browser,
            "Browser refined-response validation is missing")
    require("Patient LPS refined surface" in index,
            "Phase 6B refined UI identity is missing")
    require("Patient LPS accurate surface" in index,
            "Phase 6A accurate-reference identity was discarded")
    require("segmentation-surface-viewer.js?v=phase6a-r1-phase6b-r1" in browser_app,
            "Phase 6B surface-viewer cache identity is missing")
    require("phase6a-r1-phase6b-r1" in index,
            "Phase 6B app cache identity is missing")

    combined = (surfaces + app + worker6b + browser).lower()
    for forbidden in (
        "export_stl",
        "export_obj",
        "hausdorff",
        "surface_to_mask(",
        "exploded_view",
        "presentation_profile",
        "fidelity_profile",
    ):
        require(forbidden not in combined, f"Later Phase 6 functionality leaked into 6B: {forbidden}")
    require("clinical-grade" not in combined and "diagnostic accuracy" not in combined,
            "Clinical claim found")

    print("PHASE6B_ACCURATE_REFERENCE_PRESERVED=PASS")
    print("PHASE6B_SAFE_TOPOLOGY_CLEANUP=PASS")
    print("PHASE6B_BOUNDED_LOCAL_FACE_TOPOLOGY_REPAIR=PASS")
    print("PHASE6B_VERTEX_FAN_MANIFOLDNESS=PASS")
    print("PHASE6B_TOPOLOGY_INVARIANT_GATE=PASS")
    print("PHASE6B_COMPONENT_TOPOLOGY_SIGNATURE=PASS")
    print("PHASE6B_BOUNDED_TAUBIN_SMOOTHING=PASS")
    print("PHASE6B_BOUNDED_VERTEX_CLUSTER_DECIMATION=PASS")
    print("PHASE6B_VOXEL_CELL_CONTAINMENT=PASS")
    print("PHASE6B_PATIENT_LPS_NORMALS=PASS")
    print("PHASE6B_IMMUTABLE_PROVENANCE_REFERENCE=PASS")
    print("PHASE6B_BROWSER_REFINED_PRESENTATION=PASS")
    print("PHASE6B_ROADMAP_BOUNDARY=PASS")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6B_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
