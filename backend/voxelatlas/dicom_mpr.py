from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - runtime dependency probe
    np = None  # type: ignore[assignment]

from .dicom_ingestion import DicomStudyRepository


MPR_SCHEMA_VERSION = 1
MAX_MPR_DIMENSION = 1024
MIN_WINDOW_WIDTH = 1e-6


class DicomMprError(ValueError):
    """Base class for safe MPR failures."""


class DicomMprDependencyUnavailable(DicomMprError):
    pass


class DicomMprValidationError(DicomMprError):
    pass


@dataclass(frozen=True)
class MprPlaneImage:
    plane: str
    index: int
    position_mm: float
    width: int
    height: int
    pixels: bytes


@dataclass(frozen=True)
class _VolumeContext:
    volume: object
    shape: tuple[int, int, int]
    modality: str
    intensity_units: str
    value_range: tuple[float, float]
    origin: object
    basis: object
    inverse_basis: object
    bounds_min: object
    bounds_max: object
    world_spacing: object


_PLANE_CONFIG = {
    "axial": {
        "normal_axis": 2,
        "horizontal_axis": 0,
        "vertical_axis": 1,
        "vertical_reverse": False,
        "coordinate": "Z",
        "labels": {"left": "R", "right": "L", "top": "A", "bottom": "P"},
    },
    "coronal": {
        "normal_axis": 1,
        "horizontal_axis": 0,
        "vertical_axis": 2,
        "vertical_reverse": True,
        "coordinate": "Y",
        "labels": {"left": "R", "right": "L", "top": "S", "bottom": "I"},
    },
    "sagittal": {
        "normal_axis": 0,
        "horizontal_axis": 1,
        "vertical_axis": 2,
        "vertical_reverse": True,
        "coordinate": "X",
        "labels": {"left": "A", "right": "P", "top": "S", "bottom": "I"},
    },
}

_AXIS_NAMES = ("x", "y", "z")


