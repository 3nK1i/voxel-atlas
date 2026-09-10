#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import json
from math import isfinite
import os
from pathlib import Path
import platform
import struct
import sys

SCHEMA_VERSION = 1
MAGIC = b"VXVS"
HEADER = struct.Struct("<4s7I")
FLAGS = 1
EXTRACTION = "marching_cubes_isovalue"
DEGENERATE_DOUBLE_AREA_EPSILON = 1e-12
MAX_DEGENERATE_TRIANGLE_FRACTION = 1e-4

KNOWN_ERROR_CODES = {
    "volume surface request contract is invalid": "request_contract_invalid",
    "volume shape is invalid": "volume_shape_invalid",
    "Patient LPS affine is invalid": "patient_lps_affine_invalid",
    "source value range is invalid": "source_value_range_invalid",
    "volume surface isovalue is invalid": "isovalue_invalid",
    "surface runtime changed after qualification": "runtime_changed",
    "canonical patient volume changed": "source_volume_changed",
    "canonical patient volume contract changed": "source_volume_contract_changed",
    "canonical patient volume has no extractable surface at this isovalue": "no_extractable_surface",
    "volume surface exceeds geometry budget": "geometry_budget_exceeded",
    "volume surface orientation reference is invalid": "orientation_reference_invalid",
    "volume surface cleanup input is invalid": "cleanup_input_invalid",
    "volume surface degenerate-face cleanup exceeds safety bound": "degenerate_face_budget_exceeded",
    "surface cleanup left degenerate triangles": "cleanup_failed",
    "surface orientation reference is ambiguous": "orientation_ambiguous",
    "surface normals are invalid": "normals_invalid",
    "volume surface exceeds payload budget": "payload_budget_exceeded",
}


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def absolute_regular_file(value: str, field: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"{field} must be an absolute regular file")
    return path.resolve(strict=True)


def absolute_output(value: str, field: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or path.exists():
        raise ValueError(f"{field} must be a new absolute non-symlink path")
    resolved = path.resolve(strict=False)
    if resolved.parent.is_symlink() or not resolved.parent.is_dir():
        raise ValueError(f"{field} parent is unsafe")
    return resolved


def runtime_identity() -> dict[str, str]:
    identity = {
        "schema_version": 1,
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "scikit_image_version": importlib.metadata.version("scikit-image"),
        "marching_cubes_available": True,
    }
    fingerprint = sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return {
        "python_version": identity["python_version"],
        "numpy_version": identity["numpy_version"],
        "scikit_image_version": identity["scikit_image_version"],
        "runtime_fingerprint_sha256": fingerprint,
    }


def load_request(path: Path) -> dict[str, object]:
    request = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(request, dict)
        or request.get("schema_version") != SCHEMA_VERSION
        or request.get("operation") != "extract_volume_isosurface"
        or request.get("extraction") != EXTRACTION
        or request.get("source_type") != "canonical_volume"
        or request.get("source_volume") != "immutable"
        or request.get("source_modality") != "CT"
        or request.get("source_intensity_units") != "HU"
        or request.get("coordinate_system") != "patient_lps"
        or request.get("clinical_validation") != "not_claimed"
    ):
        raise ValueError("volume surface request contract is invalid")
    shape = request.get("shape")
    if (
        not isinstance(shape, list) or len(shape) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in shape)
    ):
        raise ValueError("volume shape is invalid")
    affine = request.get("array_index_to_patient_lps")
    if not isinstance(affine, list) or len(affine) != 4:
        raise ValueError("Patient LPS affine is invalid")
    for row in affine:
        if (
            not isinstance(row, list) or len(row) != 4
            or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not isfinite(float(item)) for item in row)
        ):
            raise ValueError("Patient LPS affine is invalid")
    if [float(item) for item in affine[3]] != [0.0, 0.0, 0.0, 1.0]:
        raise ValueError("Patient LPS affine is invalid")
    value_range = request.get("source_value_range")
    if not isinstance(value_range, list) or len(value_range) != 2:
        raise ValueError("source value range is invalid")
    low, high = (float(value_range[0]), float(value_range[1]))
    level = float(request.get("isovalue"))
    if not all(isfinite(item) for item in (low, high, level)) or not low < level < high:
        raise ValueError("volume surface isovalue is invalid")
    for key in ("expected_volume_sha256", "source_descriptor_sha256", "expected_runtime_fingerprint_sha256"):
        value = request.get(key)
        if (
            not isinstance(value, str) or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"{key} is invalid")
    for key in ("max_vertices", "max_triangles", "max_payload_bytes"):
        value = request.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{key} is invalid")
    return request


