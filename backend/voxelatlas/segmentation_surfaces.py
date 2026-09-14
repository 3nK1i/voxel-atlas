from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import ceil, isfinite
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from typing import Callable

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - numpy is a backend dependency
    np = None  # type: ignore[assignment]

from .dicom_ingestion import DicomStudyRepository
from .segmentation import SegmentationValidationError
from .segmentation_label_maps import SegmentationLabelMapService
from .segmentation_surface_runtime import (
    SegmentationSurfaceRuntimeQualifier,
    SegmentationSurfaceRuntimeReport,
)


# Phase 5F1 preview transport remains supported for backward compatibility.
SURFACE_SCHEMA_VERSION = 1
SURFACE_MEDIA_TYPE = "application/x-voxelatlas-surface-v1"
SURFACE_MAGIC = b"VXSF"
SURFACE_HEADER = struct.Struct("<4s7I")
SURFACE_EXTRACTION = "voxel_boundary_faces"
SURFACE_QUALITIES = {
    "preview": {"target_occupied_cells": 7_000, "max_triangles": 30_000},
    "balanced": {"target_occupied_cells": 18_000, "max_triangles": 72_000},
}
MAX_SURFACE_STRIDE = 16

# Phase 6A accurate transport. Later mesh-refinement policy remains out of scope.
ACCURATE_SURFACE_SCHEMA_VERSION = 2
ACCURATE_SURFACE_MEDIA_TYPE = "application/x-voxelatlas-surface-v2"
ACCURATE_SURFACE_HEADER = struct.Struct("<4s8I")
ACCURATE_SURFACE_EXTRACTION = "marching_cubes_half_voxel"
ACCURATE_SURFACE_QUALITY = "accurate"
ACCURATE_SURFACE_FLAGS = 1  # Patient-LPS float32 normals are present.
ACCURATE_SURFACE_ALGORITHM_VERSION = 1

# Phase 6B remains the same surface service and v2 transport. The refined mesh is
# a bounded derivative of the exact Phase 6A accurate artifact, never a second
# mask-to-mesh pipeline. API default remains accurate for compatibility; the
# browser presentation may prefer the refined derivative.
REFINED_SURFACE_QUALITY = "refined"
REFINED_SURFACE_REFINEMENT = "bounded_taubin_vertex_clustering"
REFINED_SURFACE_ALGORITHM_VERSION = 2
REFINED_SMOOTHING_ITERATIONS = 2
REFINED_TAUBIN_LAMBDA = 0.33
REFINED_TAUBIN_MU = -0.34
REFINED_SMOOTHING_DISPLACEMENT_FRACTION = 0.25
REFINED_TOTAL_DISPLACEMENT_FRACTION = 0.80
REFINED_MIN_TRIANGLE_RETENTION_RATIO = 0.70
REFINED_CLUSTER_CELL_SIZES_INDEX = (0.50, 0.65, 0.70, 0.80)
REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES = 12
REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES = 6
REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION = 0.0001
REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION = 0.0001
DEFAULT_SURFACE_QUALITY = ACCURATE_SURFACE_QUALITY
PRESENTATION_SURFACE_QUALITY = REFINED_SURFACE_QUALITY
MAX_ACCURATE_ROI_VOXELS = 64_000_000
MAX_ACCURATE_VERTICES = 1_500_000
MAX_ACCURATE_TRIANGLES = 2_500_000
MAX_ACCURATE_PAYLOAD_BYTES = 96 * 1024 * 1024
MAX_ACCURATE_WORKER_REPORT_BYTES = 64 * 1024
MAX_ACCURATE_WORKER_TIMEOUT_SECONDS = 180.0


WorkerRunner = Callable[..., object]


@dataclass(frozen=True)
class SegmentationSurface:
    label_map_id: str
    label_id: int
    quality: str
    extraction: str
    coordinate_system: str
    stride: int
    vertex_count: int
    triangle_count: int
    bounds_lps_mm: tuple[float, float, float, float, float, float]
    payload_sha256: str
    payload: bytes
    schema_version: int = SURFACE_SCHEMA_VERSION
    media_type: str = SURFACE_MEDIA_TYPE
    surface_id: str = ""
    provenance_sha256: str = ""
    normal_count: int = 0
    refinement: str = ""
    reference_surface_id: str = ""
    reference_payload_sha256: str = ""
    topology_repair_count: int = 0
    boundary_edge_count: int = 0
    nonmanifold_edge_count: int = 0
    nonmanifold_vertex_count: int = 0
    connected_component_count: int = 0
    euler_characteristic: int = 0
    safe_compact_repair_count: int = 0
    post_compact_reference_triangle_count: int = 0
    reference_boundary_edge_count: int = 0
    reference_nonmanifold_edge_count: int = 0
    reference_nonmanifold_vertex_count: int = 0
    reference_connected_component_count: int = 0
    topology_local_repair_applied: bool = False
    topology_repair_removed_face_count: int = 0
    topology_repair_removed_face_fraction: float = 0.0
    topology_repair_removed_area_mm2: float = 0.0
    topology_repair_removed_area_fraction: float = 0.0
    topology_repair_initial_displacement_mm: float = 0.0
    repaired_reference_triangle_count: int = 0
    max_displacement_mm: float = 0.0
    displacement_limit_mm: float = 0.0
    triangle_retention_ratio: float = 1.0
    decimation_applied: bool = False
    decimation_cell_size_index: float = 0.0


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SegmentationValidationError("Segmentation surface metadata is invalid") from exc


def _canonical_sha256(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SegmentationValidationError("Canonical label-map artifact is unreadable") from exc
    return digest.hexdigest()


def _shape(value: object) -> tuple[int, int, int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value)
    ):
        raise SegmentationValidationError("Canonical label-map shape is invalid")
    return int(value[0]), int(value[1]), int(value[2])


def _affine(value: object):
    if np is None:
        raise SegmentationValidationError("Segmentation surface extraction requires numpy")
    try:
        matrix = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SegmentationValidationError("Canonical label-map Patient LPS affine is invalid") from exc
    if (
        matrix.shape != (4, 4)
        or not np.all(np.isfinite(matrix))
        or not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-8)
        or abs(float(np.linalg.det(matrix[:3, :3]))) <= 1e-12
    ):
        raise SegmentationValidationError("Canonical label-map Patient LPS affine is invalid")
    return matrix


def _matrix_list(value: object, field: str) -> list[list[float]]:
    matrix = _affine(value)
    return [[float(item) for item in row] for row in matrix.tolist()]


def _labels(value: object) -> tuple[int, ...]:
    if (
        not isinstance(value, list)
        or not value
        or value != sorted(set(value))
        or value[0] != 0
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in value)
    ):
        raise SegmentationValidationError("Canonical label inventory is invalid")
    return tuple(int(item) for item in value)


def _required_text(descriptor: dict[str, object], key: str) -> str:
    value = descriptor.get(key)
    if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
        raise SegmentationValidationError(f"Segmentation surface provenance field {key} is invalid")
    return value


def _required_sha256(descriptor: dict[str, object], key: str) -> str:
    value = _required_text(descriptor, key).lower()
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise SegmentationValidationError(f"Segmentation surface provenance field {key} is invalid")
    return value


