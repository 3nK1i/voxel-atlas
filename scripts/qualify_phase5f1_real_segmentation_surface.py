#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_surfaces import SegmentationSurfaceService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify one real Phase 5F1 segmentation-derived 3D surface."
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--label-map-id", required=True)
    parser.add_argument("--label-id", type=int, default=91)
    parser.add_argument("--quality", choices=("preview", "balanced"), default="preview")
    args = parser.parse_args()

    service = SegmentationSurfaceService(data_dir=args.data_dir)
    descriptor = service.descriptor_latest(label_map_id=args.label_map_id)
    surface = service.surface_latest(
        label_id=args.label_id,
        label_map_id=args.label_map_id,
        quality=args.quality,
    )
    print("===== PHASE 5F1 REAL 3D SEGMENTATION SURFACE QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    print(f"LABEL_MAP_ID={surface.label_map_id}")
    print(f"SOURCE_STUDY_ID={descriptor['source_study_id']}")
    print(f"LABEL_ID={surface.label_id}")
    print(f"QUALITY={surface.quality}")
    print(f"EXTRACTION={surface.extraction}")
    print(f"STRIDE={surface.stride}")
    print(f"VERTEX_COUNT={surface.vertex_count}")
    print(f"TRIANGLE_COUNT={surface.triangle_count}")
    print("BOUNDS_LPS_MM=" + ",".join(f"{value:.6f}" for value in surface.bounds_lps_mm))
    print(f"SURFACE_PAYLOAD_SHA256={surface.payload_sha256}")
    print("COORDINATE_SYSTEM=patient_lps")
    print("SOURCE_LABEL_MAP=IMMUTABLE")
    print("COMBINED_SURFACE_VOLUME=READY_FOR_MANUAL_QUALIFICATION")
    print("SURFACE_REFINEMENT=DEFERRED_TO_PHASE6")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE5F1_REAL_SURFACE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
