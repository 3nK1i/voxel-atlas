from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Callable

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - exercised by runtime dependency probe
    np = None  # type: ignore[assignment]

from .dicom_ingestion import (
    DicomStudyRepository,
    _geometry_from_manifest_series,
    _manifest_to_public,
)


VOLUME_SCHEMA_VERSION = 1
STUDY_MANIFEST_SCHEMA_VERSION = 3
MAX_CANONICAL_VOLUME_BYTES = 2 * 1024 * 1024 * 1024


class DicomVolumeError(ValueError):
    """Base class for safe, user-facing patient-volume construction failures."""


class DicomVolumeDependencyUnavailable(DicomVolumeError):
    pass


class DicomVolumeValidationError(DicomVolumeError):
    pass


class DicomPixelDecodeError(DicomVolumeError):
    pass


@dataclass(frozen=True)
class DecodedDicomSlice:
    pixels: object
    rescale_slope: float = 1.0
    rescale_intercept: float = 0.0


@dataclass(frozen=True)
class CanonicalVolumeDescriptor:
    schema_version: int
    ready: bool
    created_at_utc: str
    source_series_uid: str
    source_instance_count: int
    modality: str
    dtype: str
    shape: tuple[int, int, int]
    axis_order: tuple[str, str, str]
    spacing_mm: tuple[float, float, float]
    origin_patient_lps_mm: tuple[float, float, float]
    array_index_to_patient_lps: tuple[
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
    ]
    intensity_units: str
    value_range: tuple[float, float]
    artifact_path: str
    metadata_path: str

    def manifest_dict(self) -> dict[str, object]:
        return asdict(self)

    def public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "ready": self.ready,
            "created_at_utc": self.created_at_utc,
            "source_series_uid": self.source_series_uid,
            "source_instance_count": self.source_instance_count,
            "modality": self.modality,
            "dtype": self.dtype,
            "shape": list(self.shape),
            "axis_order": list(self.axis_order),
            "spacing_mm": list(self.spacing_mm),
            "origin_patient_lps_mm": list(self.origin_patient_lps_mm),
            "array_index_to_patient_lps": [list(row) for row in self.array_index_to_patient_lps],
            "intensity_units": self.intensity_units,
            "value_range": list(self.value_range),
        }


PixelReader = Callable[[Path], DecodedDicomSlice]


def read_dicom_pixels(path: Path) -> DecodedDicomSlice:
    if np is None:
        raise DicomVolumeDependencyUnavailable(
            "Patient volume construction requires the numpy backend dependency"
        )
    try:
        import pydicom
        from pydicom.errors import InvalidDicomError
    except ModuleNotFoundError as exc:
        raise DicomVolumeDependencyUnavailable(
            "Patient volume construction requires the pydicom backend dependency"
        ) from exc

    try:
        dataset = pydicom.dcmread(str(path), force=False)
    except (InvalidDicomError, OSError, ValueError) as exc:
        raise DicomPixelDecodeError("A qualified DICOM slice could not be reopened") from exc

    try:
        from pydicom.pixels import apply_modality_lut

        pixels = np.asarray(apply_modality_lut(dataset.pixel_array, dataset))
    except Exception as exc:  # Decoder plugins raise several backend-specific exception types.
        raise DicomPixelDecodeError(
            "DICOM pixel data could not be decoded; the transfer syntax may require decoder support"
        ) from exc

    if pixels.ndim != 2:
        raise DicomVolumeValidationError(
            "Only single-frame monochrome CT/MR slices are qualified for canonical volume construction"
        )

    # pydicom's modality LUT applies either ModalityLUTSequence or the standard
    # RescaleSlope/RescaleIntercept transform when present. The construction
    # service therefore receives physical/modality values directly here.
    return DecodedDicomSlice(
        pixels=pixels,
        rescale_slope=1.0,
        rescale_intercept=0.0,
    )


