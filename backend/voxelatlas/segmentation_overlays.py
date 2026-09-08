from __future__ import annotations

from dataclasses import dataclass
import colorsys
from math import isfinite
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - numpy is a backend dependency
    np = None  # type: ignore[assignment]

from .dicom_ingestion import DicomStudyRepository
from .dicom_mpr import CanonicalMprService
from .segmentation import SegmentationValidationError
from .segmentation_label_maps import SegmentationLabelMapService


OVERLAY_SCHEMA_VERSION = 1
OVERLAY_MEDIA_TYPE = "application/x-voxelatlas-rgba8"
OVERLAY_SAMPLING = "nearest_neighbor"
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


@dataclass(frozen=True)
class SegmentationOverlayImage:
    plane: str
    index: int
    position_mm: float
    width: int
    height: int
    label_map_id: str
    pixels: bytes


def color_for_label(label_id: int) -> str:
    """Return a stable, visually separated display color for a nonzero label."""
    if isinstance(label_id, bool) or not isinstance(label_id, int) or label_id <= 0:
        raise SegmentationValidationError("Segmentation overlay label is invalid")
    hue = (float(label_id) * 0.618033988749895) % 1.0
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.68, 1.0)
    return "#{:02x}{:02x}{:02x}".format(
        round(red * 255.0),
        round(green * 255.0),
        round(blue * 255.0),
    )


def _matrix(value: object, field: str):
    if np is None:
        raise SegmentationValidationError("Segmentation overlay rendering requires numpy")
    try:
        matrix = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SegmentationValidationError(f"{field} is invalid") from exc
    if (
        matrix.shape != (4, 4)
        or not np.all(np.isfinite(matrix))
        or not np.allclose(matrix[3], np.asarray([0.0, 0.0, 0.0, 1.0]), atol=1e-8)
        or abs(float(np.linalg.det(matrix[:3, :3]))) <= 1e-12
    ):
        raise SegmentationValidationError(f"{field} is invalid")
    return matrix


def _shape(value: object) -> tuple[int, int, int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value)
    ):
        raise SegmentationValidationError("Segmentation overlay shape is invalid")
    return int(value[0]), int(value[1]), int(value[2])