def _float_list(value: object, *, length: int, field: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise DicomMprValidationError(f"Patient volume is missing {field}")
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise DicomMprValidationError(f"Patient volume has invalid {field}") from exc
    if not all(isfinite(item) for item in result):
        raise DicomMprValidationError(f"Patient volume has invalid {field}")
    return result


def _positive_int_list(value: object, *, length: int, field: str) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise DicomMprValidationError(f"Patient volume is missing {field}")
    try:
        result = tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise DicomMprValidationError(f"Patient volume has invalid {field}") from exc
    if any(item <= 0 for item in result):
        raise DicomMprValidationError(f"Patient volume has invalid {field}")
    return result


def _axis_samples(minimum: float, maximum: float, nominal_spacing: float) -> tuple[int, float]:
    extent = max(0.0, maximum - minimum)
    if extent <= 1e-9:
        return 1, nominal_spacing
    count = int(round(extent / nominal_spacing)) + 1
    count = max(2, min(MAX_MPR_DIMENSION, count))
    return count, extent / float(count - 1)


class CanonicalMprService:
    """Patient-space MPR extraction from the Phase 3C canonical volume.

    The source volume remains in native [slice, row, column] sampling. Each MPR
    plane is resampled in DICOM patient LPS coordinates so axial/coronal/
    sagittal presentation is independent from the acquisition orientation.
    """

    def __init__(self, *, data_dir: Path):
        self.repository = DicomStudyRepository(data_dir)

    def _latest_manifest_path(self) -> Path:
        if not self.repository.studies_dir.exists():
            raise DicomMprValidationError("No stored DICOM study is available")
        manifests = list(self.repository.studies_dir.glob("*/manifest.json"))
        if not manifests:
            raise DicomMprValidationError("No stored DICOM study is available")
        return max(manifests, key=lambda item: item.stat().st_mtime_ns)

    def _context(self) -> _VolumeContext:
        if np is None:
            raise DicomMprDependencyUnavailable("MPR rendering requires the numpy backend dependency")

        manifest_path = self._latest_manifest_path()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DicomMprValidationError("Stored DICOM study manifest is unreadable") from exc
        if not isinstance(payload, dict):
            raise DicomMprValidationError("Stored DICOM study manifest is invalid")

        descriptor = payload.get("volume")
        if not isinstance(descriptor, dict) or descriptor.get("ready") is not True:
            raise DicomMprValidationError("Canonical patient volume is not ready")
        if descriptor.get("artifact_path") != "derived/volume.npy":
            raise DicomMprValidationError("Canonical patient volume artifact is invalid")

        shape = _positive_int_list(descriptor.get("shape"), length=3, field="shape")
        affine_rows = descriptor.get("array_index_to_patient_lps")
        if not isinstance(affine_rows, (list, tuple)) or len(affine_rows) != 4:
            raise DicomMprValidationError("Patient volume is missing its patient-space affine")
        affine = np.asarray(affine_rows, dtype=np.float64)
        if affine.shape != (4, 4) or not np.all(np.isfinite(affine)):
            raise DicomMprValidationError("Patient volume has an invalid patient-space affine")
        if not np.allclose(affine[3], np.asarray([0.0, 0.0, 0.0, 1.0]), atol=1e-8):
            raise DicomMprValidationError("Patient volume has an invalid patient-space affine")

        basis = affine[:3, :3]
        origin = affine[:3, 3]
        determinant = float(np.linalg.det(basis))
        if not isfinite(determinant) or abs(determinant) < 1e-12:
            raise DicomMprValidationError("Patient volume affine is not invertible")
        inverse_basis = np.linalg.inv(basis)

        artifact_path = manifest_path.parent / "derived" / "volume.npy"
        if not artifact_path.is_file():
            raise DicomMprValidationError("Canonical patient volume artifact is missing")
        try:
            volume = np.load(artifact_path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise DicomMprValidationError("Canonical patient volume artifact is unreadable") from exc
        if volume.ndim != 3 or tuple(int(item) for item in volume.shape) != shape:
            raise DicomMprValidationError("Canonical patient volume artifact shape is invalid")
        if str(volume.dtype) != str(descriptor.get("dtype")):
            raise DicomMprValidationError("Canonical patient volume artifact dtype is invalid")

        corner_indices = np.asarray(
            [
                [s, r, c]
                for s in (0, shape[0] - 1)
                for r in (0, shape[1] - 1)
                for c in (0, shape[2] - 1)
            ],
            dtype=np.float64,
        )
        world_corners = corner_indices @ basis.T + origin
        bounds_min = np.min(world_corners, axis=0)
        bounds_max = np.max(world_corners, axis=0)

        world_spacing = np.empty(3, dtype=np.float64)
        for axis in range(3):
            unit = np.zeros(3, dtype=np.float64)
            unit[axis] = 1.0
            index_per_mm = float(np.linalg.norm(inverse_basis @ unit))
            if not isfinite(index_per_mm) or index_per_mm <= 1e-12:
                raise DicomMprValidationError("Patient volume has invalid effective spatial sampling")
            world_spacing[axis] = 1.0 / index_per_mm

        value_range = _float_list(descriptor.get("value_range"), length=2, field="value range")
        return _VolumeContext(
            volume=volume,
            shape=shape,
            modality=str(descriptor.get("modality") or "").upper(),
            intensity_units=str(descriptor.get("intensity_units") or "modality"),
            value_range=(value_range[0], value_range[1]),
            origin=origin,
            basis=basis,
            inverse_basis=inverse_basis,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            world_spacing=world_spacing,
        )

    def _plane_descriptor(self, context: _VolumeContext, plane: str) -> dict[str, object]:
        if plane not in _PLANE_CONFIG:
            raise DicomMprValidationError("Unsupported MPR plane")
        config = _PLANE_CONFIG[plane]
        n = int(config["normal_axis"])
        h = int(config["horizontal_axis"])
        v = int(config["vertical_axis"])

        slice_count, slice_spacing = _axis_samples(
            float(context.bounds_min[n]),
            float(context.bounds_max[n]),
            float(context.world_spacing[n]),
        )
        width, horizontal_spacing = _axis_samples(
            float(context.bounds_min[h]),
            float(context.bounds_max[h]),
            float(context.world_spacing[h]),
        )
        height, vertical_spacing = _axis_samples(
            float(context.bounds_min[v]),
            float(context.bounds_max[v]),
            float(context.world_spacing[v]),
        )
        return {
            "plane": plane,
            "normal_axis": _AXIS_NAMES[n],
            "horizontal_axis": _AXIS_NAMES[h],
            "vertical_axis": _AXIS_NAMES[v],
            "coordinate": config["coordinate"],
            "slice_count": slice_count,
            "slice_spacing_mm": slice_spacing,
            "position_range_mm": [float(context.bounds_min[n]), float(context.bounds_max[n])],
            "image_width": width,
            "image_height": height,
            "pixel_spacing_mm": [vertical_spacing, horizontal_spacing],
            "horizontal_range_mm": [float(context.bounds_min[h]), float(context.bounds_max[h])],
            "vertical_range_mm": [float(context.bounds_min[v]), float(context.bounds_max[v])],
            "vertical_reverse": bool(config["vertical_reverse"]),
            "labels": dict(config["labels"]),
        }

    def descriptor_latest(self) -> dict[str, object]:
        context = self._context()
        if context.modality == "CT":
            window_width = 400.0
            window_level = 40.0
        else:
            low, high = context.value_range
            window_width = max(float(high - low), 1.0)
            window_level = float((high + low) / 2.0)

        center = [
            float((context.bounds_min[axis] + context.bounds_max[axis]) / 2.0)
            for axis in range(3)
        ]
        return {
            "schema_version": MPR_SCHEMA_VERSION,
            "ready": True,
            "modality": context.modality,
            "intensity_units": context.intensity_units,
            "value_range": list(context.value_range),
            "default_window": {"width": window_width, "level": window_level},
            "patient_bounds_lps_mm": {
                _AXIS_NAMES[axis]: [
                    float(context.bounds_min[axis]),
                    float(context.bounds_max[axis]),
                ]
                for axis in range(3)
            },
            "crosshair_lps_mm": center,
            "planes": {
                plane: self._plane_descriptor(context, plane)
                for plane in ("axial", "coronal", "sagittal")
            },
        }

    def render_latest(
        self,
        plane: str,
        *,
        index: int,
        window: float,
        level: float,
    ) -> MprPlaneImage:
        if np is None:
            raise DicomMprDependencyUnavailable("MPR rendering requires the numpy backend dependency")
        if not isfinite(window) or window <= MIN_WINDOW_WIDTH:
            raise DicomMprValidationError("MPR window width must be greater than zero")
        if not isfinite(level):
            raise DicomMprValidationError("MPR window level is invalid")

        context = self._context()
        descriptor = self._plane_descriptor(context, plane)
        slice_count = int(descriptor["slice_count"])
        if index < 0 or index >= slice_count:
            raise DicomMprValidationError("MPR slice index is outside the available patient volume")

        config = _PLANE_CONFIG[plane]
        n = int(config["normal_axis"])
        h = int(config["horizontal_axis"])
        v = int(config["vertical_axis"])
        position_min, _ = descriptor["position_range_mm"]  # type: ignore[misc]
        position = float(position_min) + float(index) * float(descriptor["slice_spacing_mm"])

        horizontal_min, horizontal_max = descriptor["horizontal_range_mm"]  # type: ignore[misc]
        vertical_min, vertical_max = descriptor["vertical_range_mm"]  # type: ignore[misc]
        width = int(descriptor["image_width"])
        height = int(descriptor["image_height"])

        horizontal = np.linspace(float(horizontal_min), float(horizontal_max), width, dtype=np.float64)
        if bool(descriptor["vertical_reverse"]):
            vertical = np.linspace(float(vertical_max), float(vertical_min), height, dtype=np.float64)
        else:
            vertical = np.linspace(float(vertical_min), float(vertical_max), height, dtype=np.float64)
        horizontal_grid, vertical_grid = np.meshgrid(horizontal, vertical)

        world = np.empty((height, width, 3), dtype=np.float64)
        world[..., n] = position
        world[..., h] = horizontal_grid
        world[..., v] = vertical_grid
        delta = world - context.origin
        indices = np.einsum("ij,...j->...i", context.inverse_basis, delta)

        valid = np.ones((height, width), dtype=bool)
        for axis, axis_size in enumerate(context.shape):
            valid &= indices[..., axis] >= -1e-6
            valid &= indices[..., axis] <= float(axis_size - 1) + 1e-6
            indices[..., axis] = np.clip(indices[..., axis], 0.0, float(axis_size - 1))

        i0 = np.floor(indices).astype(np.int64)
        i1 = np.empty_like(i0)
        fractions = indices - i0
        for axis, axis_size in enumerate(context.shape):
            i1[..., axis] = np.minimum(i0[..., axis] + 1, axis_size - 1)

        s0, r0, c0 = i0[..., 0], i0[..., 1], i0[..., 2]
        s1, r1, c1 = i1[..., 0], i1[..., 1], i1[..., 2]
        fs, fr, fc = fractions[..., 0], fractions[..., 1], fractions[..., 2]
        volume = context.volume

        c000 = np.asarray(volume[s0, r0, c0], dtype=np.float64)
        c001 = np.asarray(volume[s0, r0, c1], dtype=np.float64)
        c010 = np.asarray(volume[s0, r1, c0], dtype=np.float64)
        c011 = np.asarray(volume[s0, r1, c1], dtype=np.float64)
        c100 = np.asarray(volume[s1, r0, c0], dtype=np.float64)
        c101 = np.asarray(volume[s1, r0, c1], dtype=np.float64)
        c110 = np.asarray(volume[s1, r1, c0], dtype=np.float64)
        c111 = np.asarray(volume[s1, r1, c1], dtype=np.float64)

        c00 = c000 * (1.0 - fc) + c001 * fc
        c01 = c010 * (1.0 - fc) + c011 * fc
        c10 = c100 * (1.0 - fc) + c101 * fc
        c11 = c110 * (1.0 - fc) + c111 * fc
        c0 = c00 * (1.0 - fr) + c01 * fr
        c1 = c10 * (1.0 - fr) + c11 * fr
        values = c0 * (1.0 - fs) + c1 * fs

        low = float(level) - float(window) / 2.0
        scaled = np.clip((values - low) / float(window), 0.0, 1.0)
        gray = np.rint(scaled * 255.0).astype(np.uint8)
        gray[~valid] = 0

        return MprPlaneImage(
            plane=plane,
            index=index,
            position_mm=position,
            width=width,
            height=height,
            pixels=gray.tobytes(order="C"),
        )