def bounded_degenerate_face_cleanup(positions, faces, orientation_reference):
    import numpy as np

    if (
        positions.ndim != 2
        or positions.shape[1] != 3
        or faces.ndim != 2
        or faces.shape[1] != 3
        or orientation_reference.shape != positions.shape
        or len(positions) <= 0
        or len(faces) <= 0
    ):
        raise ValueError("volume surface cleanup input is invalid")
    if not np.all(np.isfinite(positions)) or not np.all(np.isfinite(orientation_reference)):
        raise ValueError("volume surface cleanup input is invalid")
    if np.any(faces < 0) or np.any(faces >= len(positions)):
        raise ValueError("volume surface cleanup input is invalid")

    raw_vertex_count = int(len(positions))
    raw_triangle_count = int(len(faces))
    triangles = positions[faces]
    cross = np.cross(
        triangles[:, 1] - triangles[:, 0],
        triangles[:, 2] - triangles[:, 0],
    )
    if not np.all(np.isfinite(cross)):
        raise ValueError("volume surface cleanup input is invalid")
    double_area = np.linalg.norm(cross, axis=1)
    if not np.all(np.isfinite(double_area)):
        raise ValueError("volume surface cleanup input is invalid")

    degenerate = double_area <= DEGENERATE_DOUBLE_AREA_EPSILON
    degenerate_count = int(np.count_nonzero(degenerate))
    degenerate_fraction = float(degenerate_count / raw_triangle_count)
    if degenerate_fraction > MAX_DEGENERATE_TRIANGLE_FRACTION:
        raise ValueError("volume surface degenerate-face cleanup exceeds safety bound")

    clean_faces = faces[~degenerate] if degenerate_count else faces
    if len(clean_faces) <= 0:
        raise ValueError("volume surface degenerate-face cleanup exceeds safety bound")

    used_mask = np.zeros(raw_vertex_count, dtype=np.bool_)
    used_mask[clean_faces] = True
    used_vertices = np.flatnonzero(used_mask)
    remap = np.full(raw_vertex_count, -1, dtype=np.int64)
    remap[used_vertices] = np.arange(len(used_vertices), dtype=np.int64)
    clean_faces = remap[clean_faces]
    clean_positions = positions[used_vertices]
    clean_orientation = orientation_reference[used_vertices]

    cleanup = {
        "raw_vertex_count": raw_vertex_count,
        "raw_triangle_count": raw_triangle_count,
        "degenerate_triangle_count": degenerate_count,
        "degenerate_triangle_fraction": degenerate_fraction,
        "unreferenced_vertex_count": raw_vertex_count - int(len(used_vertices)),
        "final_vertex_count": int(len(clean_positions)),
        "final_triangle_count": int(len(clean_faces)),
        "double_area_epsilon_mm2": DEGENERATE_DOUBLE_AREA_EPSILON,
        "max_degenerate_triangle_fraction": MAX_DEGENERATE_TRIANGLE_FRACTION,
    }
    return clean_positions, clean_faces, clean_orientation, cleanup