def _float_tuple(value: object, expected: int, field: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != expected:
        raise DicomVolumeValidationError(f"Qualified geometry is missing {field}")
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise DicomVolumeValidationError(f"Qualified geometry has invalid {field}") from exc
    if not all(isfinite(item) for item in result):
        raise DicomVolumeValidationError(f"Qualified geometry has invalid {field}")
    return result


def _int_tuple(value: object, expected: int, field: str) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != expected:
        raise DicomVolumeValidationError(f"Qualified geometry is missing {field}")
    try:
        result = tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise DicomVolumeValidationError(f"Qualified geometry has invalid {field}") from exc
    if any(item <= 0 for item in result):
        raise DicomVolumeValidationError(f"Qualified geometry has invalid {field}")
    return result


def _volume_affine(
    *,
    origin: tuple[float, float, float],
    row_direction: tuple[float, float, float],
    column_direction: tuple[float, float, float],
    slice_normal: tuple[float, float, float],
    row_spacing: float,
    column_spacing: float,
    slice_spacing: float,
) -> tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]:
    # NumPy volume order is [slice, row, column]. DICOM's first IOP vector
    # advances with the column index, while the second advances with the row index.
    slice_axis = tuple(component * slice_spacing for component in slice_normal)
    row_axis = tuple(component * row_spacing for component in column_direction)
    column_axis = tuple(component * column_spacing for component in row_direction)
    return (
        (slice_axis[0], row_axis[0], column_axis[0], origin[0]),
        (slice_axis[1], row_axis[1], column_axis[1], origin[1]),
        (slice_axis[2], row_axis[2], column_axis[2], origin[2]),
        (0.0, 0.0, 0.0, 1.0),
    )


def _ensure_manifest_geometry(payload: dict[str, object]) -> str | None:
    ready_series: list[tuple[int, str]] = []
    series_items = payload.get("series", [])
    if not isinstance(series_items, list):
        return None
    for raw in series_items:
        if not isinstance(raw, dict):
            continue
        geometry = _geometry_from_manifest_series(raw)
        raw["geometry"] = geometry.manifest_dict()
        series_uid = str(raw.get("series_instance_uid") or "").strip()
        try:
            instance_count = int(raw.get("instance_count") or 0)
        except (TypeError, ValueError):
            instance_count = 0
        if geometry.reconstruction_ready and series_uid:
            ready_series.append((instance_count, series_uid))
    if not ready_series:
        payload["reconstruction_ready"] = False
        payload["reconstruction_series_uid"] = None
        return None
    selected = max(ready_series, key=lambda item: (item[0], item[1]))[1]
    requested = str(payload.get("reconstruction_series_uid") or "").strip()
    if requested and any(uid == requested for _, uid in ready_series):
        selected = requested
    payload["reconstruction_ready"] = True
    payload["reconstruction_series_uid"] = selected
    payload["schema_version"] = max(int(payload.get("schema_version") or 0), 2)
    return selected


