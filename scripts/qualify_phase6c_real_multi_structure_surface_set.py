#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
from time import perf_counter
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_surfaces import (  # noqa: E402
    REFINED_SURFACE_QUALITY,
    REFINED_SURFACE_REFINEMENT,
    SegmentationSurfaceService,
)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify a small real-study set of refined surfaces for Phase 6C presentation."
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--label-map-id", required=True)
    parser.add_argument("--labels", type=int, nargs="+", required=True)
    parser.add_argument("--python", required=True, dest="worker_python")
    args = parser.parse_args()

    labels = list(dict.fromkeys(args.labels))
    if len(labels) < 2 or any(label <= 0 for label in labels):
        raise SystemExit("Phase 6C real surface-set qualification requires at least two positive labels")

    service = SegmentationSurfaceService(
        data_dir=args.data_dir,
        worker_python=args.worker_python,
    )
    descriptor = service.descriptor_latest(label_map_id=args.label_map_id)
    present = set(descriptor.get("present_labels") or [])
    missing = [label for label in labels if label not in present]
    if descriptor.get("ready") is not True or missing:
        raise SystemExit(f"Requested labels are not available for this canonical label map: {missing}")

    artifact = args.data_dir / "segmentation" / "label-maps" / args.label_map_id / "labels.npy"
    before_sha = file_sha256(artifact)
    started = perf_counter()
    surfaces = []
    print("===== PHASE 6C REAL MULTI-STRUCTURE SURFACE SET QUALIFICATION =====")
    print("STATUS=RUNNING")
    print(f"LABEL_MAP_ID={args.label_map_id}")
    print(f"SOURCE_STUDY_ID={descriptor.get('source_study_id')}")
    print("REQUESTED_LABELS=" + ",".join(str(label) for label in labels))

    for label in labels:
        item_started = perf_counter()
        surface = service.surface_latest(
            label_id=label,
            label_map_id=args.label_map_id,
            quality=REFINED_SURFACE_QUALITY,
        )
        if (
            surface.quality != REFINED_SURFACE_QUALITY
            or surface.refinement != REFINED_SURFACE_REFINEMENT
            or surface.coordinate_system != "patient_lps"
            or surface.schema_version != 2
            or surface.vertex_count <= 0
            or surface.triangle_count <= 0
            or surface.normal_count != surface.vertex_count
            or not surface.reference_surface_id
            or not surface.reference_payload_sha256
            or surface.boundary_edge_count != 0
            or surface.nonmanifold_edge_count != 0
            or surface.nonmanifold_vertex_count != 0
            or surface.max_displacement_mm > surface.displacement_limit_mm + 1e-6
        ):
            raise SystemExit(f"Refined surface contract failed for label {label}")
        elapsed = perf_counter() - item_started
        surfaces.append(surface)
        prefix = f"LABEL_{label}"
        print(f"{prefix}_SURFACE_ID={surface.surface_id}")
        print(f"{prefix}_PAYLOAD_SHA256={surface.payload_sha256}")
        print(f"{prefix}_VERTEX_COUNT={surface.vertex_count}")
        print(f"{prefix}_TRIANGLE_COUNT={surface.triangle_count}")
        print(f"{prefix}_BOUNDARY_EDGE_COUNT={surface.boundary_edge_count}")
        print(f"{prefix}_NONMANIFOLD_EDGE_COUNT={surface.nonmanifold_edge_count}")
        print(f"{prefix}_NONMANIFOLD_VERTEX_COUNT={surface.nonmanifold_vertex_count}")
        print(f"{prefix}_MAX_DISPLACEMENT_MM={surface.max_displacement_mm:.6f}")
        print(f"{prefix}_SECONDS={elapsed:.6f}")

    after_sha = file_sha256(artifact)
    if before_sha != after_sha:
        raise SystemExit("Canonical source label map changed during Phase 6C qualification")

    total_triangles = sum(surface.triangle_count for surface in surfaces)
    print(f"MULTI_STRUCTURE_COUNT={len(surfaces)}")
    print(f"TOTAL_REFINED_TRIANGLES={total_triangles}")
    print(f"TOTAL_SECONDS={perf_counter() - started:.6f}")
    print("GEOMETRY_CHAIN=PATIENT_LPS")
    print("SOURCE_LABEL_MAP=IMMUTABLE")
    print("PHASE6A_ACCURATE_REFERENCE=IMMUTABLE")
    print("PHASE6B_REFINED_GEOMETRY=PRESERVED")
    print("PHASE6D_WORKFLOW=NOT_ENABLED")
    print("PHASE6F_ADVANCED_MULTI_ISOLATION=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("STATUS=QUALIFIED")
    print("PHASE6C_REAL_SURFACE_SET_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
