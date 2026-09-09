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


SCHEMA_VERSION = 2
MAGIC = b"VXSF"
HEADER = struct.Struct("<4s8I")
FLAGS = 1
EXTRACTION = "marching_cubes_half_voxel"


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


def positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} is invalid")
    return value


def load_request(path: Path) -> dict[str, object]:
    request = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(request, dict)
        or request.get("schema_version") != SCHEMA_VERSION
        or request.get("operation") != "extract_accurate_surface"
        or request.get("extraction") != EXTRACTION
        or request.get("source_label_map") != "immutable"
        or request.get("clinical_validation") != "not_claimed"
    ):
        raise ValueError("surface request contract is invalid")
    label_id = positive_int(request.get("label_id"), "label id")
    del label_id
    digest = request.get("expected_label_map_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("label-map digest is invalid")
    shape = request.get("shape")
    if (
        not isinstance(shape, list)
        or len(shape) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in shape)
    ):
        raise ValueError("label-map shape is invalid")
    for key in ("minimum_index", "maximum_index"):
        value = request.get(key)
        if (
            not isinstance(value, list)
            or len(value) != 3
            or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in value)
        ):
            raise ValueError(f"{key} is invalid")
    affine = request.get("array_index_to_patient_lps")
    if not isinstance(affine, list) or len(affine) != 4:
        raise ValueError("Patient LPS affine is invalid")
    for row in affine:
        if (
            not isinstance(row, list)
            or len(row) != 4
            or any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not isfinite(float(item))
                for item in row
            )
        ):
            raise ValueError("Patient LPS affine is invalid")
    if [float(item) for item in affine[3]] != [0.0, 0.0, 0.0, 1.0]:
        raise ValueError("Patient LPS affine is invalid")
    runtime_fingerprint = request.get("expected_runtime_fingerprint_sha256")
    if (
        not isinstance(runtime_fingerprint, str)
        or len(runtime_fingerprint) != 64
        or any(character not in "0123456789abcdef" for character in runtime_fingerprint)
    ):
        raise ValueError("surface runtime fingerprint is invalid")
    for key in ("voxel_count", "max_vertices", "max_triangles", "max_payload_bytes"):
        positive_int(request.get(key), key)
    return request


