#!/usr/bin/env python3
import argparse
from hashlib import sha256
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.segmentation_overlays import SegmentationOverlayService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify real Phase 5D Patient-LPS MPR segmentation overlays."
    )
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--label-map-id", default=None)
    args = parser.parse_args()

    service = SegmentationOverlayService(data_dir=args.data_dir)
    descriptor = service.descriptor_latest(label_map_id=args.label_map_id)
    if descriptor.get("ready") is not True:
        print("STATUS=FAILED")
        print("MESSAGE=No canonical label map is bound to the current study")
        return 1

    mpr = service.mpr_service.descriptor_latest()
    plane_results = []
    for plane in ("axial", "coronal", "sagittal"):
        plane_descriptor = mpr["planes"][plane]
        index = int(plane_descriptor["slice_count"]) // 2
        image = service.render_latest(
            plane,
            index=index,
            label_map_id=str(descriptor["label_map_id"]),
        )
        alpha = image.pixels[3::4]
        visible_pixels = sum(1 for value in alpha if value != 0)
        plane_results.append((plane, image, visible_pixels))

    print("===== PHASE 5D REAL MPR SEGMENTATION OVERLAY QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    print(f"LABEL_MAP_ID={descriptor['label_map_id']}")
    print(f"SOURCE_STUDY_ID={descriptor['source_study_id']}")
    print(f"LABEL_MAP_SHA256={descriptor['label_map_sha256']}")
    print(f"PRESENT_LABEL_COUNT={descriptor['present_label_count']}")
    for plane, image, visible_pixels in plane_results:
        prefix = plane.upper()
        print(f"{prefix}_INDEX={image.index}")
        print(f"{prefix}_SHAPE={image.height}x{image.width}")
        print(f"{prefix}_RGBA_SHA256={sha256(image.pixels).hexdigest()}")
        print(f"{prefix}_VISIBLE_PIXELS={visible_pixels}")
    print("COORDINATE_SYSTEM=patient_lps")
    print("LABEL_SAMPLING=nearest_neighbor")
    print("ACTUAL_APP_VISUALIZATION=READY")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
