from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.dicom_geometry import GeometryInstance, qualify_series_geometry
from voxelatlas.dicom_ingestion import DicomIngestionService


def synthetic_probe() -> int:
    result = qualify_series_geometry(
        [
            GeometryInstance(
                stored_filename="slice-c.dcm",
                rows=512,
                columns=512,
                pixel_spacing=(0.5, 0.5),
                image_position_patient=(0.0, 0.0, 2.0),
                image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
                instance_number=1,
                number_of_frames=1,
            ),
            GeometryInstance(
                stored_filename="slice-a.dcm",
                rows=512,
                columns=512,
                pixel_spacing=(0.5, 0.5),
                image_position_patient=(0.0, 0.0, 0.0),
                image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
                instance_number=99,
                number_of_frames=1,
            ),
            GeometryInstance(
                stored_filename="slice-b.dcm",
                rows=512,
                columns=512,
                pixel_spacing=(0.5, 0.5),
                image_position_patient=(0.0, 0.0, 1.0),
                image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
                instance_number=50,
                number_of_frames=1,
            ),
        ]
    )
    assert result.reconstruction_ready
    assert result.ordered_instance_filenames == (
        "slice-a.dcm",
        "slice-b.dcm",
        "slice-c.dcm",
    )
    assert result.orientation_label == "axial"
    assert result.dimensions == (512, 512, 3)
    assert result.spacing_mm == (0.5, 0.5, 1.0)
    print("PASS ordering=ImagePositionPatient_projection")
    print("PASS orientation=direction_cosine_cross_product")
    print("PASS spacing=geometric_regular_stack")
    print("PASS readiness=canonical_volume_geometry")
    print("PHASE3B_DICOM_GEOMETRY_OK=YES")
    return 0


def latest_probe(data_dir: Path) -> int:
    service = DicomIngestionService(data_dir=data_dir, max_upload_mib=512)
    study = service.latest_public_study()
    if study is None:
        print("LATEST_STUDY=NONE")
        return 2

    series_list = study.get("series", [])
    ready_series = [
        item
        for item in series_list
        if isinstance(item, dict)
        and isinstance(item.get("geometry"), dict)
        and item["geometry"].get("reconstruction_ready") is True
    ]
    print("LATEST_STUDY=PRESENT")
    print(f"SERIES_COUNT={study.get('series_count', 0)}")
    print(f"RECONSTRUCTION_READY={'YES' if study.get('reconstruction_ready') else 'NO'}")
    print(f"READY_SERIES_COUNT={len(ready_series)}")
    for index, series in enumerate(series_list, start=1):
        if not isinstance(series, dict):
            continue
        geometry = series.get("geometry")
        if not isinstance(geometry, dict):
            print(f"SERIES_{index}=geometry_unavailable")
            continue
        dimensions = geometry.get("dimensions")
        spacing = geometry.get("spacing_mm")
        issues = geometry.get("issues") if isinstance(geometry.get("issues"), list) else []
        issue_codes = [
            str(item.get("code"))
            for item in issues
            if isinstance(item, dict) and item.get("code")
        ]
        print(
            f"SERIES_{index}="
            f"{'ready' if geometry.get('reconstruction_ready') else 'review'} "
            f"{geometry.get('orientation_label') or 'unknown'} "
            f"dimensions={dimensions or '-'} spacing_mm={spacing or '-'} "
            f"issues={','.join(issue_codes) if issue_codes else '-'}"
        )
    return 0 if study.get("reconstruction_ready") else 3


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate VoxelAtlas Phase 3B DICOM geometry")
    parser.add_argument("--latest", action="store_true", help="Inspect the latest stored study")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="VoxelAtlas data directory")
    args = parser.parse_args()
    if args.latest:
        return latest_probe(args.data_dir.expanduser().resolve())
    return synthetic_probe()


if __name__ == "__main__":
    raise SystemExit(main())