def canonical_vertex_normals(positions, faces, orientation_reference):
    import numpy as np
    triangles = positions[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    if not np.all(np.isfinite(cross)) or np.any(lengths <= DEGENERATE_DOUBLE_AREA_EPSILON):
        raise ValueError("surface cleanup left degenerate triangles")
    reference = orientation_reference[faces].mean(axis=1)
    agreement = np.einsum("ij,ij->i", cross, reference)
    magnitude = float(np.sum(np.abs(agreement), dtype=np.float64))
    score = float(np.sum(agreement, dtype=np.float64))
    if not np.isfinite(magnitude) or not np.isfinite(score) or magnitude <= 1e-12:
        raise ValueError("surface orientation reference is ambiguous")
    if score < 0.0:
        faces = faces[:, [0, 2, 1]]
        cross = -cross
    vertex_normals = np.zeros_like(positions, dtype=np.float64)
    np.add.at(vertex_normals, faces[:, 0], cross)
    np.add.at(vertex_normals, faces[:, 1], cross)
    np.add.at(vertex_normals, faces[:, 2], cross)
    normal_lengths = np.linalg.norm(vertex_normals, axis=1)
    if np.any(normal_lengths <= 1e-12) or not np.all(np.isfinite(normal_lengths)):
        raise ValueError("surface normals are invalid")
    vertex_normals /= normal_lengths[:, None]
    return faces, vertex_normals


def extract_surface(*, volume_path: Path, request: dict[str, object], output: Path) -> dict[str, object]:
    import numpy as np
    from skimage.measure import marching_cubes

    runtime = runtime_identity()
    if runtime["runtime_fingerprint_sha256"] != request["expected_runtime_fingerprint_sha256"]:
        raise ValueError("surface runtime changed after qualification")
    if sha256_file(volume_path) != request["expected_volume_sha256"]:
        raise ValueError("canonical patient volume changed")
    volume = np.load(volume_path, mmap_mode="r", allow_pickle=False)
    expected_shape = tuple(int(item) for item in request["shape"])
    if tuple(volume.shape) != expected_shape or str(volume.dtype) != "float32":
        raise ValueError("canonical patient volume contract changed")
    # scikit-image requires a writable C-contiguous buffer. Keep the canonical
    # memmap immutable and extract from a private worker copy.
    working_volume = np.array(volume, dtype=np.float32, order="C", copy=True)
    level = float(request["isovalue"])
    vertices, faces, skimage_normals, _ = marching_cubes(
        working_volume,
        level=level,
        spacing=(1.0, 1.0, 1.0),
        gradient_direction="descent",
        allow_degenerate=False,
        method="lewiner",
    )
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    skimage_normals = np.asarray(skimage_normals, dtype=np.float64)
    if len(vertices) <= 0 or len(faces) <= 0:
        raise ValueError("canonical patient volume has no extractable surface at this isovalue")
    if len(vertices) > int(request["max_vertices"]) or len(faces) > int(request["max_triangles"]):
        raise ValueError("volume surface exceeds geometry budget")

    affine = np.asarray(request["array_index_to_patient_lps"], dtype=np.float64)
    if (
        affine.shape != (4, 4) or not np.all(np.isfinite(affine))
        or abs(float(np.linalg.det(affine[:3, :3]))) <= 1e-12
    ):
        raise ValueError("Patient LPS affine is invalid")
    linear = affine[:3, :3]
    positions = vertices @ linear.T + affine[:3, 3]
    normal_matrix = np.linalg.inv(linear).T
    orientation_reference = skimage_normals @ normal_matrix.T
    orientation_lengths = np.linalg.norm(orientation_reference, axis=1)
    if np.any(orientation_lengths <= 1e-12) or not np.all(np.isfinite(orientation_lengths)):
        raise ValueError("volume surface orientation reference is invalid")
    orientation_reference /= orientation_lengths[:, None]
    positions, faces, orientation_reference, cleanup = bounded_degenerate_face_cleanup(
        positions, faces, orientation_reference
    )
    faces, normals = canonical_vertex_normals(positions, faces, orientation_reference)

    positions32 = np.ascontiguousarray(positions, dtype="<f4")
    normals32 = np.ascontiguousarray(normals, dtype="<f4")
    indices32 = np.ascontiguousarray(faces.reshape(-1), dtype="<u4")
    bounds = tuple(float(item) for item in np.concatenate((positions32.min(axis=0), positions32.max(axis=0))))
    pos = positions32.tobytes(order="C")
    norm = normals32.tobytes(order="C")
    ind = indices32.tobytes(order="C")
    payload = HEADER.pack(MAGIC, SCHEMA_VERSION, len(positions32), len(indices32), len(pos), len(norm), len(ind), FLAGS) + pos + norm + ind
    if len(payload) > int(request["max_payload_bytes"]):
        raise ValueError("volume surface exceeds payload budget")
    with output.open("xb") as handle:
        os.chmod(output, 0o600)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "extract_volume_isosurface",
        "extraction": EXTRACTION,
        "isovalue": level,
        "intensity_units": "HU",
        "vertex_count": len(positions32),
        "triangle_count": len(faces),
        "raw_vertex_count": cleanup["raw_vertex_count"],
        "raw_triangle_count": cleanup["raw_triangle_count"],
        "degenerate_triangle_count": cleanup["degenerate_triangle_count"],
        "degenerate_triangle_fraction": cleanup["degenerate_triangle_fraction"],
        "unreferenced_vertex_count": cleanup["unreferenced_vertex_count"],
        "degenerate_double_area_epsilon_mm2": cleanup["double_area_epsilon_mm2"],
        "max_degenerate_triangle_fraction": cleanup["max_degenerate_triangle_fraction"],
        "payload_bytes": len(payload),
        "payload_sha256": sha256(payload).hexdigest(),
        "bounds_lps_mm": list(bounds),
        "coordinate_system": "patient_lps",
        "runtime_fingerprint_sha256": runtime["runtime_fingerprint_sha256"],
        "python_version": runtime["python_version"],
        "numpy_version": runtime["numpy_version"],
        "scikit_image_version": runtime["scikit_image_version"],
        "source_volume": "immutable",
        "clinical_validation": "not_claimed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a Phase 6D1 Patient-LPS surface directly from a canonical CT volume")
    parser.add_argument("--volume-npy", required=True)
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--output-surface", required=True)
    args = parser.parse_args()
    try:
        volume_path = absolute_regular_file(args.volume_npy, "volume NPY")
        request_path = absolute_regular_file(args.request_json, "request JSON")
        output = absolute_output(args.output_surface, "surface output")
        report = extract_surface(volume_path=volume_path, request=load_request(request_path), output=output)
    except Exception as exc:
        error_code = KNOWN_ERROR_CODES.get(str(exc), "worker_execution_failed")
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_code": error_code,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
