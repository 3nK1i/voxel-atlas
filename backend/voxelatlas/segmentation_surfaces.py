from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import ceil, isfinite
from pathlib import Path
import struct

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - numpy is a backend dependency
    np = None  # type: ignore[assignment]

from .dicom_ingestion import DicomStudyRepository
from .segmentation import SegmentationValidationError
from .segmentation_label_maps import SegmentationLabelMapService


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
            if (
                0 <= neighbor[axis] < dimensions[axis]
                and bool(coarse[tuple(neighbor)])
            ):
                continue
            low = np.asarray(minimum, dtype=np.float64) + cell * stride - 0.5
            high = np.minimum(
                low + stride,
                np.asarray(maximum, dtype=np.float64) + 0.5,
            )
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


class SegmentationSurfaceService:
    """Bounded Patient-LPS triangle surfaces derived from immutable labels."""

    def __init__(
        self,
        *,
        data_dir: Path,
        study_repository: object | None = None,
        label_map_service: SegmentationLabelMapService | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.repository = study_repository or DicomStudyRepository(self.data_dir)
        self.label_map_service = label_map_service or SegmentationLabelMapService(
            data_dir=self.data_dir
        )
        self._cache: dict[tuple[str, int, str, int, int], SegmentationSurface] = {}

    def _artifact_path(self, label_map_id: str) -> Path:
        return (
            self.data_dir
            / "segmentation"
            / "label-maps"
            / label_map_id
            / "labels.npy"
        )

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
            raise SegmentationValidationError(
                "Canonical label map is not surface-compatible"
            )
        _shape(descriptor.get("shape"))
        _affine(descriptor.get("array_index_to_patient_lps"))
        _labels(descriptor.get("present_labels"))

    def descriptor_latest(
        self, *, label_map_id: str | None = None
    ) -> dict[str, object]:
        resolved = self._resolve(label_map_id)
        if resolved is None:
            return {
                "schema_version": SURFACE_SCHEMA_VERSION,
                "ready": False,
                "reason": "no_label_map",
                "source_study_id": self._current_study_id(),
                "clinical_validation": "not_claimed",
            }
        study_id, descriptor = resolved
        labels = [label for label in _labels(descriptor["present_labels"]) if label != 0]
        return {
            "schema_version": SURFACE_SCHEMA_VERSION,
            "ready": True,
            "label_map_id": descriptor["label_map_id"],
            "label_map_sha256": descriptor["artifact_sha256"],
            "source_study_id": study_id,
            "source_modality": descriptor["source_modality"],
            "provider_id": descriptor["provider_id"],
            "model_id": descriptor["model_id"],
            "coordinate_system": "patient_lps",
            "surface_endpoint": "/api/studies/latest/segmentation-surfaces/{label_id}",
            "surface_media_type": SURFACE_MEDIA_TYPE,
            "extraction": SURFACE_EXTRACTION,
            "quality_profiles": list(SURFACE_QUALITIES),
            "default_quality": "preview",
            "present_label_count": len(labels),
            "present_labels": labels,
            "source_label_map_immutable": True,
            "clinical_validation": "not_claimed",
        }

    def surface_latest(
        self,
        *,
        label_id: int,
        label_map_id: str | None = None,
        quality: str = "preview",
    ) -> SegmentationSurface:
        if np is None:
            raise SegmentationValidationError("Segmentation surface extraction requires numpy")
        if isinstance(label_id, bool) or not isinstance(label_id, int) or label_id <= 0:
            raise SegmentationValidationError("Segmentation surface label is invalid")
        profile = SURFACE_QUALITIES.get(quality)
        if profile is None:
            raise SegmentationValidationError("Segmentation surface quality is invalid")
        resolved = self._resolve(label_map_id)
        if resolved is None:
            raise SegmentationValidationError(
                "No canonical label map is available for the current study"
            )
        study_id, descriptor = resolved
        del study_id
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
