#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.dicom_mpr import CanonicalMprService  # noqa: E402
from voxelatlas.config import load_settings  # noqa: E402


def _write_probe(root: Path) -> None:
    study_dir = root / "studies" / "probe"
    derived = study_dir / "derived"
    derived.mkdir(parents=True)
    volume = np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5)
    np.save(derived / "volume.npy", volume, allow_pickle=False)
    descriptor = {
        "schema_version": 1,
        "ready": True,
        "created_at_utc": "2026-09-01T00:00:00+00:00",
        "source_series_uid": "probe-series",
        "source_instance_count": 3,
        "modality": "CT",
        "dtype": "float32",
        "shape": [3, 4, 5],
        "axis_order": ["slice", "row", "column"],
        "spacing_mm": [2.0, 1.0, 0.5],
        "origin_patient_lps_mm": [0.0, 0.0, 0.0],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 0.5, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "intensity_units": "HU",
        "value_range": [0.0, float(volume.max())],
        "artifact_path": "derived/volume.npy",
        "metadata_path": "derived/volume.json",
    }
    (derived / "volume.json").write_text(json.dumps(descriptor), encoding="utf-8")
    (study_dir / "manifest.json").write_text(
        json.dumps({"schema_version": 3, "study_id": "probe", "volume": descriptor}),
        encoding="utf-8",
    )


def _report(service: CanonicalMprService, *, prefix: str) -> int:
    descriptor = service.descriptor_latest()
    print(f"{prefix}_MPR_READY={'YES' if descriptor.get('ready') else 'NO'}")
    print(f"{prefix}_MPR_UNITS={descriptor.get('intensity_units')}")
    window = descriptor.get("default_window", {})
    print(f"{prefix}_MPR_WINDOW=[{window.get('width')}, {window.get('level')}]")
    for plane in ("axial", "coronal", "sagittal"):
        info = descriptor["planes"][plane]
        index = int(info["slice_count"]) // 2
        image = service.render_latest(
            plane,
            index=index,
            window=float(window["width"]),
            level=float(window["level"]),
        )
        print(
            f"{prefix}_{plane.upper()}=ready "
            f"slices={info['slice_count']} image={image.width}x{image.height} "
            f"spacing_mm={info['pixel_spacing_mm']} position_mm={image.position_mm:.3f} "
            f"bytes={len(image.pixels)}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 3D patient-space MPR rendering")
    parser.add_argument("--latest", action="store_true", help="Validate the latest stored patient volume")
    args = parser.parse_args()

    if args.latest:
        settings = load_settings()
        try:
            return _report(CanonicalMprService(data_dir=settings.data_dir), prefix="LATEST")
        except Exception as exc:
            print("LATEST_MPR_READY=NO")
            print(f"LATEST_MPR_ERROR={exc}")
            return 3

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_probe(root)
        return _report(CanonicalMprService(data_dir=root), prefix="PROBE")


if __name__ == "__main__":
    raise SystemExit(main())