class SegmentationOverlayService:
    """Patient-LPS MPR presentation of an immutable canonical label map."""

    def __init__(
        self,
        *,
        data_dir: Path,
        mpr_service: CanonicalMprService | None = None,
        label_map_service: SegmentationLabelMapService | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.repository = DicomStudyRepository(self.data_dir)
        self.mpr_service = mpr_service or CanonicalMprService(data_dir=self.data_dir)
        self.label_map_service = label_map_service or SegmentationLabelMapService(
            data_dir=self.data_dir
        )
        self._descriptor_cache: dict[str, tuple[dict[str, object], int, int]] = {}
        self._array_cache: dict[str, tuple[object, object, int, int]] = {}

    def _artifact_path(self, label_map_id: str) -> Path:
        return (
            self.data_dir
            / "segmentation"
            / "label-maps"
            / label_map_id
            / "labels.npy"
        )

    def _remember_descriptor(self, descriptor: dict[str, object]) -> None:
        label_map_id = str(descriptor.get("label_map_id") or "")
        path = self._artifact_path(label_map_id)
        try:
            stat = path.stat()
        except OSError:
            return
        self._descriptor_cache[label_map_id] = (
            dict(descriptor),
            stat.st_size,
            stat.st_mtime_ns,
        )

    def _current_study_id(self) -> str:
        manifest = self.repository.latest_manifest()
        study_id = manifest.get("study_id") if isinstance(manifest, dict) else None
        if not isinstance(study_id, str) or not study_id:
            raise SegmentationValidationError("No stored DICOM study is available")
        return study_id

    def _resolve_label_map(
        self,
        *,
        study_id: str,
        label_map_id: str | None,
    ) -> dict[str, object] | None:
        if label_map_id is None:
            maps = self.label_map_service.list(study_id=study_id)
            if not maps:
                return None
            descriptor = dict(maps[0])
            self._remember_descriptor(descriptor)
            return descriptor
        cached = self._descriptor_cache.get(label_map_id)
        if cached is not None:
            descriptor, expected_size, expected_mtime = cached
            path = self._artifact_path(label_map_id)
            try:
                stat = path.stat()
            except OSError:
                stat = None
            if (
                stat is not None
                and stat.st_size == expected_size
                and stat.st_mtime_ns == expected_mtime
                and descriptor.get("source_study_id") == study_id
            ):
                return dict(descriptor)
            self._descriptor_cache.pop(label_map_id, None)
            self._array_cache.pop(label_map_id, None)
        descriptor = self.label_map_service.get(label_map_id)
        if descriptor.get("source_study_id") != study_id:
            raise SegmentationValidationError(
                "Canonical label map does not belong to the current study"
            )
        self._remember_descriptor(descriptor)
        return descriptor

    @staticmethod
    def _validate_descriptor(
        descriptor: dict[str, object], *, study_id: str
    ) -> tuple[tuple[int, int, int], object, tuple[int, ...]]:
        if (
            descriptor.get("state") != "ready"
            or descriptor.get("source_study_id") != study_id
            or descriptor.get("coordinate_system") != "patient_lps"
            or descriptor.get("representation") != "label_map"
            or descriptor.get("artifact_format") != "npy"
            or descriptor.get("dtype") != "uint16"
            or descriptor.get("axis_order") != ["slice", "row", "column"]
        ):
            raise SegmentationValidationError("Canonical label map is not overlay-compatible")
        shape = _shape(descriptor.get("shape"))
        affine = _matrix(
            descriptor.get("array_index_to_patient_lps"),
            "Canonical label-map Patient LPS affine",
        )
        raw_labels = descriptor.get("present_labels")
        if (
            not isinstance(raw_labels, list)
            or not raw_labels
            or raw_labels != sorted(set(raw_labels))
            or raw_labels[0] != 0
            or any(
                isinstance(item, bool) or not isinstance(item, int) or item < 0
                for item in raw_labels
            )
        ):
            raise SegmentationValidationError("Canonical label inventory is invalid")
        return shape, affine, tuple(int(item) for item in raw_labels)

    def descriptor_latest(
        self, *, label_map_id: str | None = None
    ) -> dict[str, object]:
        study_id = self._current_study_id()
        descriptor = self._resolve_label_map(
            study_id=study_id,
            label_map_id=label_map_id,
        )
        if descriptor is None:
            return {
                "schema_version": OVERLAY_SCHEMA_VERSION,
                "ready": False,
                "reason": "no_label_map",
                "source_study_id": study_id,
                "clinical_validation": "not_claimed",
            }
        _, _, labels = self._validate_descriptor(descriptor, study_id=study_id)
        visible_labels = [label for label in labels if label != 0]
        return {
            "schema_version": OVERLAY_SCHEMA_VERSION,
            "ready": True,
            "label_map_id": descriptor["label_map_id"],
            "source_study_id": study_id,
            "source_modality": descriptor["source_modality"],
            "provider_id": descriptor["provider_id"],
            "provider_version": descriptor["provider_version"],
            "model_id": descriptor["model_id"],
            "model_version": descriptor["model_version"],
            "coordinate_system": "patient_lps",
            "sampling": OVERLAY_SAMPLING,
            "present_label_count": len(visible_labels),
            "present_labels": visible_labels,
            "palette": [
                {"label_id": label, "color_hex": color_for_label(label)}
                for label in visible_labels
            ],
            "label_map_sha256": descriptor["artifact_sha256"],
            "clinical_validation": descriptor["clinical_validation"],
        }

    def _load_labels(
        self,
        descriptor: dict[str, object],
        *,
        study_id: str,
    ) -> tuple[object, object]:
        if np is None:
            raise SegmentationValidationError("Segmentation overlay rendering requires numpy")
        shape, affine, _ = self._validate_descriptor(descriptor, study_id=study_id)
        label_map_id = str(descriptor["label_map_id"])
        path = self._artifact_path(label_map_id)
        if path.is_symlink() or not path.is_file():
            raise SegmentationValidationError("Canonical label-map artifact is unavailable")
        try:
            stat = path.stat()
        except OSError as exc:
            raise SegmentationValidationError("Canonical label-map artifact is unavailable") from exc
        cached = self._array_cache.get(label_map_id)
        if (
            cached is not None
            and cached[2] == stat.st_size
            and cached[3] == stat.st_mtime_ns
        ):
            return cached[0], cached[1]
        try:
            labels = np.load(path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise SegmentationValidationError("Canonical label-map artifact is unreadable") from exc
        if tuple(labels.shape) != shape or str(labels.dtype) != "uint16":
            raise SegmentationValidationError("Canonical label-map artifact changed")
        self._array_cache[label_map_id] = (
            labels,
            affine,
            stat.st_size,
            stat.st_mtime_ns,
        )
        return labels, affine

    def render_latest(
        self,
        plane: str,
        *,
        index: int,
        label_map_id: str | None = None,
    ) -> SegmentationOverlayImage:
        if np is None:
            raise SegmentationValidationError("Segmentation overlay rendering requires numpy")
        study_id = self._current_study_id()
        descriptor = self._resolve_label_map(
            study_id=study_id,
            label_map_id=label_map_id,
        )
        if descriptor is None:
            raise SegmentationValidationError("No canonical label map is available for the current study")
        labels, affine = self._load_labels(descriptor, study_id=study_id)

        mpr = self.mpr_service.descriptor_latest()
        plane_descriptor = mpr.get("planes", {}).get(plane)  # type: ignore[union-attr]
        if not isinstance(plane_descriptor, dict):
            raise SegmentationValidationError("Unsupported segmentation overlay plane")
        slice_count = int(plane_descriptor["slice_count"])
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= slice_count:
            raise SegmentationValidationError("Segmentation overlay slice index is outside the patient volume")

        try:
            n = _AXIS_INDEX[str(plane_descriptor["normal_axis"])]
            h = _AXIS_INDEX[str(plane_descriptor["horizontal_axis"])]
            v = _AXIS_INDEX[str(plane_descriptor["vertical_axis"])]
            position = float(plane_descriptor["position_range_mm"][0]) + (
                float(index) * float(plane_descriptor["slice_spacing_mm"])
            )
            horizontal_min, horizontal_max = map(
                float, plane_descriptor["horizontal_range_mm"]
            )
            vertical_min, vertical_max = map(float, plane_descriptor["vertical_range_mm"])
            width = int(plane_descriptor["image_width"])
            height = int(plane_descriptor["image_height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SegmentationValidationError("MPR overlay geometry is invalid") from exc
        if not all(isfinite(item) for item in (position, horizontal_min, horizontal_max, vertical_min, vertical_max)):
            raise SegmentationValidationError("MPR overlay geometry is invalid")

        horizontal = np.linspace(horizontal_min, horizontal_max, width, dtype=np.float64)
        if plane_descriptor.get("vertical_reverse") is True:
            vertical = np.linspace(vertical_max, vertical_min, height, dtype=np.float64)
        else:
            vertical = np.linspace(vertical_min, vertical_max, height, dtype=np.float64)
        horizontal_grid, vertical_grid = np.meshgrid(horizontal, vertical)
        world = np.empty((height, width, 3), dtype=np.float64)
        world[..., n] = position
        world[..., h] = horizontal_grid
        world[..., v] = vertical_grid

        inverse = np.linalg.inv(affine[:3, :3])
        indices = np.einsum("ij,...j->...i", inverse, world - affine[:3, 3])
        nearest = np.rint(indices).astype(np.int64)
        valid = np.ones((height, width), dtype=bool)
        for axis, axis_size in enumerate(labels.shape):
            valid &= indices[..., axis] >= -0.5
            valid &= indices[..., axis] <= float(axis_size) - 0.5
            nearest[..., axis] = np.clip(nearest[..., axis], 0, axis_size - 1)

        sampled = np.zeros((height, width), dtype=np.uint16)
        sampled[valid] = labels[
            nearest[..., 0][valid],
            nearest[..., 1][valid],
            nearest[..., 2][valid],
        ]
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        for label in np.unique(sampled):
            label_id = int(label)
            if label_id == 0:
                continue
            color = color_for_label(label_id)
            rgb = tuple(int(color[offset : offset + 2], 16) for offset in (1, 3, 5))
            mask = sampled == label_id
            rgba[mask, 0] = rgb[0]
            rgba[mask, 1] = rgb[1]
            rgba[mask, 2] = rgb[2]
            rgba[mask, 3] = 255

        return SegmentationOverlayImage(
            plane=plane,
            index=index,
            position_mm=position,
            width=width,
            height=height,
            label_map_id=str(descriptor["label_map_id"]),
            pixels=rgba.tobytes(order="C"),
        )
