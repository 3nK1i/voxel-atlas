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
DEFAULT_SURFACE_QUALITY = ACCURATE_SURFACE_QUALITY
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
    os.chmod(segmentation, 0o700)
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
        self._runtime_qualifier = runtime_qualifier or SegmentationSurfaceRuntimeQualifier()
        self._runtime_report: SegmentationSurfaceRuntimeReport | None = None
        self._cache: dict[tuple[str, int, str, int, int], SegmentationSurface] = {}
        self._accurate_cache: dict[str, SegmentationSurface] = {}

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
            "quality_profiles": [ACCURATE_SURFACE_QUALITY, *SURFACE_QUALITIES],
            "default_quality": DEFAULT_SURFACE_QUALITY,
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
        if quality != ACCURATE_SURFACE_QUALITY and quality not in SURFACE_QUALITIES:
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
        if quality == ACCURATE_SURFACE_QUALITY:
            return self._accurate_surface(
                label_id=label_id,
                descriptor=descriptor,
                labels=labels,
                path=path,
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
