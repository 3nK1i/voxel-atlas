#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_surface_runtime import SegmentationSurfaceRuntimeQualifier
from voxelatlas.volume_surfaces import (
    DEFAULT_MR_NORMALIZED_ISOVALUE,
    MRI_NORMALIZATION_HIGH_PERCENTILE,
    MRI_NORMALIZATION_LOW_PERCENTILE,
    MRI_NORMALIZATION_PROFILE,
    MRI_PRESENTATION_GAUSSIAN_SIGMA_MM,
    MRI_SURFACE_INTENSITY_UNITS,
)

HEADER = struct.Struct("<4s7I")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe D4.5B Direct MR surface extraction in the isolated surface runtime")
    parser.add_argument("--python", required=True)
    args = parser.parse_args()

    runtime = SegmentationSurfaceRuntimeQualifier().qualify(args.python)
    if not runtime.qualified or not runtime.runtime_fingerprint_sha256:
        print("PHASE6J_D45B_SURFACE_RUNTIME=FAIL")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        volume_path = root / "volume.npy"
        request_path = root / "request.json"
        output_path = root / "surface.vxvs"

        shape = (40, 56, 64)
        zz, yy, xx = np.indices(shape, dtype=np.float32)
        center = np.asarray([(shape[0] - 1) / 2, (shape[1] - 1) / 2, (shape[2] - 1) / 2], dtype=np.float32)
        radius = ((zz - center[0]) / 15.0) ** 2 + ((yy - center[1]) / 20.0) ** 2 + ((xx - center[2]) / 24.0) ** 2
        volume = np.zeros(shape, dtype=np.float32)
        volume[radius <= 1.0] = 700.0
        volume[radius <= 0.70] = 950.0
        volume[radius <= 0.45] = 1200.0
        np.save(volume_path, volume, allow_pickle=False)
        before = digest(volume_path)

        request = {
            "schema_version": 1,
            "operation": "extract_volume_isosurface",
            "extraction": "marching_cubes_isovalue",
            "source_type": "canonical_volume",
            "source_volume": "immutable",
            "source_modality": "MR",
            "source_intensity_units": "modality",
            "surface_intensity_units": MRI_SURFACE_INTENSITY_UNITS,
            "source_value_range": [0.0, 1200.0],
            "source_descriptor_sha256": "1" * 64,
            "expected_volume_sha256": before,
            "shape": list(shape),
            "array_index_to_patient_lps": [
                [0.0, 0.0, 0.82, 10.0],
                [0.0, 0.82, 0.0, 20.0],
                [1.5, 0.0, 0.0, 30.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "isovalue": DEFAULT_MR_NORMALIZED_ISOVALUE,
            "normalization": {
                "profile": MRI_NORMALIZATION_PROFILE,
                "low_percentile": MRI_NORMALIZATION_LOW_PERCENTILE,
                "high_percentile": MRI_NORMALIZATION_HIGH_PERCENTILE,
                "clip_to_unit_interval": True,
                "gaussian_sigma_mm": MRI_PRESENTATION_GAUSSIAN_SIGMA_MM,
            },
            "coordinate_system": "patient_lps",
            "expected_runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
            "max_vertices": 2_000_000,
            "max_triangles": 4_000_000,
            "max_payload_bytes": 160 * 1024 * 1024,
            "clinical_validation": "not_claimed",
        }
        request_path.write_text(json.dumps(request, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        completed = subprocess.run(
            [
                args.python,
                "-I",
                str(ROOT / "scripts" / "phase6d1_volume_surface_worker.py"),
                "--volume-npy",
                str(volume_path),
                "--request-json",
                str(request_path),
                "--output-surface",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr)
            return 1
        report = json.loads([line for line in completed.stdout.splitlines() if line.strip()][-1])
        if not output_path.is_file() or output_path.is_symlink():
            return 1
        payload = output_path.read_bytes()
        magic, version, vertices, indices, _, _, _, flags = HEADER.unpack_from(payload)
        normalization = report.get("normalization")
        if (
            magic != b"VXVS"
            or version != 1
            or flags != 1
            or vertices <= 0
            or indices <= 0
            or indices % 3 != 0
            or digest(volume_path) != before
            or report.get("intensity_units") != MRI_SURFACE_INTENSITY_UNITS
            or report.get("isovalue") != DEFAULT_MR_NORMALIZED_ISOVALUE
            or not isinstance(normalization, dict)
            or normalization.get("profile") != MRI_NORMALIZATION_PROFILE
            or normalization.get("low_percentile") != MRI_NORMALIZATION_LOW_PERCENTILE
            or normalization.get("high_percentile") != MRI_NORMALIZATION_HIGH_PERCENTILE
            or normalization.get("gaussian_sigma_mm") != MRI_PRESENTATION_GAUSSIAN_SIGMA_MM
            or not float(normalization.get("low_value")) < float(normalization.get("high_value"))
            or report.get("coordinate_system") != "patient_lps"
            or report.get("source_volume") != "immutable"
            or report.get("clinical_validation") != "not_claimed"
        ):
            return 1

        print(f"VERTEX_COUNT={vertices}")
        print(f"TRIANGLE_COUNT={indices // 3}")
        print("PHASE6J_D45B_DIRECT_MR_RUNTIME=PASS")
        print("DIRECT_MR_SEGMENTATION_REQUIRED=NO")
        print("DIRECT_MR_SIGNAL_BASIS=NORMALIZED")
        print(f"DIRECT_MR_NORMALIZATION_PROFILE={MRI_NORMALIZATION_PROFILE}")
        print(f"DIRECT_MR_GAUSSIAN_SIGMA_MM={MRI_PRESENTATION_GAUSSIAN_SIGMA_MM}")
        print("DIRECT_MR_PATIENT_LPS=PASS")
        print("SOURCE_VOLUME=IMMUTABLE")
        print("MRI_INFERENCE=NOT_RUN")
        print("CLINICAL_VALIDATION=NOT_CLAIMED")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