def _accurate_provenance(
    descriptor: dict[str, object],
    *,
    label_id: int,
    runtime: SegmentationSurfaceRuntimeReport,
) -> tuple[dict[str, object], str, str]:
    if (
        not runtime.qualified
        or runtime.python_version is None
        or runtime.numpy_version is None
        or runtime.scikit_image_version is None
        or runtime.runtime_fingerprint_sha256 is None
    ):
        raise SegmentationValidationError("Accurate segmentation surface runtime is not qualified")
    provenance: dict[str, object] = {
        "surface_schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
        "surface_algorithm_version": ACCURATE_SURFACE_ALGORITHM_VERSION,
        "extraction": ACCURATE_SURFACE_EXTRACTION,
        "coordinate_system": "patient_lps",
        "length_units": "mm",
        "label_id": label_id,
        "label_map_id": _required_text(descriptor, "label_map_id"),
        "label_map_sha256": _required_sha256(descriptor, "artifact_sha256"),
        "source_study_id": _required_text(descriptor, "source_study_id"),
        "source_study_instance_uid": _required_text(descriptor, "source_study_instance_uid"),
        "source_series_uid": _required_text(descriptor, "source_series_uid"),
        "source_modality": _required_text(descriptor, "source_modality"),
        "source_volume_descriptor_sha256": _required_sha256(
            descriptor, "source_volume_descriptor_sha256"
        ),
        "source_volume_artifact_sha256": _required_sha256(
            descriptor, "source_volume_artifact_sha256"
        ),
        "segmentation_job_id": _required_text(descriptor, "segmentation_job_id"),
        "segmentation_terminal_provenance_sha256": _required_sha256(
            descriptor, "segmentation_terminal_provenance_sha256"
        ),
        "provider_id": _required_text(descriptor, "provider_id"),
        "provider_version": _required_text(descriptor, "provider_version"),
        "model_id": _required_text(descriptor, "model_id"),
        "model_version": _required_text(descriptor, "model_version"),
        "model_descriptor_sha256": _required_sha256(descriptor, "model_descriptor_sha256"),
        "task": _required_text(descriptor, "task"),
        "task_definition_sha256": _required_sha256(descriptor, "task_definition_sha256"),
        "provider_mask_sha256": _required_sha256(descriptor, "provider_mask_sha256"),
        "surface_runtime": {
            "python_version": runtime.python_version,
            "numpy_version": runtime.numpy_version,
            "scikit_image_version": runtime.scikit_image_version,
            "runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
        },
        "array_index_to_patient_lps": _matrix_list(
            descriptor.get("array_index_to_patient_lps"), "array_index_to_patient_lps"
        ),
        "model_index_to_patient_lps": _matrix_list(
            descriptor.get("model_index_to_patient_lps"), "model_index_to_patient_lps"
        ),
        "source_to_model_index": _matrix_list(
            descriptor.get("source_to_model_index"), "source_to_model_index"
        ),
        "model_to_source_index": _matrix_list(
            descriptor.get("model_to_source_index"), "model_to_source_index"
        ),
        "resampled": descriptor.get("resampled") is True,
        "interpolation": _required_text(descriptor, "interpolation"),
        "source_label_map": "immutable",
        "clinical_validation": "not_claimed",
    }
    if descriptor.get("resampled") not in (True, False):
        raise SegmentationValidationError("Segmentation surface provenance resampling state is invalid")
    provenance_sha256 = _canonical_sha256(provenance)
    identity = {
        "surface_schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
        "surface_algorithm_version": ACCURATE_SURFACE_ALGORITHM_VERSION,
        "provenance_sha256": provenance_sha256,
    }
    surface_id = f"surf-{_canonical_sha256(identity)[:32]}"
    return provenance, provenance_sha256, surface_id


def _refined_policy() -> dict[str, object]:
    return {
        "smoothing_iterations": REFINED_SMOOTHING_ITERATIONS,
        "taubin_lambda": REFINED_TAUBIN_LAMBDA,
        "taubin_mu": REFINED_TAUBIN_MU,
        "smoothing_displacement_fraction": REFINED_SMOOTHING_DISPLACEMENT_FRACTION,
        "total_displacement_fraction": REFINED_TOTAL_DISPLACEMENT_FRACTION,
        "minimum_triangle_retention_ratio": REFINED_MIN_TRIANGLE_RETENTION_RATIO,
        "cluster_cell_sizes_index": list(REFINED_CLUSTER_CELL_SIZES_INDEX),
        "local_topology_repair_max_candidate_faces": REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES,
        "local_topology_repair_max_removed_faces": REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES,
        "local_topology_repair_max_removed_face_fraction": REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION,
        "local_topology_repair_max_removed_area_fraction": REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION,
        "require_closed_edge_manifold": True,
        "require_vertex_fan_manifold": True,
    }


def _refined_provenance(
    descriptor: dict[str, object],
    *,
    label_id: int,
    runtime: SegmentationSurfaceRuntimeReport,
    reference_surface: SegmentationSurface,
) -> tuple[dict[str, object], str, str]:
    accurate_provenance, _, _ = _accurate_provenance(
        descriptor, label_id=label_id, runtime=runtime
    )
    provenance = dict(accurate_provenance)
    provenance.update(
        {
            "refinement_algorithm_version": REFINED_SURFACE_ALGORITHM_VERSION,
            "quality": REFINED_SURFACE_QUALITY,
            "refinement": REFINED_SURFACE_REFINEMENT,
            "refinement_policy": _refined_policy(),
            "derived_from_accurate_surface": {
                "surface_id": reference_surface.surface_id,
                "payload_sha256": reference_surface.payload_sha256,
                "provenance_sha256": reference_surface.provenance_sha256,
                "vertex_count": reference_surface.vertex_count,
                "triangle_count": reference_surface.triangle_count,
            },
            "surface_to_mask_deviation_qualification": "deferred_to_phase6g",
        }
    )
    provenance_sha256 = _canonical_sha256(provenance)
    identity = {
        "surface_schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
        "refinement_algorithm_version": REFINED_SURFACE_ALGORITHM_VERSION,
        "reference_surface_id": reference_surface.surface_id,
        "reference_payload_sha256": reference_surface.payload_sha256,
        "provenance_sha256": provenance_sha256,
    }
    surface_id = f"surf-{_canonical_sha256(identity)[:32]}"
    return provenance, provenance_sha256, surface_id


def _boundary_face_count(mask: object) -> int:
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    center = padded[1:-1, 1:-1, 1:-1]
    faces = 0
    for axis in range(3):
        before = [slice(1, -1)] * 3
        after = [slice(1, -1)] * 3
        before[axis] = slice(0, -2)
        after[axis] = slice(2, None)
        faces += int(np.count_nonzero(center & ~padded[tuple(before)]))
        faces += int(np.count_nonzero(center & ~padded[tuple(after)]))
    return faces


def _coarse_mask(
    labels: object,
    *,
    label_id: int,
    minimum: object,
    maximum: object,
    stride: int,
):
    slices = tuple(slice(int(minimum[axis]), int(maximum[axis]) + 1) for axis in range(3))
    mask = np.asarray(labels[slices] == label_id, dtype=bool)
    padded_shape = tuple(int(ceil(size / stride) * stride) for size in mask.shape)
    padding = tuple((0, padded_shape[axis] - mask.shape[axis]) for axis in range(3))
    if any(after for _, after in padding):
        mask = np.pad(mask, padding, mode="constant", constant_values=False)
    coarse = mask.reshape(
        padded_shape[0] // stride,
        stride,
        padded_shape[1] // stride,
        stride,
        padded_shape[2] // stride,
        stride,
    ).any(axis=(1, 3, 5))
    return coarse


_FACE_CORNERS = (
    (0, -1, ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0))),
    (0, 1, ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
    (1, -1, ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
    (1, 1, ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0))),
    (2, -1, ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0))),
    (2, 1, ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
)


