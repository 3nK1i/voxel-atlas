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
    ACCURATE_SURFACE_EXTRACTION,
    ACCURATE_SURFACE_MEDIA_TYPE,
    SegmentationSurfaceService,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify one real Phase 6A accurate Patient-LPS segmentation surface."
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--label-map-id", required=True)
    parser.add_argument("--label-id", type=int, default=91)
    parser.add_argument(
        "--python",
        default=os.environ.get("VOXELATLAS_SURFACE_PYTHON"),
        help="Qualified isolated Phase 6A surface Python executable",
    )
    parser.add_argument("--max-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if args.max_seconds <= 0:
        raise SystemExit("--max-seconds must be positive")
    if not args.python:
        raise SystemExit(
            "Phase 6A surface runtime is not configured; pass --python or set VOXELATLAS_SURFACE_PYTHON"
        )

    label_maps = SegmentationLabelMapService(data_dir=args.data_dir)
    descriptor = label_maps.get(args.label_map_id)
    service = SegmentationSurfaceService(
        data_dir=args.data_dir,
        label_map_service=label_maps,
        worker_python=args.python,
    )
    started = perf_counter()
    surface = service.surface_latest(
        label_id=args.label_id,
        label_map_id=args.label_map_id,
        quality="accurate",
    )
    elapsed = perf_counter() - started
    if elapsed > args.max_seconds:
        raise SegmentationValidationError("Phase 6A accurate surface performance budget was exceeded")
    cell_bounds = _canonical_affine_bounds(descriptor, voxel_cells=True)
    for axis in range(3):
        if (
            surface.bounds_lps_mm[axis] < cell_bounds[axis] - 1e-3
            or surface.bounds_lps_mm[axis + 3] > cell_bounds[axis + 3] + 1e-3
        ):
            raise SegmentationValidationError(
                "Phase 6A surface exceeds canonical Patient-LPS voxel-cell bounds"
            )
    if (
        surface.schema_version != 2
        or surface.media_type != ACCURATE_SURFACE_MEDIA_TYPE
        or surface.extraction != ACCURATE_SURFACE_EXTRACTION
        or surface.normal_count != surface.vertex_count
        or not surface.surface_id.startswith("surf-")
        or len(surface.provenance_sha256) != 64
    ):
        raise SegmentationValidationError("Phase 6A accurate surface contract is incomplete")

    print("===== PHASE 6A REAL ACCURATE SEGMENTATION SURFACE QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    print(f"LABEL_MAP_ID={surface.label_map_id}")
    print(f"SOURCE_STUDY_ID={descriptor['source_study_id']}")
    print(f"LABEL_ID={surface.label_id}")
    print(f"SURFACE_ID={surface.surface_id}")
    print(f"SURFACE_SCHEMA_VERSION={surface.schema_version}")
    print(f"EXTRACTION={surface.extraction}")
    print(f"VERTEX_COUNT={surface.vertex_count}")
    print(f"TRIANGLE_COUNT={surface.triangle_count}")
    print(f"NORMAL_COUNT={surface.normal_count}")
    print("BOUNDS_LPS_MM=" + ",".join(f"{value:.6f}" for value in surface.bounds_lps_mm))
    print(f"SURFACE_PAYLOAD_SHA256={surface.payload_sha256}")
    print(f"SURFACE_PROVENANCE_SHA256={surface.provenance_sha256}")
    print(f"SURFACE_SECONDS={elapsed:.6f}")
    print("GEOMETRY_CHAIN=PATIENT_LPS")
    print("SURFACE_CONTAINMENT=CANONICAL_VOXEL_CELL_BOUNDS")
    print("BOUNDARY_SEMANTICS=HALF_VOXEL")
    print("SOURCE_LABEL_MAP=IMMUTABLE")
    print("LEGACY_PHASE5F1_PREVIEW=AVAILABLE")
    print("PHASE6B_REFINEMENT=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6A_REAL_SURFACE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
