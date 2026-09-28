#!/usr/bin/env python3
from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    worker6a = load_module("phase6a_surface_worker_d4_probe", ROOT / "scripts" / "phase6a_surface_worker.py")
    worker6b = load_module("phase6b_surface_worker_d4_probe", ROOT / "scripts" / "phase6b_surface_worker.py")

    runtime6a = worker6a.runtime_identity()
    runtime6b = worker6b.runtime_identity()
    if runtime6a != runtime6b:
        raise RuntimeError("surface runtime identity differs between accurate and refined workers")

    shape = (32, 32, 32)
    z, y, x = np.indices(shape, dtype=np.float64)
    center = np.asarray(shape, dtype=np.float64) / 2.0
    mask = (
        ((z - center[0]) / 9.5) ** 2
        + ((y - center[1]) / 11.0) ** 2
        + ((x - center[2]) / 10.0) ** 2
        <= 1.0
    )
    labels = np.zeros(shape, dtype=np.uint16)
    labels[mask] = 50
    indices = np.argwhere(mask)
    minimum = indices.min(axis=0)
    maximum = indices.max(axis=0)
    affine = np.asarray(
        [
            [1.50, 0.00, 0.00, 10.0],
            [0.00, 0.82, 0.00, 20.0],
            [0.00, 0.00, 0.82, 30.0],
            [0.00, 0.00, 0.00, 1.0],
        ],
        dtype=np.float64,
    )

    with tempfile.TemporaryDirectory(prefix="voxelatlas-d4-runtime-") as tmp:
        stage = Path(tmp)
        label_map = stage / "labels.npy"
        accurate_surface = stage / "accurate.vxsf2"
        refined_surface = stage / "refined.vxsf2"
        np.save(label_map, labels, allow_pickle=False)
        label_sha = sha256(label_map.read_bytes()).hexdigest()

        accurate_request = {
            "schema_version": 2,
            "operation": "extract_accurate_surface",
            "label_id": 50,
            "expected_label_map_sha256": label_sha,
            "shape": list(shape),
            "minimum_index": [int(v) for v in minimum],
            "maximum_index": [int(v) for v in maximum],
            "voxel_count": int(mask.sum()),
            "array_index_to_patient_lps": affine.tolist(),
            "extraction": "marching_cubes_half_voxel",
            "expected_runtime_fingerprint_sha256": runtime6a["runtime_fingerprint_sha256"],
            "max_vertices": 1_500_000,
            "max_triangles": 2_500_000,
            "max_payload_bytes": 96 * 1024 * 1024,
            "source_label_map": "immutable",
            "clinical_validation": "not_claimed",
        }
        accurate_report = worker6a.extract_surface(
            label_map=label_map,
            request=accurate_request,
            output=accurate_surface,
        )

        reference_sha = sha256(accurate_surface.read_bytes()).hexdigest()
        refined_request = {
            "schema_version": 2,
            "operation": "refine_accurate_surface",
            "refinement": worker6b.REFINEMENT,
            "refinement_algorithm_version": worker6b.REFINEMENT_ALGORITHM_VERSION,
            "label_id": 50,
            "reference_surface_id": "surf-" + "8" * 32,
            "reference_surface_sha256": reference_sha,
            "array_index_to_patient_lps": affine.tolist(),
            "shape": list(shape),
            "expected_runtime_fingerprint_sha256": runtime6b["runtime_fingerprint_sha256"],
            "max_vertices": 1_500_000,
            "max_triangles": 2_500_000,
            "max_payload_bytes": 96 * 1024 * 1024,
            "policy": worker6b.mri_total_mr_policy(),
            "label_map_npy": str(label_map.resolve(strict=True)),
            "expected_label_map_sha256": label_sha,
            "source_label_map": "immutable",
            "clinical_validation": "not_claimed",
        }
        refined_report = worker6b.refine_surface(
            reference_surface=accurate_surface,
            request=refined_request,
            output=refined_surface,
        )

        if refined_report.get("refinement_profile") != worker6b.MRI_TOTAL_MR_PROFILE:
            raise RuntimeError("MRI presentation profile was not used")
        if refined_report.get("presentation_reconstruction") != worker6b.MRI_TOTAL_MR_PRESENTATION_RECONSTRUCTION:
            raise RuntimeError("MRI presentation reconstruction identity is wrong")
        if refined_report.get("presentation_reconstruction_applied") is not True:
            raise RuntimeError("MRI presentation reconstruction was not applied")
        if float(refined_report.get("displacement_limit_mm", -1.0)) != worker6b.MRI_TOTAL_MR_MAX_DISPLACEMENT_MM:
            raise RuntimeError("MRI presentation displacement bound is wrong")
        if float(refined_report.get("max_displacement_mm", 1e9)) > worker6b.MRI_TOTAL_MR_MAX_DISPLACEMENT_MM + 1e-9:
            raise RuntimeError("MRI presentation reconstruction exceeded its bound")
        if refined_report.get("source_label_map") != "immutable":
            raise RuntimeError("MRI presentation reconstruction did not preserve label-map provenance")
        if refined_report.get("clinical_validation") != "not_claimed":
            raise RuntimeError("MRI presentation reconstruction made an unsupported clinical claim")
        if not refined_surface.is_file() or refined_surface.stat().st_size <= 0:
            raise RuntimeError("MRI presentation runtime did not produce a surface")
        if accurate_report["payload_sha256"] != reference_sha:
            raise RuntimeError("accurate reference surface identity changed")

    print("PHASE6J_D4_MRI_PRESENTATION_RUNTIME=PASS")
    print("MRI_PRESENTATION_RECONSTRUCTION=GAUSSIAN_LABEL_MAP_ISOSURFACE")
    print("MRI_PRESENTATION_RECONSTRUCTION_APPLIED=PASS")
    print("MRI_PRESENTATION_MAX_DISPLACEMENT_MM=3.0")
    print("MRI_REFERENCE_SURFACE=UNCHANGED")
    print("MRI_INFERENCE=NOT_RUN")
    print("PRODUCTION_MRI_IMPORT=NOT_RUN")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
