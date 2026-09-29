#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from time import perf_counter
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation import SegmentationValidationError  # noqa: E402
from voxelatlas.segmentation_label_maps import SegmentationLabelMapService  # noqa: E402
from voxelatlas.segmentation_qualification import _canonical_affine_bounds  # noqa: E402
from voxelatlas.segmentation_surfaces import (  # noqa: E402
    ACCURATE_SURFACE_MEDIA_TYPE,
    ACCURATE_SURFACE_QUALITY,
    REFINED_MIN_TRIANGLE_RETENTION_RATIO,
    REFINED_SURFACE_ALGORITHM_VERSION,
    REFINED_SURFACE_QUALITY,
    REFINED_SURFACE_REFINEMENT,
    SegmentationSurfaceService,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify one real Phase 6B topology-repaired, bounded Patient-LPS "
            "segmentation surface while preserving the Phase 6A reference."
        )
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--label-map-id", required=True)
    parser.add_argument("--label-id", type=int, default=91)
    parser.add_argument(
        "--python",
        default=os.environ.get("VOXELATLAS_SURFACE_PYTHON"),
        help="Qualified isolated surface Python executable",
    )
    parser.add_argument("--max-refinement-seconds", type=float, default=60.0)
    parser.add_argument("--expected-accurate-sha256", default=None)
    args = parser.parse_args()
    if args.max_refinement_seconds <= 0:
        raise SystemExit("--max-refinement-seconds must be positive")
    if not args.python:
        raise SystemExit(
            "Surface runtime is not configured; pass --python or set "
            "VOXELATLAS_SURFACE_PYTHON"
        )
    if args.expected_accurate_sha256 is not None:
        digest = args.expected_accurate_sha256.lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise SystemExit("--expected-accurate-sha256 must be a lowercase SHA256")
        args.expected_accurate_sha256 = digest

    label_maps = SegmentationLabelMapService(data_dir=args.data_dir)
    descriptor = label_maps.get(args.label_map_id)
    service = SegmentationSurfaceService(
        data_dir=args.data_dir,
        label_map_service=label_maps,
        worker_python=args.python,
    )

    accurate_started = perf_counter()
    accurate = service.surface_latest(
        label_id=args.label_id,
        label_map_id=args.label_map_id,
        quality=ACCURATE_SURFACE_QUALITY,
    )
    accurate_seconds = perf_counter() - accurate_started
    if (
        args.expected_accurate_sha256 is not None
        and accurate.payload_sha256 != args.expected_accurate_sha256
    ):
        raise SegmentationValidationError(
            "Phase 6A accurate reference payload changed before Phase 6B qualification"
        )

    refinement_started = perf_counter()
    refined = service.surface_latest(
        label_id=args.label_id,
        label_map_id=args.label_map_id,
        quality=REFINED_SURFACE_QUALITY,
    )
    refinement_seconds = perf_counter() - refinement_started
    if refinement_seconds > args.max_refinement_seconds:
        raise SegmentationValidationError("Phase 6B refinement performance budget was exceeded")

    cell_bounds = _canonical_affine_bounds(descriptor, voxel_cells=True)
    for axis in range(3):
        if (
            refined.bounds_lps_mm[axis] < cell_bounds[axis] - 1e-3
            or refined.bounds_lps_mm[axis + 3] > cell_bounds[axis + 3] + 1e-3
        ):
            raise SegmentationValidationError(
                "Phase 6B surface exceeds canonical Patient-LPS voxel-cell bounds"
            )
    if (
        accurate.quality != ACCURATE_SURFACE_QUALITY
        or refined.quality != REFINED_SURFACE_QUALITY
        or refined.media_type != ACCURATE_SURFACE_MEDIA_TYPE
        or refined.refinement != REFINED_SURFACE_REFINEMENT
        or refined.reference_surface_id != accurate.surface_id
        or refined.reference_payload_sha256 != accurate.payload_sha256
        or refined.normal_count != refined.vertex_count
        or refined.nonmanifold_edge_count != 0
        or refined.nonmanifold_vertex_count != 0
        or refined.boundary_edge_count != 0
        or refined.connected_component_count <= 0
        or refined.reference_connected_component_count != refined.connected_component_count
        or refined.topology_repair_initial_displacement_mm != 0.0
        or refined.max_displacement_mm > refined.displacement_limit_mm + 1e-6
        or refined.triangle_retention_ratio < REFINED_MIN_TRIANGLE_RETENTION_RATIO - 1e-9
        or refined.triangle_retention_ratio > 1.0 + 1e-9
        or not refined.surface_id.startswith("surf-")
        or len(refined.provenance_sha256) != 64
    ):
        raise SegmentationValidationError("Phase 6B refined surface contract is incomplete")

    accurate_after = service.surface_latest(
        label_id=args.label_id,
        label_map_id=args.label_map_id,
        quality=ACCURATE_SURFACE_QUALITY,
    )
    if (
        accurate_after.surface_id != accurate.surface_id
        or accurate_after.payload_sha256 != accurate.payload_sha256
        or accurate_after.payload != accurate.payload
    ):
        raise SegmentationValidationError(
            "Phase 6B refinement modified the Phase 6A accurate reference"
        )

    print("===== PHASE 6B REAL BOUNDED SURFACE REFINEMENT QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    print(f"LABEL_MAP_ID={refined.label_map_id}")
    print(f"SOURCE_STUDY_ID={descriptor['source_study_id']}")
    print(f"LABEL_ID={refined.label_id}")
    print(f"ACCURATE_SURFACE_ID={accurate.surface_id}")
    print(f"ACCURATE_PAYLOAD_SHA256={accurate.payload_sha256}")
    print(f"ACCURATE_VERTEX_COUNT={accurate.vertex_count}")
    print(f"ACCURATE_TRIANGLE_COUNT={accurate.triangle_count}")
    print(f"REFINED_SURFACE_ID={refined.surface_id}")
    print(f"REFINED_PAYLOAD_SHA256={refined.payload_sha256}")
    print(f"REFINED_PROVENANCE_SHA256={refined.provenance_sha256}")
    print(f"REFINEMENT={refined.refinement}")
    print(f"REFINEMENT_ALGORITHM_VERSION={REFINED_SURFACE_ALGORITHM_VERSION}")
    print(f"REFINED_VERTEX_COUNT={refined.vertex_count}")
    print(f"REFINED_TRIANGLE_COUNT={refined.triangle_count}")
    print(f"NORMAL_COUNT={refined.normal_count}")
    print(f"TRIANGLE_RETENTION_RATIO={refined.triangle_retention_ratio:.9f}")
    print(f"DECIMATION_APPLIED={'YES' if refined.decimation_applied else 'NO'}")
    print(f"DECIMATION_CELL_SIZE_INDEX={refined.decimation_cell_size_index:.6f}")
    print(f"TOPOLOGY_REPAIR_COUNT={refined.topology_repair_count}")
    print(f"SAFE_COMPACT_REPAIR_COUNT={refined.safe_compact_repair_count}")
    print(
        "POST_COMPACT_REFERENCE_TRIANGLE_COUNT="
        f"{refined.post_compact_reference_triangle_count}"
    )
    print(f"REFERENCE_BOUNDARY_EDGE_COUNT={refined.reference_boundary_edge_count}")
    print(
        "REFERENCE_NONMANIFOLD_EDGE_COUNT="
        f"{refined.reference_nonmanifold_edge_count}"
    )
    print(
        "REFERENCE_NONMANIFOLD_VERTEX_COUNT="
        f"{refined.reference_nonmanifold_vertex_count}"
    )
    print(
        "REFERENCE_CONNECTED_COMPONENT_COUNT="
        f"{refined.reference_connected_component_count}"
    )
    print(
        "LOCAL_TOPOLOGY_REPAIR_APPLIED="
        f"{'YES' if refined.topology_local_repair_applied else 'NO'}"
    )
    print(
        "TOPOLOGY_REPAIR_REMOVED_FACE_COUNT="
        f"{refined.topology_repair_removed_face_count}"
    )
    print(
        "TOPOLOGY_REPAIR_REMOVED_FACE_FRACTION="
        f"{refined.topology_repair_removed_face_fraction:.12f}"
    )
    print(
        "TOPOLOGY_REPAIR_REMOVED_AREA_MM2="
        f"{refined.topology_repair_removed_area_mm2:.9f}"
    )
    print(
        "TOPOLOGY_REPAIR_REMOVED_AREA_FRACTION="
        f"{refined.topology_repair_removed_area_fraction:.12f}"
    )
    print(
        "TOPOLOGY_REPAIR_INITIAL_DISPLACEMENT_MM="
        f"{refined.topology_repair_initial_displacement_mm:.6f}"
    )
    print(
        "REPAIRED_REFERENCE_TRIANGLE_COUNT="
        f"{refined.repaired_reference_triangle_count}"
    )
    print(f"BOUNDARY_EDGE_COUNT={refined.boundary_edge_count}")
    print(f"NONMANIFOLD_EDGE_COUNT={refined.nonmanifold_edge_count}")
    print(f"NONMANIFOLD_VERTEX_COUNT={refined.nonmanifold_vertex_count}")
    print(f"CONNECTED_COMPONENT_COUNT={refined.connected_component_count}")
    print(f"EULER_CHARACTERISTIC={refined.euler_characteristic}")
    print(f"MAX_DISPLACEMENT_MM={refined.max_displacement_mm:.6f}")
    print(f"DISPLACEMENT_LIMIT_MM={refined.displacement_limit_mm:.6f}")
    print("BOUNDS_LPS_MM=" + ",".join(f"{value:.6f}" for value in refined.bounds_lps_mm))
    print(f"ACCURATE_SECONDS={accurate_seconds:.6f}")
    print(f"REFINEMENT_SECONDS={refinement_seconds:.6f}")
    print("GEOMETRY_CHAIN=PATIENT_LPS")
    print("SURFACE_CONTAINMENT=CANONICAL_VOXEL_CELL_BOUNDS")
    print("ACCURATE_REFERENCE=IMMUTABLE")
    print("REPAIRED_TOPOLOGY_BASELINE=PRESERVED")
    print("VERTEX_FAN_MANIFOLDNESS=REQUIRED")
    print("SOURCE_LABEL_MAP=IMMUTABLE")
    print("PHASE6C_PRESENTATION=NOT_ENABLED")
    print("PHASE6G_SURFACE_TO_MASK_DEVIATION=NOT_RUN")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6B_REAL_SURFACE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