class CanonicalVolumeService:
    def __init__(
        self,
        *,
        data_dir: Path,
        pixel_reader: PixelReader = read_dicom_pixels,
        max_volume_bytes: int = MAX_CANONICAL_VOLUME_BYTES,
    ):
        self.repository = DicomStudyRepository(data_dir)
        self.pixel_reader = pixel_reader
        self.max_volume_bytes = max_volume_bytes

    def _latest_manifest_path(self) -> Path:
        studies_dir = self.repository.studies_dir
        if not studies_dir.exists():
            raise DicomVolumeValidationError("No stored DICOM study is available")
        manifests = list(studies_dir.glob("*/manifest.json"))
        if not manifests:
            raise DicomVolumeValidationError("No stored DICOM study is available")
        return max(manifests, key=lambda item: item.stat().st_mtime_ns)

    def build_latest(self) -> dict[str, object]:
        if np is None:
            raise DicomVolumeDependencyUnavailable(
                "Patient volume construction requires the numpy backend dependency"
            )

        manifest_path = self._latest_manifest_path()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DicomVolumeValidationError("Stored DICOM study manifest is unreadable") from exc
        if not isinstance(payload, dict):
            raise DicomVolumeValidationError("Stored DICOM study manifest is invalid")

        existing = payload.get("volume")
        if isinstance(existing, dict) and existing.get("ready") is True:
            artifact = existing.get("artifact_path")
            metadata = existing.get("metadata_path")
            artifact_path = manifest_path.parent / "derived" / "volume.npy"
            metadata_path = manifest_path.parent / "derived" / "volume.json"
            if (
                artifact == "derived/volume.npy"
                and metadata == "derived/volume.json"
                and artifact_path.is_file()
                and metadata_path.is_file()
            ):
                try:
                    existing_array = np.load(artifact_path, mmap_mode="r", allow_pickle=False)
                    expected_shape = tuple(int(item) for item in existing.get("shape", []))
                    if (
                        existing_array.ndim == 3
                        and tuple(existing_array.shape) == expected_shape
                        and str(existing_array.dtype) == str(existing.get("dtype"))
                    ):
                        return _manifest_to_public(payload)
                except (OSError, ValueError, TypeError):
                    pass
            payload.pop("volume", None)

        series_uid = _ensure_manifest_geometry(payload)
        if not series_uid:
            raise DicomVolumeValidationError(
                "DICOM geometry must be reconstruction-ready before building the patient volume"
            )

        series_payload = next(
            (
                item
                for item in payload.get("series", [])
                if isinstance(item, dict) and str(item.get("series_instance_uid") or "") == series_uid
            ),
            None,
        )
        if not isinstance(series_payload, dict):
            raise DicomVolumeValidationError("The reconstruction-qualified DICOM series is unavailable")
        geometry = series_payload.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("reconstruction_ready") is not True:
            raise DicomVolumeValidationError("The selected DICOM series geometry is not reconstruction-ready")

        dimensions = _int_tuple(geometry.get("dimensions"), 3, "dimensions")
        rows, columns, slice_count = dimensions
        geometry_spacing = _float_tuple(geometry.get("spacing_mm"), 3, "spacing")
        row_spacing, column_spacing, slice_spacing = geometry_spacing
        if row_spacing <= 0 or column_spacing <= 0 or slice_spacing <= 0:
            raise DicomVolumeValidationError("Qualified geometry has invalid spacing")
        origin = _float_tuple(geometry.get("origin_patient_mm"), 3, "origin")
        row_direction = _float_tuple(geometry.get("row_direction"), 3, "row direction")
        column_direction = _float_tuple(geometry.get("column_direction"), 3, "column direction")
        slice_normal = _float_tuple(geometry.get("slice_normal"), 3, "slice normal")

        ordered = geometry.get("ordered_instance_filenames")
        if not isinstance(ordered, (list, tuple)) or len(ordered) != slice_count:
            raise DicomVolumeValidationError(
                "Qualified geometry does not contain a complete ordered slice list"
            )
        ordered_names = tuple(str(item) for item in ordered)
        if (
            any(not name or Path(name).name != name for name in ordered_names)
            or len(set(ordered_names)) != len(ordered_names)
        ):
            raise DicomVolumeValidationError("Qualified geometry contains an invalid stored slice name")

        source_hashes: dict[str, str] = {}
        for item in series_payload.get("instances", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("stored_filename") or "")
            digest = str(item.get("sha256") or "").lower()
            if name and len(digest) == 64 and all(char in "0123456789abcdef" for char in digest):
                source_hashes[name] = digest
        if any(name not in source_hashes for name in ordered_names):
            raise DicomVolumeValidationError(
                "Qualified DICOM source provenance is incomplete for volume construction"
            )

        expected_bytes = slice_count * rows * columns * 4
        if expected_bytes > self.max_volume_bytes:
            raise DicomVolumeValidationError(
                "The qualified DICOM series is too large for the configured canonical volume limit"
            )

        study_dir = manifest_path.parent
        derived_dir = study_dir / "derived"
        derived_dir.mkdir(parents=True, exist_ok=True)
        array_path = derived_dir / "volume.npy"
        array_tmp = derived_dir / "volume.npy.tmp"
        metadata_path = derived_dir / "volume.json"
        metadata_tmp = derived_dir / "volume.json.tmp"
        manifest_tmp = study_dir / "manifest.json.tmp"

        try:
            volume = np.empty((slice_count, rows, columns), dtype=np.float32)
        except MemoryError as exc:
            raise DicomVolumeValidationError(
                "The qualified DICOM series is too large to construct in available memory"
            ) from exc
        value_min = float("inf")
        value_max = float("-inf")

        try:
            for index, stored_name in enumerate(ordered_names):
                source_path = study_dir / stored_name
                if not source_path.is_file():
                    raise DicomVolumeValidationError(
                        "A qualified DICOM source slice is missing from the stored study"
                    )
                digest = sha256()
                with source_path.open("rb") as source_handle:
                    while True:
                        chunk = source_handle.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                if digest.hexdigest() != source_hashes[stored_name]:
                    raise DicomVolumeValidationError(
                        "Qualified DICOM source integrity check failed before volume construction"
                    )
                try:
                    decoded = self.pixel_reader(source_path)
                except DicomVolumeError:
                    raise
                except Exception as exc:
                    raise DicomPixelDecodeError("DICOM pixel data could not be decoded") from exc
                pixels = np.asarray(decoded.pixels)
                if pixels.ndim != 2 or pixels.shape != (rows, columns):
                    raise DicomVolumeValidationError(
                        "Decoded DICOM pixel matrix does not match the qualified series geometry"
                    )
                slope = float(decoded.rescale_slope)
                intercept = float(decoded.rescale_intercept)
                if not isfinite(slope) or not isfinite(intercept):
                    raise DicomVolumeValidationError("DICOM intensity rescale metadata is invalid")
                converted = pixels.astype(np.float32, copy=False)
                if slope != 1.0:
                    converted = converted * np.float32(slope)
                if intercept != 0.0:
                    converted = converted + np.float32(intercept)
                if not np.all(np.isfinite(converted)):
                    raise DicomVolumeValidationError(
                        "Decoded DICOM pixel data contains non-finite intensity values"
                    )
                volume[index] = converted
                value_min = min(value_min, float(np.min(converted)))
                value_max = max(value_max, float(np.max(converted)))

            affine = _volume_affine(
                origin=origin,  # type: ignore[arg-type]
                row_direction=row_direction,  # type: ignore[arg-type]
                column_direction=column_direction,  # type: ignore[arg-type]
                slice_normal=slice_normal,  # type: ignore[arg-type]
                row_spacing=row_spacing,
                column_spacing=column_spacing,
                slice_spacing=slice_spacing,
            )
            descriptor = CanonicalVolumeDescriptor(
                schema_version=VOLUME_SCHEMA_VERSION,
                ready=True,
                created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                source_series_uid=series_uid,
                source_instance_count=slice_count,
                modality=str(series_payload.get("modality") or "").upper(),
                dtype="float32",
                shape=(slice_count, rows, columns),
                axis_order=("slice", "row", "column"),
                spacing_mm=(slice_spacing, row_spacing, column_spacing),
                origin_patient_lps_mm=origin,  # type: ignore[arg-type]
                array_index_to_patient_lps=affine,
                intensity_units=(
                    "HU" if str(series_payload.get("modality") or "").upper() == "CT" else "modality"
                ),
                value_range=(value_min, value_max),
                artifact_path="derived/volume.npy",
                metadata_path="derived/volume.json",
            )

            with array_tmp.open("wb") as handle:
                np.save(handle, volume, allow_pickle=False)
                handle.flush()
            metadata_tmp.write_text(
                json.dumps(descriptor.manifest_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            array_tmp.replace(array_path)
            metadata_tmp.replace(metadata_path)

            payload["schema_version"] = max(
                int(payload.get("schema_version") or 0),
                STUDY_MANIFEST_SCHEMA_VERSION,
            )
            payload["volume"] = descriptor.manifest_dict()
            manifest_tmp.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            manifest_tmp.replace(manifest_path)
        except OSError as exc:
            array_tmp.unlink(missing_ok=True)
            metadata_tmp.unlink(missing_ok=True)
            manifest_tmp.unlink(missing_ok=True)
            raise DicomVolumeError("Patient volume could not be persisted") from exc
        except Exception:
            array_tmp.unlink(missing_ok=True)
            metadata_tmp.unlink(missing_ok=True)
            manifest_tmp.unlink(missing_ok=True)
            raise

        return _manifest_to_public(payload)
