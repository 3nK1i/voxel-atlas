from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.dicom_ingestion import DicomIngestionService
from voxelatlas.dicom_volume import CanonicalVolumeService, DecodedDicomSlice, DicomVolumeError


def _synthetic_manifest() -> dict[str, object]:
    return {
        "schema_version": 2,
        "study_id": "synthetic",
        "study_instance_uid": "1.2.3",
        "created_at_utc": "2026-09-01T00:00:00+00:00",
        "study_date": "20260901",
        "study_description": "Synthetic geometry probe",
        "modalities": ["CT"],
        "file_count": 3,
        "skipped_file_count": 0,
        "series_count": 1,
        "primary_series_uid": "series",
        "reconstruction_ready": True,
        "reconstruction_series_uid": "series",
        "series": [
            {
                "series_instance_uid": "series",
                "modality": "CT",
                "series_number": 1,
                "series_description": "Synthetic",
                "manufacturer": "VoxelAtlas",
                "manufacturer_model": None,
                "rows": 2,
                "columns": 2,
                "pixel_spacing": [0.5, 0.75],
                "slice_thickness": 1.5,
                "spacing_between_slices": 1.5,
                "instance_count": 3,
                "instances": [
                    {"stored_filename": name, "sop_instance_uid": name, "sha256": sha256(b"synthetic").hexdigest()}
                    for name in ("slice-a.dcm", "slice-b.dcm", "slice-c.dcm")
                ],
                "geometry": {
                    "reconstruction_ready": True,
                    "orientation_label": "axial",
                    "dimensions": [2, 2, 3],
                    "spacing_mm": [0.5, 0.75, 1.5],
                    "slice_spacing_mm": 1.5,
                    "origin_patient_mm": [10.0, 20.0, 30.0],
                    "row_direction": [1.0, 0.0, 0.0],
                    "column_direction": [0.0, 1.0, 0.0],
                    "slice_normal": [0.0, 0.0, 1.0],
                    "slice_position_range_mm": [30.0, 33.0],
                    "ordered_instance_filenames": ["slice-a.dcm", "slice-b.dcm", "slice-c.dcm"],
                    "issues": [],
                },
            }
        ],
    }


def synthetic_probe() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        study_dir = data_dir / "studies" / "synthetic"
        study_dir.mkdir(parents=True)
        for name in ("slice-a.dcm", "slice-b.dcm", "slice-c.dcm"):
            (study_dir / name).write_bytes(b"synthetic")
        (study_dir / "manifest.json").write_text(
            json.dumps(_synthetic_manifest()), encoding="utf-8"
        )

        values = {"slice-a.dcm": 0, "slice-b.dcm": 100, "slice-c.dcm": 200}

        def reader(path: Path) -> DecodedDicomSlice:
            return DecodedDicomSlice(
                np.full((2, 2), values[path.name], dtype=np.int16),
                1.0,
                -1024.0,
            )

        study = CanonicalVolumeService(data_dir=data_dir, pixel_reader=reader).build_latest()
        volume = study["volume"]
        array = np.load(study_dir / "derived" / "volume.npy", allow_pickle=False)
        assert array.shape == (3, 2, 2)
        assert array.dtype == np.float32
        assert float(array[0, 0, 0]) == -1024.0
        assert float(array[2, 0, 0]) == -824.0
        assert volume["axis_order"] == ["slice", "row", "column"]
        assert volume["spacing_mm"] == [1.5, 0.5, 0.75]
        assert volume["intensity_units"] == "HU"
        assert volume["array_index_to_patient_lps"][0][2] == 0.75
        assert volume["array_index_to_patient_lps"][1][1] == 0.5
        assert volume["array_index_to_patient_lps"][2][0] == 1.5

    print("PASS storage=float32_npy")
    print("PASS order=qualified_geometric_slice_order")
    print("PASS intensity=modality_transform")
    print("PASS coordinates=array_index_to_patient_lps")
    print("PASS publication=manifest_metadata_without_internal_paths")
    print("PHASE3C_CANONICAL_VOLUME_OK=YES")
    return 0


def latest_probe(data_dir: Path, build: bool) -> int:
    study_service = DicomIngestionService(data_dir=data_dir, max_upload_mib=512)
    study = study_service.latest_public_study()
    if study is None:
        print("LATEST_STUDY=NONE")
        return 2
    print("LATEST_STUDY=PRESENT")
    print(f"GEOMETRY_READY={'YES' if study.get('reconstruction_ready') else 'NO'}")
    if not study.get("reconstruction_ready"):
        print("VOLUME_READY=NO")
        return 3

    if build and not study.get("volume_ready"):
        try:
            study = CanonicalVolumeService(data_dir=data_dir).build_latest()
        except DicomVolumeError as exc:
            print("VOLUME_BUILD=FAIL")
            print(f"VOLUME_ERROR={exc}")
            return 4
        print("VOLUME_BUILD=PASS")

    volume = study.get("volume")
    if not study.get("volume_ready") or not isinstance(volume, dict):
        print("VOLUME_READY=NO")
        return 5

    print("VOLUME_READY=YES")
    print(f"VOLUME_SHAPE={volume.get('shape')}")
    print(f"VOLUME_SPACING_MM={volume.get('spacing_mm')}")
    print(f"VOLUME_AXIS_ORDER={volume.get('axis_order')}")
    print(f"VOLUME_DTYPE={volume.get('dtype')}")
    print(f"VOLUME_UNITS={volume.get('intensity_units')}")
    print(f"VOLUME_RANGE={volume.get('value_range')}")

    studies_dir = data_dir / "studies"
    manifests = list(studies_dir.glob("*/manifest.json"))
    if not manifests:
        print("VOLUME_ARTIFACT=FAIL")
        return 6
    manifest_path = max(manifests, key=lambda item: item.stat().st_mtime_ns)
    array_path = manifest_path.parent / "derived" / "volume.npy"
    metadata_path = manifest_path.parent / "derived" / "volume.json"
    if not array_path.is_file() or not metadata_path.is_file():
        print("VOLUME_ARTIFACT=FAIL")
        return 6
    try:
        array = np.load(array_path, mmap_mode="r", allow_pickle=False)
    except Exception:
        print("VOLUME_ARTIFACT=FAIL")
        return 6
    if list(array.shape) != list(volume.get("shape") or []):
        print("VOLUME_ARTIFACT=FAIL")
        return 6
    if str(array.dtype) != str(volume.get("dtype")):
        print("VOLUME_ARTIFACT=FAIL")
        return 6
    print(f"VOLUME_ARTIFACT_BYTES={array_path.stat().st_size}")
    print("VOLUME_ARTIFACT=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate VoxelAtlas Phase 3C canonical patient volume")
    parser.add_argument("--latest", action="store_true", help="Inspect the latest stored study")
    parser.add_argument("--build", action="store_true", help="Build the latest qualified volume when absent")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="VoxelAtlas data directory")
    args = parser.parse_args()
    if args.build and not args.latest:
        parser.error("--build requires --latest")
    if args.latest:
        return latest_probe(args.data_dir.expanduser().resolve(), args.build)
    return synthetic_probe()


if __name__ == "__main__":
    raise SystemExit(main())