def canonical_vertex_normals(positions, faces, orientation_reference):
    import numpy as np

    triangles = positions[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    if not np.all(np.isfinite(cross)) or np.any(lengths <= 1e-12):
        raise ValueError("marching-cubes output contains degenerate triangles")

    # scikit-image normals are interpolated scalar-field gradient references. They
    # define the *global* inside/outside orientation, but a complex real mask can
    # contain a small number of faces whose cross product disagrees locally with
    # the average of those interpolated vertex references. Treating every local
    # disagreement as invalid rejects otherwise coherent marching-cubes meshes.
    reference = orientation_reference[faces].mean(axis=1)
    agreement = np.einsum("ij,ij->i", cross, reference)
    agreement_magnitude = float(np.sum(np.abs(agreement), dtype=np.float64))
    agreement_score = float(np.sum(agreement, dtype=np.float64))
    if (
        not np.all(np.isfinite(agreement))
        or not np.isfinite(agreement_magnitude)
        or not np.isfinite(agreement_score)
        or agreement_magnitude <= 1e-12
        or abs(agreement_score) <= max(1e-12, agreement_magnitude * 1e-6)
    ):
        raise ValueError("surface outward orientation reference is ambiguous")
    if agreement_score < 0.0:
        faces = faces[:, [0, 2, 1]]
        cross = -cross

    # Emit canonical Patient-LPS normals from the final triangle geometry itself.
    # Area-weighted accumulation preserves deterministic vertex normals and
    # makes their orientation follow the single globally canonicalized winding.
    vertex_normals = np.zeros_like(positions, dtype=np.float64)
    np.add.at(vertex_normals, faces[:, 0], cross)
    np.add.at(vertex_normals, faces[:, 1], cross)
    np.add.at(vertex_normals, faces[:, 2], cross)
    normal_lengths = np.linalg.norm(vertex_normals, axis=1)
    if np.any(normal_lengths <= 1e-12) or not np.all(np.isfinite(normal_lengths)):
        raise ValueError("surface normals are invalid")
    vertex_normals /= normal_lengths[:, None]

    face_alignment = np.einsum(
        "ij,ij->i", cross, vertex_normals[faces].mean(axis=1)
    )
    alignment_magnitude = float(np.sum(np.abs(face_alignment), dtype=np.float64))
    alignment_score = float(np.sum(face_alignment, dtype=np.float64))
    if (
        not np.all(np.isfinite(face_alignment))
        or not np.isfinite(alignment_magnitude)
        or not np.isfinite(alignment_score)
        or alignment_magnitude <= 1e-12
        or alignment_score <= max(1e-12, alignment_magnitude * 1e-6)
    ):
        raise ValueError("surface normals do not match triangle winding")
    return faces, vertex_normals


def runtime_identity() -> dict[str, str]:
    payload = {
        "schema_version": 1,
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "scikit_image_version": importlib.metadata.version("scikit-image"),
        "marching_cubes_available": True,
    }
    fingerprint = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return {
        "python_version": payload["python_version"],
        "numpy_version": payload["numpy_version"],
        "scikit_image_version": payload["scikit_image_version"],
        "runtime_fingerprint_sha256": fingerprint,
    }


def extract_surface(*, label_map: Path, request: dict[str, object], output: Path) -> dict[str, object]:
    import numpy as np
    from skimage.measure import marching_cubes

    runtime = runtime_identity()
    if runtime["runtime_fingerprint_sha256"] != request["expected_runtime_fingerprint_sha256"]:
        raise ValueError("surface runtime changed after qualification")
    if sha256_file(label_map) != request["expected_label_map_sha256"]:
        raise ValueError("canonical label-map artifact changed")
    labels = np.load(label_map, mmap_mode="r", allow_pickle=False)
    expected_shape = tuple(int(item) for item in request["shape"])
    if tuple(labels.shape) != expected_shape or str(labels.dtype) != "uint16":
        raise ValueError("canonical label-map artifact contract changed")
    minimum = np.asarray(request["minimum_index"], dtype=np.int64)
    maximum = np.asarray(request["maximum_index"], dtype=np.int64)
    if np.any(maximum < minimum) or np.any(maximum >= np.asarray(expected_shape)):
        raise ValueError("surface ROI is invalid")
    roi_shape = maximum - minimum + 1
    roi_voxels = int(np.prod(roi_shape))
    if roi_voxels <= 0 or roi_voxels > 64_000_000:
        raise ValueError("surface ROI exceeds worker budget")
    slices = tuple(slice(int(minimum[axis]), int(maximum[axis]) + 1) for axis in range(3))
    mask = np.asarray(labels[slices] == int(request["label_id"]), dtype=np.uint8)
    if int(np.count_nonzero(mask)) != int(request["voxel_count"]):
        raise ValueError("selected label changed during surface extraction")
    padded = np.pad(mask, 1, mode="constant", constant_values=0)
    vertices, faces, skimage_normals, _ = marching_cubes(
        padded,
        level=0.5,
        spacing=(1.0, 1.0, 1.0),
        gradient_direction="descent",
        allow_degenerate=False,
        method="lewiner",
    )
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    skimage_normals = np.asarray(skimage_normals, dtype=np.float64)
    if len(vertices) <= 0 or len(faces) <= 0:
        raise ValueError("selected label has no extractable surface")
    if len(vertices) > int(request["max_vertices"]) or len(faces) > int(request["max_triangles"]):
        raise ValueError("accurate surface exceeds worker geometry budget")

    # Padding creates an explicit zero-valued exterior, so the 0.5 interface lands at
    # voxel-cell boundaries (-0.5 / N-0.5) even when the label touches an array edge.
    vertices += minimum.astype(np.float64) - 1.0
    affine = np.asarray(request["array_index_to_patient_lps"], dtype=np.float64)
    if (
        affine.shape != (4, 4)
        or not np.all(np.isfinite(affine))
        or abs(float(np.linalg.det(affine[:3, :3]))) <= 1e-12
    ):
        raise ValueError("Patient LPS affine is invalid")
    linear = affine[:3, :3]
    positions = vertices @ linear.T + affine[:3, 3]
    normal_matrix = np.linalg.inv(linear).T
    orientation_reference = skimage_normals @ normal_matrix.T
    orientation_lengths = np.linalg.norm(orientation_reference, axis=1)
    if np.any(orientation_lengths <= 1e-12) or not np.all(np.isfinite(orientation_lengths)):
        raise ValueError("surface orientation reference is invalid")
    orientation_reference /= orientation_lengths[:, None]
    faces, normals = canonical_vertex_normals(positions, faces, orientation_reference)

    positions32 = np.ascontiguousarray(positions, dtype="<f4")
    normals32 = np.ascontiguousarray(normals, dtype="<f4")
    indices32 = np.ascontiguousarray(faces.reshape(-1), dtype="<u4")
    if not np.all(np.isfinite(positions32)) or not np.all(np.isfinite(normals32)):
        raise ValueError("surface output contains non-finite geometry")
    bounds = tuple(
        float(item)
        for item in np.concatenate((positions32.min(axis=0), positions32.max(axis=0)))
    )
    position_bytes = positions32.tobytes(order="C")
    normal_bytes = normals32.tobytes(order="C")
    index_bytes = indices32.tobytes(order="C")
    header = HEADER.pack(
        MAGIC,
        SCHEMA_VERSION,
        int(request["label_id"]),
        len(positions32),
        len(indices32),
        len(position_bytes),
        len(normal_bytes),
        len(index_bytes),
        FLAGS,
    )
    payload = header + position_bytes + normal_bytes + index_bytes
    if len(payload) > int(request["max_payload_bytes"]):
        raise ValueError("accurate surface exceeds worker payload budget")
    with output.open("xb") as handle:
        os.chmod(output, 0o600)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "extract_accurate_surface",
        "label_id": int(request["label_id"]),
        "vertex_count": len(positions32),
        "triangle_count": len(faces),
        "payload_bytes": len(payload),
        "payload_sha256": sha256(payload).hexdigest(),
        "bounds_lps_mm": list(bounds),
        "coordinate_system": "patient_lps",
        "extraction": EXTRACTION,
        "runtime_fingerprint_sha256": runtime["runtime_fingerprint_sha256"],
        "python_version": runtime["python_version"],
        "numpy_version": runtime["numpy_version"],
        "scikit_image_version": runtime["scikit_image_version"],
        "source_label_map": "immutable",
        "clinical_validation": "not_claimed",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract one accurate Phase 6A Patient-LPS segmentation surface"
    )
    parser.add_argument("--label-map-npy", required=True)
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--output-surface", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        label_map = absolute_regular_file(args.label_map_npy, "label-map NPY")
        request_path = absolute_regular_file(args.request_json, "surface request JSON")
        output = absolute_output(args.output_surface, "surface output")
        report = extract_surface(
            label_map=label_map,
            request=load_request(request_path),
            output=output,
        )
    except Exception as exc:  # Parent keeps worker diagnostics private.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