def _mesh_payload(
    coarse: object,
    *,
    minimum: object,
    maximum: object,
    stride: int,
    affine: object,
    label_id: int,
) -> tuple[bytes, int, int, tuple[float, float, float, float, float, float]]:
    positions: list[tuple[float, float, float]] = []
    indices: list[int] = []
    dimensions = coarse.shape
    for cell in np.argwhere(coarse):
        for axis, direction, corners in _FACE_CORNERS:
            neighbor = cell.copy()
            neighbor[axis] += direction
            if 0 <= neighbor[axis] < dimensions[axis] and bool(coarse[tuple(neighbor)]):
                continue
            low = np.asarray(minimum, dtype=np.float64) + cell * stride - 0.5
            high = np.minimum(low + stride, np.asarray(maximum, dtype=np.float64) + 0.5)
            base = len(positions)
            for corner in corners:
                source = np.where(np.asarray(corner, dtype=bool), high, low)
                patient = affine[:3, :3] @ source + affine[:3, 3]
                positions.append(tuple(float(item) for item in patient))
            indices.extend((base, base + 1, base + 2, base, base + 2, base + 3))

    position_array = np.asarray(positions, dtype="<f4")
    index_array = np.asarray(indices, dtype="<u4")
    vertex_count = int(position_array.shape[0])
    triangle_count = int(index_array.size // 3)
    if vertex_count <= 0 or triangle_count <= 0:
        raise SegmentationValidationError("Selected segmentation label has no extractable surface")
    minimum_lps = np.min(position_array, axis=0)
    maximum_lps = np.max(position_array, axis=0)
    bounds = tuple(float(item) for item in np.concatenate((minimum_lps, maximum_lps)))
    if not all(isfinite(item) for item in bounds):
        raise SegmentationValidationError("Segmentation surface bounds are invalid")
    position_bytes = position_array.tobytes(order="C")
    index_bytes = index_array.tobytes(order="C")
    header = SURFACE_HEADER.pack(
        SURFACE_MAGIC,
        SURFACE_SCHEMA_VERSION,
        label_id,
        vertex_count,
        len(indices),
        stride,
        len(position_bytes),
        len(index_bytes),
    )
    return header + position_bytes + index_bytes, vertex_count, triangle_count, bounds


def _label_bounds_and_count(labels: object, *, label_id: int) -> tuple[object, object, int]:
    minimum = np.asarray(labels.shape, dtype=np.int64)
    maximum = np.asarray([-1, -1, -1], dtype=np.int64)
    count = 0
    for slice_index in range(int(labels.shape[0])):
        plane = np.asarray(labels[slice_index] == label_id, dtype=bool)
        plane_count = int(np.count_nonzero(plane))
        if plane_count == 0:
            continue
        rows, columns = np.nonzero(plane)
        count += plane_count
        minimum[0] = min(int(minimum[0]), slice_index)
        minimum[1] = min(int(minimum[1]), int(rows.min()))
        minimum[2] = min(int(minimum[2]), int(columns.min()))
        maximum[0] = max(int(maximum[0]), slice_index)
        maximum[1] = max(int(maximum[1]), int(rows.max()))
        maximum[2] = max(int(maximum[2]), int(columns.max()))
    if count <= 0 or np.any(maximum < minimum):
        raise SegmentationValidationError(
            "Selected segmentation label is absent from the canonical artifact"
        )
    return minimum, maximum, count


def _safe_surface_temp_root(data_dir: Path) -> Path:
    segmentation = data_dir / "segmentation"
    root = segmentation / "surface-tmp"
    if segmentation.is_symlink() or (segmentation.exists() and not segmentation.is_dir()):
        raise SegmentationValidationError("Segmentation surface temporary repository is unsafe")
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise SegmentationValidationError("Segmentation surface temporary repository is unsafe")
    segmentation.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.mkdir(exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    return root


def _parse_worker_report(completed: object) -> dict[str, object]:
    if getattr(completed, "returncode", None) != 0:
        raise SegmentationValidationError("Accurate segmentation surface worker failed")
    stdout = getattr(completed, "stdout", None)
    if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_ACCURATE_WORKER_REPORT_BYTES:
        raise SegmentationValidationError("Accurate segmentation surface worker report is invalid")
    try:
        lines = [line for line in stdout.splitlines() if line.strip()]
        if not lines:
            raise ValueError("empty")
        report = json.loads(lines[-1])
    except (ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise SegmentationValidationError(
            "Accurate segmentation surface worker report is invalid"
        ) from exc
    if not isinstance(report, dict):
        raise SegmentationValidationError("Accurate segmentation surface worker report is invalid")
    return report


def _validate_accurate_payload(
    payload: bytes,
    *,
    label_id: int,
    report: dict[str, object],
    runtime: SegmentationSurfaceRuntimeReport,
) -> tuple[int, int, tuple[float, float, float, float, float, float]]:
    if np is None:
        raise SegmentationValidationError("Segmentation surface extraction requires numpy")
    if len(payload) < ACCURATE_SURFACE_HEADER.size or len(payload) > MAX_ACCURATE_PAYLOAD_BYTES:
        raise SegmentationValidationError("Accurate segmentation surface payload size is invalid")
    try:
        (
            magic,
            version,
            payload_label_id,
            vertex_count,
            index_count,
            position_bytes,
            normal_bytes,
            index_bytes,
            flags,
        ) = ACCURATE_SURFACE_HEADER.unpack_from(payload)
    except struct.error as exc:
        raise SegmentationValidationError("Accurate segmentation surface payload is invalid") from exc
    if (
        magic != SURFACE_MAGIC
        or version != ACCURATE_SURFACE_SCHEMA_VERSION
        or payload_label_id != label_id
        or vertex_count <= 0
        or vertex_count > MAX_ACCURATE_VERTICES
        or index_count <= 0
        or index_count % 3 != 0
        or index_count // 3 > MAX_ACCURATE_TRIANGLES
        or position_bytes != vertex_count * 3 * 4
        or normal_bytes != vertex_count * 3 * 4
        or index_bytes != index_count * 4
        or flags != ACCURATE_SURFACE_FLAGS
        or len(payload)
        != ACCURATE_SURFACE_HEADER.size + position_bytes + normal_bytes + index_bytes
    ):
        raise SegmentationValidationError("Accurate segmentation surface payload contract is invalid")
    offset = ACCURATE_SURFACE_HEADER.size
    positions = np.frombuffer(payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape(-1, 3)
    offset += position_bytes
    normals = np.frombuffer(payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape(-1, 3)
    offset += normal_bytes
    indices = np.frombuffer(payload, dtype="<u4", count=index_count, offset=offset)
    if (
        not np.all(np.isfinite(positions))
        or not np.all(np.isfinite(normals))
        or int(indices.max()) >= vertex_count
    ):
        raise SegmentationValidationError("Accurate segmentation surface geometry is invalid")
    lengths = np.linalg.norm(normals.astype(np.float64), axis=1)
    if not np.allclose(lengths, 1.0, rtol=0.0, atol=2e-5):
        raise SegmentationValidationError("Accurate segmentation surface normals are invalid")
    minimum_lps = positions.min(axis=0).astype(np.float64)
    maximum_lps = positions.max(axis=0).astype(np.float64)
    bounds = tuple(float(item) for item in np.concatenate((minimum_lps, maximum_lps)))
    if not all(isfinite(item) for item in bounds):
        raise SegmentationValidationError("Accurate segmentation surface bounds are invalid")
    expected_report = {
        "schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
        "operation": "extract_accurate_surface",
        "label_id": label_id,
        "vertex_count": vertex_count,
        "triangle_count": index_count // 3,
        "payload_bytes": len(payload),
        "payload_sha256": sha256(payload).hexdigest(),
        "bounds_lps_mm": list(bounds),
        "coordinate_system": "patient_lps",
        "extraction": ACCURATE_SURFACE_EXTRACTION,
        "runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
        "python_version": runtime.python_version,
        "numpy_version": runtime.numpy_version,
        "scikit_image_version": runtime.scikit_image_version,
        "source_label_map": "immutable",
        "clinical_validation": "not_claimed",
    }
    for key, expected in expected_report.items():
        actual = report.get(key)
        if key == "bounds_lps_mm":
            try:
                actual_array = np.asarray(actual, dtype=np.float64)
            except (TypeError, ValueError) as exc:
                raise SegmentationValidationError(
                    "Accurate segmentation surface worker report is invalid"
                ) from exc
            if actual_array.shape != (6,) or not np.allclose(
                actual_array, np.asarray(expected), rtol=0.0, atol=1e-5
            ):
                raise SegmentationValidationError(
                    "Accurate segmentation surface worker report is invalid"
                )
        elif actual != expected:
            raise SegmentationValidationError("Accurate segmentation surface worker report is invalid")
    return vertex_count, index_count // 3, bounds


def _link_component_count(first: object, second: object) -> int:
    mapping: dict[int, int] = {}
    parent: list[int] = []
    rank: list[int] = []

    def local_index(value: int) -> int:
        index = mapping.get(value)
        if index is not None:
            return index
        index = len(parent)
        mapping[value] = index
        parent.append(index)
        rank.append(0)
        return index

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a: int, b: int) -> None:
        root_a = find(a)
        root_b = find(b)
        if root_a == root_b:
            return
        if rank[root_a] < rank[root_b]:
            root_a, root_b = root_b, root_a
        parent[root_b] = root_a
        if rank[root_a] == rank[root_b]:
            rank[root_a] += 1

    for raw_a, raw_b in zip(first, second):
        union(local_index(int(raw_a)), local_index(int(raw_b)))
    return len({find(index) for index in range(len(parent))})


def _nonmanifold_vertex_fan_count(faces: object, *, vertex_count: int) -> int:
    if vertex_count <= 0:
        return 0
    face_array = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    if len(face_array) <= 0:
        return 0
    owners = np.concatenate(
        (face_array[:, 0], face_array[:, 1], face_array[:, 2])
    )
    link_first = np.concatenate(
        (face_array[:, 1], face_array[:, 2], face_array[:, 0])
    )
    link_second = np.concatenate(
        (face_array[:, 2], face_array[:, 0], face_array[:, 1])
    )
    order = np.argsort(owners, kind="stable")
    owners = owners[order]
    link_first = link_first[order]
    link_second = link_second[order]
    changes = np.flatnonzero(owners[1:] != owners[:-1]) + 1
    starts = np.concatenate((np.asarray([0], dtype=np.int64), changes))
    ends = np.concatenate((changes, np.asarray([len(owners)], dtype=np.int64)))
    nonmanifold = 0
    for start, end in zip(starts.tolist(), ends.tolist()):
        if _link_component_count(link_first[start:end], link_second[start:end]) != 1:
            nonmanifold += 1
    return nonmanifold


def _compact_reference_topology_geometry(
    positions: object, indices: object
) -> tuple[object, object, int, float]:
    positions_array = np.asarray(positions, dtype=np.float64)
    faces = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
    valid = (
        (faces[:, 0] != faces[:, 1])
        & (faces[:, 1] != faces[:, 2])
        & (faces[:, 0] != faces[:, 2])
    )
    removed_degenerate = int(np.count_nonzero(~valid))
    faces = faces[valid]
    if len(faces) <= 0:
        raise SegmentationValidationError(
            "Accurate segmentation surface reference has no valid triangles"
        )
    triangles = positions_array[faces]
    cross = np.cross(
        triangles[:, 1] - triangles[:, 0],
        triangles[:, 2] - triangles[:, 0],
    )
    areas = 0.5 * np.linalg.norm(cross, axis=1)
    area_ok = np.isfinite(areas) & (areas > 1e-12)
    removed_degenerate += int(np.count_nonzero(~area_ok))
    faces = faces[area_ok]
    if len(faces) <= 0:
        raise SegmentationValidationError(
            "Accurate segmentation surface reference has no valid triangles"
        )
    canonical = np.sort(faces, axis=1)
    _, first = np.unique(canonical, axis=0, return_index=True)
    keep = np.sort(first)
    removed_duplicates = len(faces) - len(keep)
    faces = faces[keep]
    used, inverse = np.unique(faces.reshape(-1), return_inverse=True)
    removed_unreferenced = len(positions_array) - len(used)
    compact_positions = positions_array[used]
    compact_faces = inverse.reshape(-1, 3)
    compact_triangles = compact_positions[compact_faces]
    compact_cross = np.cross(
        compact_triangles[:, 1] - compact_triangles[:, 0],
        compact_triangles[:, 2] - compact_triangles[:, 0],
    )
    compact_area = float(
        (0.5 * np.linalg.norm(compact_cross, axis=1)).sum(dtype=np.float64)
    )
    if not isfinite(compact_area) or compact_area <= 1e-12:
        raise SegmentationValidationError(
            "Accurate segmentation surface reference area is invalid"
        )
    return (
        compact_positions,
        compact_faces,
        removed_degenerate + removed_duplicates + removed_unreferenced,
        compact_area,
    )


def _topology_metrics_from_indices(indices: object, *, vertex_count: int) -> dict[str, object]:
    faces = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.sort(edges, axis=1)
    unique_edges, counts = np.unique(edges, axis=0, return_counts=True)
    parent = list(range(vertex_count))
    rank = [0] * vertex_count

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a: int, b: int) -> None:
        root_a = find(a)
        root_b = find(b)
        if root_a == root_b:
            return
        if rank[root_a] < rank[root_b]:
            root_a, root_b = root_b, root_a
        parent[root_b] = root_a
        if rank[root_a] == rank[root_b]:
            rank[root_a] += 1

    for first, second in unique_edges.tolist():
        union(int(first), int(second))

    roots = np.asarray([find(index) for index in range(vertex_count)], dtype=np.int64)
    unique_roots = np.unique(roots)
    component_eulers: list[int] = []
    for root in unique_roots.tolist():
        vertices_mask = roots == root
        component_vertices = int(np.count_nonzero(vertices_mask))
        component_edges = int(np.count_nonzero(vertices_mask[unique_edges[:, 0]]))
        component_faces = int(np.count_nonzero(vertices_mask[faces[:, 0]]))
        component_eulers.append(component_vertices - component_edges + component_faces)

    return {
        "boundary_edge_count": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edge_count": int(np.count_nonzero(counts > 2)),
        "nonmanifold_vertex_count": _nonmanifold_vertex_fan_count(
            faces, vertex_count=vertex_count
        ),
        "connected_component_count": len(unique_roots),
        "euler_characteristic": int(vertex_count - len(unique_edges) + len(faces)),
        "component_euler_signature": sorted(component_eulers),
    }


def _decode_v2_payload_geometry(
    payload: bytes, *, label_id: int, error_prefix: str
) -> tuple[object, object, object, tuple[float, float, float, float, float, float]]:
    if len(payload) < ACCURATE_SURFACE_HEADER.size or len(payload) > MAX_ACCURATE_PAYLOAD_BYTES:
        raise SegmentationValidationError(f"{error_prefix} payload size is invalid")
    try:
        (
            magic,
            version,
            payload_label_id,
            vertex_count,
            index_count,
            position_bytes,
            normal_bytes,
            index_bytes,
            flags,
        ) = ACCURATE_SURFACE_HEADER.unpack_from(payload)
    except struct.error as exc:
        raise SegmentationValidationError(f"{error_prefix} payload is invalid") from exc
    if (
        magic != SURFACE_MAGIC
        or version != ACCURATE_SURFACE_SCHEMA_VERSION
        or payload_label_id != label_id
        or vertex_count <= 0
        or vertex_count > MAX_ACCURATE_VERTICES
        or index_count <= 0
        or index_count % 3 != 0
        or index_count // 3 > MAX_ACCURATE_TRIANGLES
        or position_bytes != vertex_count * 3 * 4
        or normal_bytes != vertex_count * 3 * 4
        or index_bytes != index_count * 4
        or flags != ACCURATE_SURFACE_FLAGS
        or len(payload)
        != ACCURATE_SURFACE_HEADER.size + position_bytes + normal_bytes + index_bytes
    ):
        raise SegmentationValidationError(f"{error_prefix} payload contract is invalid")
    offset = ACCURATE_SURFACE_HEADER.size
    positions = np.frombuffer(
        payload, dtype="<f4", count=vertex_count * 3, offset=offset
    ).reshape(-1, 3)
    offset += position_bytes
    normals = np.frombuffer(
        payload, dtype="<f4", count=vertex_count * 3, offset=offset
    ).reshape(-1, 3)
    offset += normal_bytes
    indices = np.frombuffer(payload, dtype="<u4", count=index_count, offset=offset)
    if (
        not np.all(np.isfinite(positions))
        or not np.all(np.isfinite(normals))
        or int(indices.max()) >= vertex_count
    ):
        raise SegmentationValidationError(f"{error_prefix} geometry is invalid")
    lengths = np.linalg.norm(normals.astype(np.float64), axis=1)
    if not np.allclose(lengths, 1.0, rtol=0.0, atol=2e-5):
        raise SegmentationValidationError(f"{error_prefix} normals are invalid")
    bounds = tuple(
        float(item)
        for item in np.concatenate(
            (positions.min(axis=0).astype(np.float64), positions.max(axis=0).astype(np.float64))
        )
    )
    if not all(isfinite(item) for item in bounds):
        raise SegmentationValidationError(f"{error_prefix} bounds are invalid")
    return positions, normals, indices, bounds


def _parse_refinement_worker_report(completed: object) -> dict[str, object]:
    if getattr(completed, "returncode", None) != 0:
        raise SegmentationValidationError("Refined segmentation surface worker failed")
    stdout = getattr(completed, "stdout", None)
    if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_ACCURATE_WORKER_REPORT_BYTES:
        raise SegmentationValidationError("Refined segmentation surface worker report is invalid")
    try:
        lines = [line for line in stdout.splitlines() if line.strip()]
        if not lines:
            raise ValueError("empty")
        report = json.loads(lines[-1])
    except (ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        ) from exc
    if not isinstance(report, dict):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    return report


def _validate_refined_payload(
    payload: bytes,
    *,
    label_id: int,
    report: dict[str, object],
    runtime: SegmentationSurfaceRuntimeReport,
    reference_surface: SegmentationSurface,
    descriptor: dict[str, object],
) -> tuple[
    int,
    int,
    tuple[float, float, float, float, float, float],
    dict[str, object],
]:
    positions, _, indices, bounds = _decode_v2_payload_geometry(
        payload, label_id=label_id, error_prefix="Refined segmentation surface"
    )
    reference_positions, _, reference_indices, _ = _decode_v2_payload_geometry(
        reference_surface.payload,
        label_id=label_id,
        error_prefix="Accurate segmentation surface reference",
    )
    vertex_count = int(positions.shape[0])
    triangle_count = int(indices.size // 3)
    topology = _topology_metrics_from_indices(indices, vertex_count=vertex_count)
    (
        compact_reference_positions,
        compact_reference_faces,
        safe_compact_repair_count,
        compact_reference_area_mm2,
    ) = _compact_reference_topology_geometry(reference_positions, reference_indices)
    compact_reference_topology = _topology_metrics_from_indices(
        compact_reference_faces.reshape(-1),
        vertex_count=int(compact_reference_positions.shape[0]),
    )
    if (
        topology["boundary_edge_count"] != 0
        or topology["nonmanifold_edge_count"] != 0
        or topology["nonmanifold_vertex_count"] != 0
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface is not a closed vertex-manifold surface"
        )
    if (
        topology["connected_component_count"]
        != compact_reference_topology["connected_component_count"]
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface changed the reference component count"
        )

    affine = _affine(descriptor.get("array_index_to_patient_lps"))
    linear = affine[:3, :3]
    minimum_step_mm = float(np.min(np.linalg.svd(linear, compute_uv=False)))
    displacement_limit_mm = minimum_step_mm * REFINED_TOTAL_DISPLACEMENT_FRACTION
    inverse_linear = np.linalg.inv(linear)
    index_positions = (positions.astype(np.float64) - affine[:3, 3]) @ inverse_linear.T
    shape = np.asarray(_shape(descriptor["shape"]), dtype=np.float64)
    if (
        np.any(index_positions < -0.5 - 2e-5)
        or np.any(index_positions > shape - 0.5 + 2e-5)
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface escaped canonical voxel-cell bounds"
        )
    reference_bounds = np.asarray(reference_surface.bounds_lps_mm, dtype=np.float64)
    refined_bounds = np.asarray(bounds, dtype=np.float64)
    if (
        np.any(refined_bounds[:3] < reference_bounds[:3] - displacement_limit_mm - 1e-5)
        or np.any(refined_bounds[3:] > reference_bounds[3:] + displacement_limit_mm + 1e-5)
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface bounds exceed the displacement policy"
        )
    retention_ratio = triangle_count / reference_surface.triangle_count
    if (
        retention_ratio < REFINED_MIN_TRIANGLE_RETENTION_RATIO - 1e-12
        or retention_ratio > 1.0 + 1e-12
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface triangle retention is outside the bounded policy"
        )

    expected_exact = {
        "schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
        "operation": "refine_accurate_surface",
        "refinement": REFINED_SURFACE_REFINEMENT,
        "refinement_algorithm_version": REFINED_SURFACE_ALGORITHM_VERSION,
        "label_id": label_id,
        "reference_surface_id": reference_surface.surface_id,
        "reference_surface_sha256": reference_surface.payload_sha256,
        "reference_vertex_count": reference_surface.vertex_count,
        "reference_triangle_count": reference_surface.triangle_count,
        "post_compact_reference_vertex_count": int(compact_reference_positions.shape[0]),
        "post_compact_reference_triangle_count": int(len(compact_reference_faces)),
        "safe_compact_repair_count": int(safe_compact_repair_count),
        "post_compact_reference_boundary_edge_count": compact_reference_topology[
            "boundary_edge_count"
        ],
        "post_compact_reference_nonmanifold_edge_count": compact_reference_topology[
            "nonmanifold_edge_count"
        ],
        "post_compact_reference_nonmanifold_vertex_count": compact_reference_topology[
            "nonmanifold_vertex_count"
        ],
        "post_compact_reference_connected_component_count": compact_reference_topology[
            "connected_component_count"
        ],
        "post_compact_reference_euler_characteristic": compact_reference_topology[
            "euler_characteristic"
        ],
        "post_compact_reference_component_euler_signature": compact_reference_topology[
            "component_euler_signature"
        ],
        "vertex_count": vertex_count,
        "triangle_count": triangle_count,
        "payload_bytes": len(payload),
        "payload_sha256": sha256(payload).hexdigest(),
        "coordinate_system": "patient_lps",
        "runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
        "python_version": runtime.python_version,
        "numpy_version": runtime.numpy_version,
        "scikit_image_version": runtime.scikit_image_version,
        "boundary_edge_count": topology["boundary_edge_count"],
        "nonmanifold_edge_count": topology["nonmanifold_edge_count"],
        "nonmanifold_vertex_count": topology["nonmanifold_vertex_count"],
        "connected_component_count": topology["connected_component_count"],
        "euler_characteristic": topology["euler_characteristic"],
        "component_euler_signature": topology["component_euler_signature"],
        "smoothing_iterations": REFINED_SMOOTHING_ITERATIONS,
        "source_label_map": "immutable",
        "clinical_validation": "not_claimed",
    }
    for key, expected in expected_exact.items():
        if report.get(key) != expected:
            raise SegmentationValidationError(
                "Refined segmentation surface worker report is invalid"
            )

    compact_area_report = report.get("post_compact_reference_surface_area_mm2")
    if (
        isinstance(compact_area_report, bool)
        or not isinstance(compact_area_report, (int, float))
        or not isfinite(float(compact_area_report))
        or not np.isclose(
            float(compact_area_report), compact_reference_area_mm2, rtol=0.0, atol=1e-6
        )
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )

    try:
        report_bounds = np.asarray(report.get("bounds_lps_mm"), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        ) from exc
    if report_bounds.shape != (6,) or not np.allclose(
        report_bounds, np.asarray(bounds), rtol=0.0, atol=1e-5
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )

    def report_int(key: str, minimum: int = 0, maximum: int | None = None) -> int:
        value = report.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise SegmentationValidationError(
                "Refined segmentation surface worker report is invalid"
            )
        if maximum is not None and value > maximum:
            raise SegmentationValidationError(
                "Refined segmentation surface worker report is invalid"
            )
        return value

    def report_float(
        key: str, minimum: float = 0.0, maximum: float = float("inf")
    ) -> float:
        value = report.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            or float(value) < minimum - 1e-9
            or float(value) > maximum + 1e-9
        ):
            raise SegmentationValidationError(
                "Refined segmentation surface worker report is invalid"
            )
        return float(value)

    local_repair_applied = report.get("topology_local_repair_applied")
    if not isinstance(local_repair_applied, bool):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    anomaly_edge_count = report_int("topology_repair_anomaly_edge_count")
    candidate_face_count = report_int(
        "topology_repair_candidate_face_count",
        maximum=REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES,
    )
    removed_face_count = report_int(
        "topology_repair_removed_face_count",
        maximum=REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES,
    )
    removed_face_fraction = report_float(
        "topology_repair_removed_face_fraction",
        maximum=REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION,
    )
    removed_area_mm2 = report_float("topology_repair_removed_area_mm2")
    removed_area_fraction = report_float(
        "topology_repair_removed_area_fraction",
        maximum=REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION,
    )
    initial_repair_displacement = report_float(
        "topology_repair_initial_displacement_mm", maximum=0.0
    )
    post_repair_compact_count = report_int("topology_repair_post_compact_count")
    repaired_vertex_count = report_int("repaired_reference_vertex_count", minimum=1)
    repaired_triangle_count = report_int("repaired_reference_triangle_count", minimum=1)

    repaired_topology = {
        "boundary_edge_count": report_int("repaired_reference_boundary_edge_count"),
        "nonmanifold_edge_count": report_int(
            "repaired_reference_nonmanifold_edge_count"
        ),
        "nonmanifold_vertex_count": report_int(
            "repaired_reference_nonmanifold_vertex_count"
        ),
        "connected_component_count": report_int(
            "repaired_reference_connected_component_count", minimum=1
        ),
        "euler_characteristic": report.get("repaired_reference_euler_characteristic"),
        "component_euler_signature": report.get(
            "repaired_reference_component_euler_signature"
        ),
    }
    if (
        isinstance(repaired_topology["euler_characteristic"], bool)
        or not isinstance(repaired_topology["euler_characteristic"], int)
        or not isinstance(repaired_topology["component_euler_signature"], list)
        or any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in repaired_topology["component_euler_signature"]
        )
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    if repaired_topology != topology:
        raise SegmentationValidationError(
            "Refined segmentation surface topology differs from the repaired reference baseline"
        )
    if (
        repaired_topology["boundary_edge_count"] != 0
        or repaired_topology["nonmanifold_edge_count"] != 0
        or repaired_topology["nonmanifold_vertex_count"] != 0
        or repaired_topology["connected_component_count"]
        != compact_reference_topology["connected_component_count"]
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface repaired topology is invalid"
        )
    if repaired_triangle_count != len(compact_reference_faces) - removed_face_count:
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    if repaired_vertex_count > int(compact_reference_positions.shape[0]):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    expected_face_fraction = removed_face_count / len(compact_reference_faces)
    if abs(removed_face_fraction - expected_face_fraction) > 1e-12:
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    if removed_area_mm2 > compact_reference_area_mm2 + 1e-6:
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    expected_area_fraction = removed_area_mm2 / compact_reference_area_mm2
    if abs(removed_area_fraction - expected_area_fraction) > 1e-12:
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    expected_anomaly_edges = (
        compact_reference_topology["boundary_edge_count"]
        + compact_reference_topology["nonmanifold_edge_count"]
    )
    if anomaly_edge_count != expected_anomaly_edges:
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    if local_repair_applied:
        if (
            expected_anomaly_edges <= 0
            or candidate_face_count <= 0
            or removed_face_count <= 0
            or removed_area_mm2 <= 0.0
        ):
            raise SegmentationValidationError(
                "Refined segmentation surface worker report is invalid"
            )
    else:
        if (
            expected_anomaly_edges != 0
            or compact_reference_topology["nonmanifold_vertex_count"] != 0
            or candidate_face_count != 0
            or removed_face_count != 0
            or removed_area_mm2 != 0.0
            or repaired_topology != compact_reference_topology
        ):
            raise SegmentationValidationError(
                "Refined segmentation surface worker report is invalid"
            )

    topology_repair_count = report_int("topology_repair_count")
    if topology_repair_count != (
        safe_compact_repair_count + removed_face_count + post_repair_compact_count
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    max_smoothing_displacement = report_float(
        "max_smoothing_displacement_mm", maximum=displacement_limit_mm
    )
    reported_displacement_limit = report_float(
        "displacement_limit_mm", minimum=displacement_limit_mm, maximum=displacement_limit_mm
    )
    max_displacement = report_float(
        "max_displacement_mm", maximum=displacement_limit_mm
    )
    mean_displacement = report_float(
        "mean_displacement_mm", maximum=displacement_limit_mm
    )
    reported_retention = report_float(
        "triangle_retention_ratio", minimum=retention_ratio, maximum=retention_ratio
    )
    decimation_cleanup_count = report_int("decimation_cleanup_count")

    decimation_applied = report.get("decimation_applied")
    cell_size = report.get("decimation_cell_size_index")
    if not isinstance(decimation_applied, bool):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )
    if (
        isinstance(cell_size, bool)
        or not isinstance(cell_size, (int, float))
        or not isfinite(float(cell_size))
        or (
            float(cell_size) != 0.0
            and not any(
                abs(float(cell_size) - candidate) <= 1e-12
                for candidate in REFINED_CLUSTER_CELL_SIZES_INDEX
            )
        )
        or (decimation_applied and float(cell_size) == 0.0)
        or (not decimation_applied and float(cell_size) != 0.0)
        or (not decimation_applied and decimation_cleanup_count != 0)
    ):
        raise SegmentationValidationError(
            "Refined segmentation surface worker report is invalid"
        )

    validated: dict[str, object] = dict(topology)
    validated.update(
        {
            "topology_repair_count": topology_repair_count,
            "safe_compact_repair_count": safe_compact_repair_count,
            "post_compact_reference_triangle_count": len(compact_reference_faces),
            "reference_boundary_edge_count": compact_reference_topology[
                "boundary_edge_count"
            ],
            "reference_nonmanifold_edge_count": compact_reference_topology[
                "nonmanifold_edge_count"
            ],
            "reference_nonmanifold_vertex_count": compact_reference_topology[
                "nonmanifold_vertex_count"
            ],
            "reference_connected_component_count": compact_reference_topology[
                "connected_component_count"
            ],
            "topology_local_repair_applied": local_repair_applied,
            "topology_repair_removed_face_count": removed_face_count,
            "topology_repair_removed_face_fraction": removed_face_fraction,
            "topology_repair_removed_area_mm2": removed_area_mm2,
            "topology_repair_removed_area_fraction": removed_area_fraction,
            "topology_repair_initial_displacement_mm": initial_repair_displacement,
            "repaired_reference_triangle_count": repaired_triangle_count,
            "max_smoothing_displacement_mm": max_smoothing_displacement,
            "displacement_limit_mm": reported_displacement_limit,
            "max_displacement_mm": max_displacement,
            "mean_displacement_mm": mean_displacement,
            "triangle_retention_ratio": reported_retention,
            "decimation_applied": decimation_applied,
            "decimation_cell_size_index": float(cell_size),
        }
    )
    return vertex_count, triangle_count, bounds, validated


class SegmentationSurfaceService:
    """Patient-LPS surfaces derived from immutable canonical segmentation labels."""

    def __init__(
        self,
        *,
        data_dir: Path,
        study_repository: object | None = None,
        label_map_service: SegmentationLabelMapService | None = None,
        worker_runner: WorkerRunner = subprocess.run,
        worker_python: str | None = None,
        worker_script: Path | None = None,
        refinement_worker_script: Path | None = None,
        runtime_qualifier: SegmentationSurfaceRuntimeQualifier | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.repository = study_repository or DicomStudyRepository(self.data_dir)
        self.label_map_service = label_map_service or SegmentationLabelMapService(
            data_dir=self.data_dir
        )
        self._worker_runner = worker_runner
        self._worker_python = str(worker_python).strip() if worker_python is not None else ""
        self._worker_script = worker_script or (
            Path(__file__).resolve().parents[2] / "scripts" / "phase6a_surface_worker.py"
        )
        self._refinement_worker_script = refinement_worker_script or (
            Path(__file__).resolve().parents[2] / "scripts" / "phase6b_surface_worker.py"
        )
        self._runtime_qualifier = runtime_qualifier or SegmentationSurfaceRuntimeQualifier()
        self._runtime_report: SegmentationSurfaceRuntimeReport | None = None
        self._cache: dict[tuple[str, int, str, int, int], SegmentationSurface] = {}
        self._accurate_cache: dict[str, SegmentationSurface] = {}
        self._refined_cache: dict[str, SegmentationSurface] = {}

    def _artifact_path(self, label_map_id: str) -> Path:
        return self.data_dir / "segmentation" / "label-maps" / label_map_id / "labels.npy"

    def _current_study_id(self) -> str:
        manifest = self.repository.latest_manifest()
        study_id = manifest.get("study_id") if isinstance(manifest, dict) else None
        if not isinstance(study_id, str) or not study_id:
            raise SegmentationValidationError("No stored DICOM study is available")
        return study_id

    def _resolve(self, label_map_id: str | None) -> tuple[str, dict[str, object]] | None:
        study_id = self._current_study_id()
        if label_map_id is None:
            maps = self.label_map_service.list(study_id=study_id)
            if not maps:
                return None
            descriptor = dict(maps[0])
        else:
            descriptor = self.label_map_service.get(label_map_id)
        if descriptor.get("source_study_id") != study_id:
            raise SegmentationValidationError(
                "Canonical label map does not belong to the current study"
            )
        self._validate_descriptor(descriptor)
        return study_id, descriptor

    @staticmethod
    def _validate_descriptor(descriptor: dict[str, object]) -> None:
        if (
            descriptor.get("state") != "ready"
            or descriptor.get("coordinate_system") != "patient_lps"
            or descriptor.get("representation") != "label_map"
            or descriptor.get("artifact_format") != "npy"
            or descriptor.get("dtype") != "uint16"
            or descriptor.get("axis_order") != ["slice", "row", "column"]
        ):
            raise SegmentationValidationError("Canonical label map is not surface-compatible")
        _shape(descriptor.get("shape"))
        _affine(descriptor.get("array_index_to_patient_lps"))
        _labels(descriptor.get("present_labels"))

    def descriptor_latest(self, *, label_map_id: str | None = None) -> dict[str, object]:
        resolved = self._resolve(label_map_id)
        if resolved is None:
            return {
                "schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
                "ready": False,
                "reason": "no_label_map",
                "source_study_id": self._current_study_id(),
                "clinical_validation": "not_claimed",
            }
        study_id, descriptor = resolved
        labels = [label for label in _labels(descriptor["present_labels"]) if label != 0]
        return {
            "schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
            "ready": True,
            "label_map_id": descriptor["label_map_id"],
            "label_map_sha256": descriptor["artifact_sha256"],
            "source_study_id": study_id,
            "source_modality": descriptor["source_modality"],
            "provider_id": descriptor["provider_id"],
            "provider_version": descriptor.get("provider_version"),
            "model_id": descriptor["model_id"],
            "model_version": descriptor.get("model_version"),
            "coordinate_system": "patient_lps",
            "length_units": "mm",
            "surface_endpoint": "/api/studies/latest/segmentation-surfaces/{label_id}",
            "surface_media_type": ACCURATE_SURFACE_MEDIA_TYPE,
            "extraction": ACCURATE_SURFACE_EXTRACTION,
            "quality_profiles": [
                REFINED_SURFACE_QUALITY,
                ACCURATE_SURFACE_QUALITY,
                *SURFACE_QUALITIES,
            ],
            "default_quality": DEFAULT_SURFACE_QUALITY,
            "presentation_quality": PRESENTATION_SURFACE_QUALITY,
            "refined_surface": {
                "schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
                "quality": REFINED_SURFACE_QUALITY,
                "reference_quality": ACCURATE_SURFACE_QUALITY,
                "extraction": ACCURATE_SURFACE_EXTRACTION,
                "refinement": REFINED_SURFACE_REFINEMENT,
                "refinement_algorithm_version": REFINED_SURFACE_ALGORITHM_VERSION,
                "media_type": ACCURATE_SURFACE_MEDIA_TYPE,
                "topology_preserving": True,
                "repaired_topology_preserving": True,
                "bounded_local_face_topology_repair": True,
                "vertex_fan_manifold_required": True,
                "local_topology_repair_max_candidate_faces": (
                    REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES
                ),
                "local_topology_repair_max_removed_faces": (
                    REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES
                ),
                "local_topology_repair_max_removed_face_fraction": (
                    REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION
                ),
                "local_topology_repair_max_removed_area_fraction": (
                    REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION
                ),
                "bounded_smoothing": True,
                "bounded_decimation": True,
                "maximum_displacement_fraction_of_minimum_voxel_step": (
                    REFINED_TOTAL_DISPLACEMENT_FRACTION
                ),
                "minimum_triangle_retention_ratio": REFINED_MIN_TRIANGLE_RETENTION_RATIO,
                "cluster_cell_sizes_index": list(REFINED_CLUSTER_CELL_SIZES_INDEX),
                "source_accurate_surface_immutable": True,
                "surface_to_mask_deviation_qualification": "deferred_to_phase6g",
            },
            "accurate_surface": {
                "schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
                "quality": ACCURATE_SURFACE_QUALITY,
                "extraction": ACCURATE_SURFACE_EXTRACTION,
                "media_type": ACCURATE_SURFACE_MEDIA_TYPE,
                "native_mask_resolution": True,
                "voxel_cell_boundary_semantics": True,
                "patient_lps_normals": True,
                "runtime_configured": bool(self._worker_python),
            },
            "preview_surface": {
                "available": True,
                "schema_version": SURFACE_SCHEMA_VERSION,
                "qualities": list(SURFACE_QUALITIES),
                "extraction": SURFACE_EXTRACTION,
                "media_type": SURFACE_MEDIA_TYPE,
            },
            "present_label_count": len(labels),
            "present_labels": labels,
            "source_label_map_immutable": True,
            "clinical_validation": "not_claimed",
        }

    def _qualified_runtime(self) -> SegmentationSurfaceRuntimeReport:
        if self._runtime_report is None:
            report = self._runtime_qualifier.qualify(self._worker_python or None)
            if not report.qualified:
                raise SegmentationValidationError(report.message)
            self._runtime_report = report
        return self._runtime_report

    def _accurate_surface(
        self,
        *,
        label_id: int,
        descriptor: dict[str, object],
        labels: object,
        path: Path,
    ) -> SegmentationSurface:
        expected_digest = _required_sha256(descriptor, "artifact_sha256")
        if _sha256_file(path) != expected_digest:
            raise SegmentationValidationError("Canonical label-map artifact changed")
        minimum, maximum, voxel_count = _label_bounds_and_count(labels, label_id=label_id)
        roi_shape = maximum - minimum + 1
        roi_voxels = int(np.prod(roi_shape.astype(np.int64)))
        if roi_voxels <= 0 or roi_voxels > MAX_ACCURATE_ROI_VOXELS:
            raise SegmentationValidationError(
                "Selected segmentation surface exceeds the accurate extraction ROI budget"
            )
        runtime = self._qualified_runtime()
        _, provenance_sha256, surface_id = _accurate_provenance(
            descriptor, label_id=label_id, runtime=runtime
        )
        cached = self._accurate_cache.get(surface_id)
        if cached is not None:
            return cached
        if (
            not self._worker_python
            or len(self._worker_python) > 4096
            or any(ord(character) < 32 for character in self._worker_python)
        ):
            raise SegmentationValidationError("Accurate segmentation surface worker Python is invalid")
        worker = Path(self._worker_script)
        if (
            not worker.is_absolute()
            or worker.suffix != ".py"
            or worker.is_symlink()
            or not worker.is_file()
        ):
            raise SegmentationValidationError("Accurate segmentation surface worker script is invalid")
        temp_root = _safe_surface_temp_root(self.data_dir)
        with tempfile.TemporaryDirectory(prefix=".phase6a-", dir=temp_root) as tmp:
            stage = Path(tmp)
            os.chmod(stage, 0o700)
            request_path = stage / "request.json"
            output_path = stage / "surface.vxsf2"
            request = {
                "schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
                "operation": "extract_accurate_surface",
                "label_id": label_id,
                "expected_label_map_sha256": expected_digest,
                "shape": list(_shape(descriptor["shape"])),
                "minimum_index": [int(item) for item in minimum],
                "maximum_index": [int(item) for item in maximum],
                "voxel_count": voxel_count,
                "array_index_to_patient_lps": _matrix_list(
                    descriptor.get("array_index_to_patient_lps"),
                    "array_index_to_patient_lps",
                ),
                "extraction": ACCURATE_SURFACE_EXTRACTION,
                "expected_runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
                "max_vertices": MAX_ACCURATE_VERTICES,
                "max_triangles": MAX_ACCURATE_TRIANGLES,
                "max_payload_bytes": MAX_ACCURATE_PAYLOAD_BYTES,
                "source_label_map": "immutable",
                "clinical_validation": "not_claimed",
            }
            with request_path.open("x", encoding="utf-8") as handle:
                os.chmod(request_path, 0o600)
                handle.write(json.dumps(request, sort_keys=True, separators=(",", ":")))
                handle.flush()
                os.fsync(handle.fileno())
            command = [
                self._worker_python,
                "-I",
                str(worker.resolve(strict=True)),
                "--label-map-npy",
                str(path.resolve(strict=True)),
                "--request-json",
                str(request_path.resolve(strict=True)),
                "--output-surface",
                str(output_path.resolve(strict=False)),
            ]
            try:
                completed = self._worker_runner(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=MAX_ACCURATE_WORKER_TIMEOUT_SECONDS,
                    shell=False,
                    cwd=str(stage),
                )
            except subprocess.TimeoutExpired as exc:
                raise SegmentationValidationError(
                    "Accurate segmentation surface extraction timed out"
                ) from exc
            except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
                raise SegmentationValidationError(
                    "Accurate segmentation surface worker is unavailable"
                ) from exc
            report = _parse_worker_report(completed)
            if output_path.is_symlink() or not output_path.is_file():
                raise SegmentationValidationError(
                    "Accurate segmentation surface worker output is unavailable"
                )
            if output_path.stat().st_size > MAX_ACCURATE_PAYLOAD_BYTES:
                raise SegmentationValidationError(
                    "Accurate segmentation surface worker output exceeds the payload budget"
                )
            try:
                payload = output_path.read_bytes()
            except OSError as exc:
                raise SegmentationValidationError(
                    "Accurate segmentation surface worker output is unreadable"
                ) from exc
        vertex_count, triangle_count, bounds = _validate_accurate_payload(
            payload, label_id=label_id, report=report, runtime=runtime
        )
        surface = SegmentationSurface(
            label_map_id=str(descriptor["label_map_id"]),
            label_id=label_id,
            quality=ACCURATE_SURFACE_QUALITY,
            extraction=ACCURATE_SURFACE_EXTRACTION,
            coordinate_system="patient_lps",
            stride=1,
            vertex_count=vertex_count,
            triangle_count=triangle_count,
            bounds_lps_mm=bounds,
            payload_sha256=sha256(payload).hexdigest(),
            payload=payload,
            schema_version=ACCURATE_SURFACE_SCHEMA_VERSION,
            media_type=ACCURATE_SURFACE_MEDIA_TYPE,
            surface_id=surface_id,
            provenance_sha256=provenance_sha256,
            normal_count=vertex_count,
        )
        self._accurate_cache.clear()
        self._accurate_cache[surface_id] = surface
        return surface

    def _refined_surface(
        self,
        *,
        label_id: int,
        descriptor: dict[str, object],
        reference_surface: SegmentationSurface,
    ) -> SegmentationSurface:
        runtime = self._qualified_runtime()
        _, provenance_sha256, surface_id = _refined_provenance(
            descriptor,
            label_id=label_id,
            runtime=runtime,
            reference_surface=reference_surface,
        )
        cached = self._refined_cache.get(surface_id)
        if cached is not None:
            return cached
        if (
            not self._worker_python
            or len(self._worker_python) > 4096
            or any(ord(character) < 32 for character in self._worker_python)
        ):
            raise SegmentationValidationError("Refined segmentation surface worker Python is invalid")
        worker = Path(self._refinement_worker_script)
        if (
            not worker.is_absolute()
            or worker.suffix != ".py"
            or worker.is_symlink()
            or not worker.is_file()
        ):
            raise SegmentationValidationError(
                "Refined segmentation surface worker script is invalid"
            )
        temp_root = _safe_surface_temp_root(self.data_dir)
        with tempfile.TemporaryDirectory(prefix=".phase6b-", dir=temp_root) as tmp:
            stage = Path(tmp)
            os.chmod(stage, 0o700)
            reference_path = stage / "accurate-reference.vxsf2"
            request_path = stage / "request.json"
            output_path = stage / "refined-surface.vxsf2"
            with reference_path.open("xb") as handle:
                os.chmod(reference_path, 0o600)
                handle.write(reference_surface.payload)
                handle.flush()
                os.fsync(handle.fileno())
            request = {
                "schema_version": ACCURATE_SURFACE_SCHEMA_VERSION,
                "operation": "refine_accurate_surface",
                "refinement": REFINED_SURFACE_REFINEMENT,
                "refinement_algorithm_version": REFINED_SURFACE_ALGORITHM_VERSION,
                "label_id": label_id,
                "reference_surface_id": reference_surface.surface_id,
                "reference_surface_sha256": reference_surface.payload_sha256,
                "array_index_to_patient_lps": _matrix_list(
                    descriptor.get("array_index_to_patient_lps"),
                    "array_index_to_patient_lps",
                ),
                "shape": list(_shape(descriptor["shape"])),
                "expected_runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
                "max_vertices": MAX_ACCURATE_VERTICES,
                "max_triangles": MAX_ACCURATE_TRIANGLES,
                "max_payload_bytes": MAX_ACCURATE_PAYLOAD_BYTES,
                "policy": _refined_policy(),
                "source_label_map": "immutable",
                "clinical_validation": "not_claimed",
            }
            with request_path.open("x", encoding="utf-8") as handle:
                os.chmod(request_path, 0o600)
                handle.write(json.dumps(request, sort_keys=True, separators=(",", ":")))
                handle.flush()
                os.fsync(handle.fileno())
            command = [
                self._worker_python,
                "-I",
                str(worker.resolve(strict=True)),
                "--reference-surface",
                str(reference_path.resolve(strict=True)),
                "--request-json",
                str(request_path.resolve(strict=True)),
                "--output-surface",
                str(output_path.resolve(strict=False)),
            ]
            try:
                completed = self._worker_runner(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=MAX_ACCURATE_WORKER_TIMEOUT_SECONDS,
                    shell=False,
                    cwd=str(stage),
                )
            except subprocess.TimeoutExpired as exc:
                raise SegmentationValidationError(
                    "Refined segmentation surface processing timed out"
                ) from exc
            except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
                raise SegmentationValidationError(
                    "Refined segmentation surface worker is unavailable"
                ) from exc
            report = _parse_refinement_worker_report(completed)
            if output_path.is_symlink() or not output_path.is_file():
                raise SegmentationValidationError(
                    "Refined segmentation surface worker output is unavailable"
                )
            if output_path.stat().st_size > MAX_ACCURATE_PAYLOAD_BYTES:
                raise SegmentationValidationError(
                    "Refined segmentation surface worker output exceeds the payload budget"
                )
            try:
                payload = output_path.read_bytes()
            except OSError as exc:
                raise SegmentationValidationError(
                    "Refined segmentation surface worker output is unreadable"
                ) from exc
        vertex_count, triangle_count, bounds, metrics = _validate_refined_payload(
            payload,
            label_id=label_id,
            report=report,
            runtime=runtime,
            reference_surface=reference_surface,
            descriptor=descriptor,
        )
        surface = SegmentationSurface(
            label_map_id=str(descriptor["label_map_id"]),
            label_id=label_id,
            quality=REFINED_SURFACE_QUALITY,
            extraction=ACCURATE_SURFACE_EXTRACTION,
            coordinate_system="patient_lps",
            stride=1,
            vertex_count=vertex_count,
            triangle_count=triangle_count,
            bounds_lps_mm=bounds,
            payload_sha256=sha256(payload).hexdigest(),
            payload=payload,
            schema_version=ACCURATE_SURFACE_SCHEMA_VERSION,
            media_type=ACCURATE_SURFACE_MEDIA_TYPE,
            surface_id=surface_id,
            provenance_sha256=provenance_sha256,
            normal_count=vertex_count,
            refinement=REFINED_SURFACE_REFINEMENT,
            reference_surface_id=reference_surface.surface_id,
            reference_payload_sha256=reference_surface.payload_sha256,
            topology_repair_count=int(metrics["topology_repair_count"]),
            boundary_edge_count=int(metrics["boundary_edge_count"]),
            nonmanifold_edge_count=int(metrics["nonmanifold_edge_count"]),
            nonmanifold_vertex_count=int(metrics["nonmanifold_vertex_count"]),
            connected_component_count=int(metrics["connected_component_count"]),
            euler_characteristic=int(metrics["euler_characteristic"]),
            safe_compact_repair_count=int(metrics["safe_compact_repair_count"]),
            post_compact_reference_triangle_count=int(
                metrics["post_compact_reference_triangle_count"]
            ),
            reference_boundary_edge_count=int(metrics["reference_boundary_edge_count"]),
            reference_nonmanifold_edge_count=int(
                metrics["reference_nonmanifold_edge_count"]
            ),
            reference_nonmanifold_vertex_count=int(
                metrics["reference_nonmanifold_vertex_count"]
            ),
            reference_connected_component_count=int(
                metrics["reference_connected_component_count"]
            ),
            topology_local_repair_applied=bool(
                metrics["topology_local_repair_applied"]
            ),
            topology_repair_removed_face_count=int(
                metrics["topology_repair_removed_face_count"]
            ),
            topology_repair_removed_face_fraction=float(
                metrics["topology_repair_removed_face_fraction"]
            ),
            topology_repair_removed_area_mm2=float(
                metrics["topology_repair_removed_area_mm2"]
            ),
            topology_repair_removed_area_fraction=float(
                metrics["topology_repair_removed_area_fraction"]
            ),
            topology_repair_initial_displacement_mm=float(
                metrics["topology_repair_initial_displacement_mm"]
            ),
            repaired_reference_triangle_count=int(
                metrics["repaired_reference_triangle_count"]
            ),
            max_displacement_mm=float(metrics["max_displacement_mm"]),
            displacement_limit_mm=float(metrics["displacement_limit_mm"]),
            triangle_retention_ratio=float(metrics["triangle_retention_ratio"]),
            decimation_applied=bool(metrics["decimation_applied"]),
            decimation_cell_size_index=float(metrics["decimation_cell_size_index"]),
        )
        self._refined_cache.clear()
        self._refined_cache[surface_id] = surface
        return surface

    def surface_latest(
        self,
        *,
        label_id: int,
        label_map_id: str | None = None,
        quality: str = DEFAULT_SURFACE_QUALITY,
    ) -> SegmentationSurface:
        if np is None:
            raise SegmentationValidationError("Segmentation surface extraction requires numpy")
        if isinstance(label_id, bool) or not isinstance(label_id, int) or label_id <= 0:
            raise SegmentationValidationError("Segmentation surface label is invalid")
        if (
            quality not in (ACCURATE_SURFACE_QUALITY, REFINED_SURFACE_QUALITY)
            and quality not in SURFACE_QUALITIES
        ):
            raise SegmentationValidationError("Segmentation surface quality is invalid")
        resolved = self._resolve(label_map_id)
        if resolved is None:
            raise SegmentationValidationError(
                "No canonical label map is available for the current study"
            )
        _, descriptor = resolved
        present_labels = _labels(descriptor["present_labels"])
        if label_id not in present_labels:
            raise SegmentationValidationError(
                "Selected segmentation label is not present in the canonical map"
            )
        path = self._artifact_path(str(descriptor["label_map_id"]))
        if path.is_symlink() or not path.is_file():
            raise SegmentationValidationError("Canonical label-map artifact is unavailable")
        try:
            stat = path.stat()
            labels = np.load(path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise SegmentationValidationError("Canonical label-map artifact is unreadable") from exc
        shape = _shape(descriptor["shape"])
        if tuple(labels.shape) != shape or str(labels.dtype) != "uint16":
            raise SegmentationValidationError("Canonical label-map artifact changed")
        if quality in (ACCURATE_SURFACE_QUALITY, REFINED_SURFACE_QUALITY):
            accurate = self._accurate_surface(
                label_id=label_id,
                descriptor=descriptor,
                labels=labels,
                path=path,
            )
            if quality == ACCURATE_SURFACE_QUALITY:
                return accurate
            return self._refined_surface(
                label_id=label_id,
                descriptor=descriptor,
                reference_surface=accurate,
            )

        profile = SURFACE_QUALITIES[quality]
        cache_key = (
            str(descriptor["label_map_id"]),
            label_id,
            quality,
            stat.st_size,
            stat.st_mtime_ns,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        coordinates = np.argwhere(labels == label_id)
        if coordinates.size == 0:
            raise SegmentationValidationError(
                "Selected segmentation label is absent from the canonical artifact"
            )
        minimum = np.min(coordinates, axis=0)
        maximum = np.max(coordinates, axis=0)
        target = int(profile["target_occupied_cells"])
        stride = max(1, int(ceil((len(coordinates) / target) ** (1.0 / 3.0))))
        maximum_triangles = int(profile["max_triangles"])
        while True:
            coarse = _coarse_mask(
                labels,
                label_id=label_id,
                minimum=minimum,
                maximum=maximum,
                stride=stride,
            )
            if _boundary_face_count(coarse) * 2 <= maximum_triangles:
                break
            stride += 1
            if stride > MAX_SURFACE_STRIDE:
                raise SegmentationValidationError(
                    "Selected segmentation surface exceeds the bounded extraction budget"
                )

        payload, vertex_count, triangle_count, bounds = _mesh_payload(
            coarse,
            minimum=minimum,
            maximum=maximum,
            stride=stride,
            affine=_affine(descriptor["array_index_to_patient_lps"]),
            label_id=label_id,
        )
        surface = SegmentationSurface(
            label_map_id=str(descriptor["label_map_id"]),
            label_id=label_id,
            quality=quality,
            extraction=SURFACE_EXTRACTION,
            coordinate_system="patient_lps",
            stride=stride,
            vertex_count=vertex_count,
            triangle_count=triangle_count,
            bounds_lps_mm=bounds,
            payload_sha256=sha256(payload).hexdigest(),
            payload=payload,
        )
        self._cache.clear()
        self._cache[cache_key] = surface
        return surface
