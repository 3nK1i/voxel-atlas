#!/usr/bin/env python3
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.volume_rendering import VolumeRenderingService  # noqa: E402


def write_probe_volume(root: Path) -> tuple[Path, np.ndarray]:
    study_dir = root / "studies" / "probe"
    derived = study_dir / "derived"
    derived.mkdir(parents=True)
    volume = np.linspace(-1024.0, 1594.0, 24, dtype=np.float32).reshape(2, 3, 4)
    np.save(derived / "volume.npy", volume, allow_pickle=False)
    descriptor = {
        "schema_version": 1,
        "ready": True,
        "created_at_utc": "2026-09-02T00:00:00+00:00",
        "source_series_uid": "phase4b-probe-series",
        "source_instance_count": 2,
        "modality": "CT",
        "dtype": "float32",
        "shape": [2, 3, 4],
        "axis_order": ["slice", "row", "column"],
        "spacing_mm": [2.0, 0.5, 0.75],
        "origin_patient_lps_mm": [10.0, 20.0, 30.0],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 0.75, 10.0],
            [0.0, 0.5, 0.0, 20.0],
            [2.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "intensity_units": "HU",
        "value_range": [float(volume.min()), float(volume.max())],
        "artifact_path": "derived/volume.npy",
        "metadata_path": "derived/volume.json",
    }
    (derived / "volume.json").write_text(
        json.dumps(descriptor, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (study_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "study_id": "probe",
                "study_instance_uid": "1.2.3",
                "volume": descriptor,
                "series": [],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return study_dir, volume


def main() -> int:
    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            study_dir, volume = write_probe_volume(Path(tmp))
            canonical_path = study_dir / "derived" / "volume.npy"
            metadata_path = study_dir / "derived" / "volume.json"
            canonical_before = sha256(canonical_path.read_bytes()).hexdigest()
            metadata_before = sha256(metadata_path.read_bytes()).hexdigest()
            service = VolumeRenderingService(data_dir=Path(tmp))
            descriptor = service.prepare_latest()
            artifact_path, _ = service.artifact_latest(str(descriptor["revision"]))
            packed = np.frombuffer(artifact_path.read_bytes(), dtype=np.uint8).reshape(-1, 2)
            quantized = packed[:, 0].astype(np.uint16) + (
                packed[:, 1].astype(np.uint16) << np.uint16(8)
            )
            decoded = (
                float(descriptor["decode_offset"])
                + float(descriptor["decode_scale"]) * quantized.astype(np.float64)
            ).reshape(volume.shape)
            maximum_error = float(np.max(np.abs(decoded - volume)))
            if canonical_before != sha256(canonical_path.read_bytes()).hexdigest():
                failures.append("canonical source changed")
            if metadata_before != sha256(metadata_path.read_bytes()).hexdigest():
                failures.append("canonical metadata changed")
            if descriptor.get("texture_dimensions") != [4, 3, 2]:
                failures.append("texture dimensions")
            if descriptor.get("encoding") != "linear_uint16_rg8":
                failures.append("encoding")
            if maximum_error > float(descriptor["decode_scale"]) / 2.0 + 1e-6:
                failures.append("quantization error")
            if "artifact_path" in descriptor or "metadata_path" in descriptor:
                failures.append("private path exposure")
    except Exception as exc:
        failures.append(f"runtime probe: {type(exc).__name__}: {exc}")

    app_source = (ROOT / "backend" / "voxelatlas" / "app.py").read_text(encoding="utf-8")
    capability_source = (
        ROOT / "web" / "js" / "volume-rendering-capabilities.js"
    ).read_text(encoding="utf-8")
    required_app_markers = (
        '"/api/studies/latest/volume-rendering"',
        '"/api/studies/latest/volume-rendering/data"',
        '"Cache-Control": "no-store"',
        '"X-Content-Type-Options": "nosniff"',
    )
    if any(marker not in app_source for marker in required_app_markers):
        failures.append("authenticated binary HTTP contract")
    if "MAX_3D_TEXTURE_SIZE" not in capability_source:
        failures.append("WebGL2 3D texture capability contract")

    if failures:
        print("PHASE4B_DIRECT_VOLUME_RENDERING=FAIL")
        for failure in failures:
            print(f"FAILED={failure}")
        return 1
    print("PHASE4B_DIRECT_VOLUME_RENDERING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
