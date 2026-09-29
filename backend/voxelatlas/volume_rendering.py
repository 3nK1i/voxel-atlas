from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite, prod
from pathlib import Path
from uuid import uuid4

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - numpy is a Phase 3C runtime dependency
    np = None  # type: ignore[assignment]

from .dicom_ingestion import DicomStudyRepository


VOLUME_RENDERING_SCHEMA_VERSION = 1
STUDY_MANIFEST_SCHEMA_VERSION = 5
DEFAULT_MAX_RENDERING_BYTES = 512 * 1024 * 1024
CANONICAL_AXIS_ORDER = ("slice", "row", "column")
TEXTURE_AXIS_ORDER = ("column", "row", "slice")
RENDERING_ENCODING = "linear_uint16_rg8"
RENDERING_MEDIA_TYPE = "application/x-voxelatlas-volume-rg8"


class VolumeRenderingError(ValueError):
    """Base class for safe direct-volume presentation failures."""


class VolumeRenderingDependencyUnavailable(VolumeRenderingError):
    pass


class VolumeRenderingValidationError(VolumeRenderingError):
    pass


@dataclass(frozen=True)
class CanonicalVolumeRenderingSource:
    manifest_path: Path
    study_dir: Path
    volume_path: Path
    source_series_uid: str
    modality: str
    dtype: str
    shape: tuple[int, int, int]
    spacing_mm: tuple[float, float, float]
    array_index_to_patient_lps: tuple[
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
    ]
    intensity_units: str
    value_range: tuple[float, float]
    volume_created_at_utc: str
    source_descriptor_sha256: str
    volume: object


@dataclass(frozen=True)
class VolumeRenderingArtifactDescriptor:
    schema_version: int
    ready: bool
    created_at_utc: str
    revision: str
    source_series_uid: str
    source_volume_descriptor_sha256: str
    source_volume_created_at_utc: str
    source_modality: str
    source_intensity_units: str
    source_value_range: tuple[float, float]
    source_shape: tuple[int, int, int]
    source_axis_order: tuple[str, str, str]
    spacing_mm: tuple[float, float, float]
    array_index_to_patient_lps: tuple[
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
    ]
    texture_dimensions: tuple[int, int, int]
    texture_axis_order: tuple[str, str, str]
    texture_coordinate_to_patient_lps: tuple[
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
    ]
    patient_bounds_lps_mm: tuple[float, float, float, float, float, float]
    encoding: str
    component_type: str
    component_order: tuple[str, str]
    bytes_per_voxel: int
    decode_offset: float
    decode_scale: float
    byte_length: int
    artifact_sha256: str
    artifact_path: str
    metadata_path: str

    def manifest_dict(self) -> dict[str, object]:
        return asdict(self)

    def public_dict(self) -> dict[str, object]:
        public = {
            key: value
            for key, value in self.manifest_dict().items()
            if key not in {"artifact_path", "metadata_path"}
        }
        return json.loads(json.dumps(public))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, message: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VolumeRenderingValidationError(message) from exc
    if not isinstance(payload, dict):
        raise VolumeRenderingValidationError(message)
    return payload


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _volume_identity(volume: dict[str, object]) -> str:
    canonical = json.dumps(
        volume,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _valid_sha256(value: str) -> bool:
    return (
        len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _float_tuple(value: object, expected: int, field: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != expected:
        raise VolumeRenderingValidationError(f"Canonical patient volume is missing {field}")
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise VolumeRenderingValidationError(
            f"Canonical patient volume has invalid {field}"
        ) from exc
    if not all(isfinite(item) for item in result):
        raise VolumeRenderingValidationError(f"Canonical patient volume has invalid {field}")
    return result


def _int_tuple(value: object, expected: int, field: str) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != expected:
        raise VolumeRenderingValidationError(f"Canonical patient volume is missing {field}")
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        raise VolumeRenderingValidationError(f"Canonical patient volume has invalid {field}")
    result = tuple(value)
    if any(item <= 0 for item in result):
        raise VolumeRenderingValidationError(f"Canonical patient volume has invalid {field}")
    return result


def _texture_transform(
    affine: object,
    shape: tuple[int, int, int],
) -> tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]:
    # Texture coordinates are [column, row, slice] in [0, 1]. The canonical
    # affine maps voxel centres in [slice, row, column], so the proxy box starts
    # half a voxel before the first centre and ends half a voxel after the last.
    source = np.asarray(affine, dtype=np.float64)
    basis = source[:3, :3]
    origin = source[:3, 3] - 0.5 * np.sum(basis, axis=1)
    slices, rows, columns = shape
    result = np.eye(4, dtype=np.float64)
    result[:3, 0] = basis[:, 2] * columns
    result[:3, 1] = basis[:, 1] * rows
    result[:3, 2] = basis[:, 0] * slices
    result[:3, 3] = origin
    return tuple(tuple(float(item) for item in row) for row in result)  # type: ignore[return-value]


def _patient_bounds(transform: object) -> tuple[float, float, float, float, float, float]:
    matrix = np.asarray(transform, dtype=np.float64)
    corners = np.asarray(
        [[x, y, z] for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)],
        dtype=np.float64,
    )
    patient = corners @ matrix[:3, :3].T + matrix[:3, 3]
    minimum = np.min(patient, axis=0)
    maximum = np.max(patient, axis=0)
    return tuple(  # type: ignore[return-value]
        float(item) for item in np.concatenate((minimum, maximum))
    )


class VolumeRenderingService:
    """Build and transport a GPU-ready derivative of the canonical patient volume."""

    def __init__(
        self,
        *,
        data_dir: Path,
        max_rendering_bytes: int = DEFAULT_MAX_RENDERING_BYTES,
        chunk_slices: int = 8,
    ):
        if max_rendering_bytes <= 0:
            raise ValueError("max_rendering_bytes must be greater than zero")
        if chunk_slices <= 0:
            raise ValueError("chunk_slices must be greater than zero")
        self.repository = DicomStudyRepository(data_dir)
        self.max_rendering_bytes = max_rendering_bytes
        self.chunk_slices = chunk_slices

    def _latest_manifest_path(self) -> Path:
        if not self.repository.studies_dir.exists():
            raise VolumeRenderingValidationError("No stored DICOM study is available")
        manifests = list(self.repository.studies_dir.glob("*/manifest.json"))
        if not manifests:
            raise VolumeRenderingValidationError("No stored DICOM study is available")
        return max(manifests, key=lambda item: item.stat().st_mtime_ns)

    def _load_latest(self) -> tuple[Path, dict[str, object], CanonicalVolumeRenderingSource]:
        manifest_path = self._latest_manifest_path()
        payload = _load_json(manifest_path, "Stored DICOM study manifest is unreadable")
        return manifest_path, payload, self._load_source(manifest_path, payload)

    def source_latest(self) -> CanonicalVolumeRenderingSource:
        """Return the validated canonical source without preparing a rendering derivative."""
        _, _, source = self._load_latest()
        return source

    def _load_source(
        self,
        manifest_path: Path,
        payload: dict[str, object],
    ) -> CanonicalVolumeRenderingSource:
        if np is None:
            raise VolumeRenderingDependencyUnavailable(
                "Direct volume rendering requires the numpy backend dependency"
            )

        descriptor = payload.get("volume")
        if not isinstance(descriptor, dict) or descriptor.get("ready") is not True:
            raise VolumeRenderingValidationError(
                "Canonical patient volume must be ready before direct volume rendering"
            )
        if descriptor.get("artifact_path") != "derived/volume.npy":
            raise VolumeRenderingValidationError(
                "Canonical patient volume has an invalid artifact contract"
            )
        if descriptor.get("metadata_path") != "derived/volume.json":
            raise VolumeRenderingValidationError(
                "Canonical patient volume has an invalid metadata contract"
            )

        study_dir = manifest_path.parent
        volume_path = study_dir / "derived" / "volume.npy"
        metadata_path = study_dir / "derived" / "volume.json"
        if not volume_path.is_file() or not metadata_path.is_file():
            raise VolumeRenderingValidationError("Canonical patient volume artifacts are missing")
        metadata = _load_json(metadata_path, "Canonical patient volume metadata is unreadable")
        if metadata != descriptor:
            raise VolumeRenderingValidationError(
                "Canonical patient volume metadata does not match the study manifest"
            )

        source_series_uid = str(descriptor.get("source_series_uid") or "").strip()
        modality = str(descriptor.get("modality") or "").strip().upper()
        dtype = str(descriptor.get("dtype") or "").strip()
        intensity_units = str(descriptor.get("intensity_units") or "").strip()
        created_at = str(descriptor.get("created_at_utc") or "").strip()
        if not all((source_series_uid, modality, dtype, intensity_units, created_at)):
            raise VolumeRenderingValidationError(
                "Canonical patient volume provenance is incomplete"
            )
        if modality not in {"CT", "MR"}:
            raise VolumeRenderingValidationError(
                "Direct volume rendering currently supports qualified CT or MR volumes"
            )
        if modality == "CT" and intensity_units != "HU":
            raise VolumeRenderingValidationError("Qualified CT volume must preserve HU semantics")
        if modality == "MR" and intensity_units != "modality":
            raise VolumeRenderingValidationError(
                "Qualified MR volume must preserve modality intensity semantics"
            )
        if dtype != "float32":
            raise VolumeRenderingValidationError(
                "Canonical patient volume dtype is unsupported for direct volume rendering"
            )
        if descriptor.get("axis_order") not in (list(CANONICAL_AXIS_ORDER), CANONICAL_AXIS_ORDER):
            raise VolumeRenderingValidationError(
                "Canonical patient volume axis order is unsupported"
            )

        shape = _int_tuple(descriptor.get("shape"), 3, "shape")
        spacing = _float_tuple(descriptor.get("spacing_mm"), 3, "spacing")
        if any(item <= 0 for item in spacing):
            raise VolumeRenderingValidationError("Canonical patient volume has invalid spacing")
        value_range = _float_tuple(descriptor.get("value_range"), 2, "value range")
        if value_range[0] > value_range[1]:
            raise VolumeRenderingValidationError(
                "Canonical patient volume has invalid value range"
            )

        affine_raw = descriptor.get("array_index_to_patient_lps")
        if not isinstance(affine_raw, (list, tuple)) or len(affine_raw) != 4:
            raise VolumeRenderingValidationError(
                "Canonical patient volume is missing patient LPS affine"
            )
        affine = tuple(_float_tuple(row, 4, "patient LPS affine") for row in affine_raw)
        affine_array = np.asarray(affine, dtype=np.float64)
        if not np.allclose(affine_array[3], [0.0, 0.0, 0.0, 1.0], atol=1e-8):
            raise VolumeRenderingValidationError(
                "Canonical patient volume has invalid patient LPS affine"
            )
        determinant = float(np.linalg.det(affine_array[:3, :3]))
        if not isfinite(determinant) or abs(determinant) <= 1e-12:
            raise VolumeRenderingValidationError(
                "Canonical patient volume patient LPS affine is singular"
            )

        try:
            volume = np.load(volume_path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise VolumeRenderingValidationError(
                "Canonical patient volume array is unreadable"
            ) from exc
        if volume.ndim != 3 or tuple(int(item) for item in volume.shape) != shape:
            raise VolumeRenderingValidationError(
                "Canonical patient volume array does not match its descriptor"
            )
        if str(volume.dtype) != dtype:
            raise VolumeRenderingValidationError(
                "Canonical patient volume array does not match its descriptor"
            )

        return CanonicalVolumeRenderingSource(
            manifest_path=manifest_path,
            study_dir=study_dir,
            volume_path=volume_path,
            source_series_uid=source_series_uid,
            modality=modality,
            dtype=dtype,
            shape=shape,  # type: ignore[arg-type]
            spacing_mm=spacing,  # type: ignore[arg-type]
            array_index_to_patient_lps=affine,  # type: ignore[arg-type]
            intensity_units=intensity_units,
            value_range=value_range,  # type: ignore[arg-type]
            volume_created_at_utc=created_at,
            source_descriptor_sha256=_volume_identity(descriptor),
            volume=volume,
        )

    def _artifact_from_manifest(
        self,
        *,
        payload: dict[str, object],
        source: CanonicalVolumeRenderingSource,
    ) -> VolumeRenderingArtifactDescriptor | None:
        raw = payload.get("volume_rendering")
        if not isinstance(raw, dict) or raw.get("ready") is not True:
            return None
        try:
            descriptor = VolumeRenderingArtifactDescriptor(
                schema_version=int(raw.get("schema_version") or 0),
                ready=True,
                created_at_utc=str(raw.get("created_at_utc") or ""),
                revision=str(raw.get("revision") or ""),
                source_series_uid=str(raw.get("source_series_uid") or ""),
                source_volume_descriptor_sha256=str(
                    raw.get("source_volume_descriptor_sha256") or ""
                ),
                source_volume_created_at_utc=str(
                    raw.get("source_volume_created_at_utc") or ""
                ),
                source_modality=str(raw.get("source_modality") or ""),
                source_intensity_units=str(raw.get("source_intensity_units") or ""),
                source_value_range=tuple(
                    float(item) for item in raw.get("source_value_range", [])
                ),  # type: ignore[arg-type]
                source_shape=tuple(
                    int(item) for item in raw.get("source_shape", [])
                ),  # type: ignore[arg-type]
                source_axis_order=tuple(
                    str(item) for item in raw.get("source_axis_order", [])
                ),  # type: ignore[arg-type]
                spacing_mm=tuple(
                    float(item) for item in raw.get("spacing_mm", [])
                ),  # type: ignore[arg-type]
                array_index_to_patient_lps=tuple(
                    tuple(float(item) for item in row)
                    for row in raw.get("array_index_to_patient_lps", [])
                ),  # type: ignore[arg-type]
                texture_dimensions=tuple(
                    int(item) for item in raw.get("texture_dimensions", [])
                ),  # type: ignore[arg-type]
                texture_axis_order=tuple(
                    str(item) for item in raw.get("texture_axis_order", [])
                ),  # type: ignore[arg-type]
                texture_coordinate_to_patient_lps=tuple(
                    tuple(float(item) for item in row)
                    for row in raw.get("texture_coordinate_to_patient_lps", [])
                ),  # type: ignore[arg-type]
                patient_bounds_lps_mm=tuple(
                    float(item) for item in raw.get("patient_bounds_lps_mm", [])
                ),  # type: ignore[arg-type]
                encoding=str(raw.get("encoding") or ""),
                component_type=str(raw.get("component_type") or ""),
                component_order=tuple(
                    str(item) for item in raw.get("component_order", [])
                ),  # type: ignore[arg-type]
                bytes_per_voxel=int(raw.get("bytes_per_voxel") or 0),
                decode_offset=float(raw.get("decode_offset")),
                decode_scale=float(raw.get("decode_scale")),
                byte_length=int(raw.get("byte_length") or 0),
                artifact_sha256=str(raw.get("artifact_sha256") or ""),
                artifact_path=str(raw.get("artifact_path") or ""),
                metadata_path=str(raw.get("metadata_path") or ""),
            )
        except (TypeError, ValueError):
            return None

        expected_dimensions = (source.shape[2], source.shape[1], source.shape[0])
        expected_length = prod(source.shape) * 2
        expected_transform = _texture_transform(source.array_index_to_patient_lps, source.shape)
        expected_bounds = _patient_bounds(expected_transform)
        if descriptor.schema_version != VOLUME_RENDERING_SCHEMA_VERSION:
            return None
        if not descriptor.created_at_utc:
            return None
        if not _valid_sha256(descriptor.revision) or not _valid_sha256(descriptor.artifact_sha256):
            return None
        if descriptor.source_series_uid != source.source_series_uid:
            return None
        if descriptor.source_volume_descriptor_sha256 != source.source_descriptor_sha256:
            return None
        if descriptor.source_volume_created_at_utc != source.volume_created_at_utc:
            return None
        if descriptor.source_modality != source.modality:
            return None
        if descriptor.source_intensity_units != source.intensity_units:
            return None
        if descriptor.source_value_range != source.value_range:
            return None
        if descriptor.source_shape != source.shape:
            return None
        if descriptor.source_axis_order != CANONICAL_AXIS_ORDER:
            return None
        if descriptor.spacing_mm != source.spacing_mm:
            return None
        if descriptor.array_index_to_patient_lps != source.array_index_to_patient_lps:
            return None
        if descriptor.texture_dimensions != expected_dimensions:
            return None
        if descriptor.texture_axis_order != TEXTURE_AXIS_ORDER:
            return None
        if not np.allclose(
            descriptor.texture_coordinate_to_patient_lps,
            expected_transform,
            atol=1e-10,
        ):
            return None
        if not np.allclose(descriptor.patient_bounds_lps_mm, expected_bounds, atol=1e-10):
            return None
        if descriptor.encoding != RENDERING_ENCODING:
            return None
        if descriptor.component_type != "uint8":
            return None
        if descriptor.component_order != ("low_byte", "high_byte"):
            return None
        if descriptor.bytes_per_voxel != 2 or descriptor.byte_length != expected_length:
            return None
        if not isfinite(descriptor.decode_offset) or not isfinite(descriptor.decode_scale):
            return None
        if descriptor.decode_scale <= 0:
            return None
        expected_offset = float(source.value_range[0])
        expected_scale = (
            float((source.value_range[1] - source.value_range[0]) / 65535.0)
            if source.value_range[1] > source.value_range[0]
            else 1.0
        )
        if descriptor.decode_offset != expected_offset or descriptor.decode_scale != expected_scale:
            return None
        expected_revision = sha256(
            (
                f"{source.source_descriptor_sha256}:{descriptor.artifact_sha256}:"
                f"{RENDERING_ENCODING}:{descriptor.byte_length}"
            ).encode("ascii")
        ).hexdigest()
        if descriptor.revision != expected_revision:
            return None

        relative_artifact = Path(descriptor.artifact_path)
        relative_metadata = Path(descriptor.metadata_path)
        if relative_artifact.is_absolute() or ".." in relative_artifact.parts:
            return None
        if relative_metadata.is_absolute() or ".." in relative_metadata.parts:
            return None
        expected_artifact_path = f"derived/volume_rendering/volume-{descriptor.revision[:16]}.rg8"
        expected_metadata_path = (
            f"derived/volume_rendering/descriptor-{descriptor.revision[:16]}.json"
        )
        if descriptor.artifact_path != expected_artifact_path:
            return None
        if descriptor.metadata_path != expected_metadata_path:
            return None

        artifact_path = source.study_dir / relative_artifact
        metadata_path = source.study_dir / relative_metadata
        if not artifact_path.is_file() or not metadata_path.is_file():
            return None
        try:
            if artifact_path.stat().st_size != descriptor.byte_length:
                return None
            if _sha256_file(artifact_path) != descriptor.artifact_sha256:
                return None
            metadata = _load_json(metadata_path, "Volume rendering metadata is unreadable")
        except (OSError, VolumeRenderingValidationError):
            return None
        if metadata != raw:
            return None
        return descriptor

    def inspect_latest(self) -> dict[str, object]:
        _, payload, source = self._load_latest()
        descriptor = self._artifact_from_manifest(payload=payload, source=source)
        if descriptor is not None:
            return descriptor.public_dict()
        return {
            "schema_version": VOLUME_RENDERING_SCHEMA_VERSION,
            "ready": False,
            "source_volume_ready": True,
            "source_volume_descriptor_sha256": source.source_descriptor_sha256,
            "source_modality": source.modality,
            "source_intensity_units": source.intensity_units,
            "source_shape": list(source.shape),
        }

    def load_latest_source(self) -> CanonicalVolumeRenderingSource:
        return self._load_latest()[2]

    def prepare_latest(self) -> dict[str, object]:
        if np is None:
            raise VolumeRenderingDependencyUnavailable(
                "Direct volume rendering requires the numpy backend dependency"
            )
        manifest_path, payload, source = self._load_latest()
        existing = self._artifact_from_manifest(payload=payload, source=source)
        if existing is not None:
            return existing.public_dict()

        voxel_count = prod(source.shape)
        byte_length = voxel_count * 2
        if byte_length > self.max_rendering_bytes:
            raise VolumeRenderingValidationError(
                "The canonical patient volume is too large for the direct rendering artifact limit"
            )

        low, high = source.value_range
        decode_offset = float(low)
        decode_scale = float((high - low) / 65535.0) if high > low else 1.0
        texture_transform = _texture_transform(source.array_index_to_patient_lps, source.shape)
        patient_bounds = _patient_bounds(texture_transform)

        output_dir = source.study_dir / "derived" / "volume_rendering"
        output_dir.mkdir(parents=True, exist_ok=True)
        nonce = uuid4().hex[:16]
        artifact_tmp = output_dir / f"volume-{nonce}.rg8.tmp"
        descriptor_tmp = output_dir / f"descriptor-{nonce}.json.tmp"
        manifest_tmp = manifest_path.with_name(f"manifest-{nonce}.json.tmp")

        try:
            digest = sha256()
            actual_min = float("inf")
            actual_max = float("-inf")
            with artifact_tmp.open("wb") as handle:
                for start in range(0, source.shape[0], self.chunk_slices):
                    stop = min(start + self.chunk_slices, source.shape[0])
                    values = np.asarray(source.volume[start:stop], dtype=np.float32)
                    if not np.all(np.isfinite(values)):
                        raise VolumeRenderingValidationError(
                            "Canonical patient volume contains non-finite intensity values"
                        )
                    actual_min = min(actual_min, float(np.min(values)))
                    actual_max = max(actual_max, float(np.max(values)))
                    if high > low:
                        scaled = np.rint((values.astype(np.float64) - decode_offset) / decode_scale)
                        quantized = np.clip(scaled, 0.0, 65535.0).astype("<u2")
                    else:
                        quantized = np.zeros(values.shape, dtype="<u2")
                    encoded = quantized.tobytes(order="C")
                    handle.write(encoded)
                    digest.update(encoded)
                handle.flush()

            tolerance = max(abs(decode_scale) * 1e-6, 1e-6)
            if not (
                abs(actual_min - low) <= tolerance
                and abs(actual_max - high) <= tolerance
            ):
                raise VolumeRenderingValidationError(
                    "Canonical patient volume value range does not match its descriptor"
                )
            if artifact_tmp.stat().st_size != byte_length:
                raise VolumeRenderingError("Volume rendering artifact has an invalid byte length")

            artifact_sha256 = digest.hexdigest()
            revision = sha256(
                (
                    f"{source.source_descriptor_sha256}:{artifact_sha256}:"
                    f"{RENDERING_ENCODING}:{byte_length}"
                ).encode("ascii")
            ).hexdigest()
            artifact_path = output_dir / f"volume-{revision[:16]}.rg8"
            artifact_is_current = (
                artifact_path.is_file()
                and artifact_path.stat().st_size == byte_length
                and _sha256_file(artifact_path) == artifact_sha256
            )
            if artifact_is_current:
                artifact_tmp.unlink(missing_ok=True)
            else:
                artifact_tmp.replace(artifact_path)
            descriptor_path = output_dir / f"descriptor-{revision[:16]}.json"

            descriptor = VolumeRenderingArtifactDescriptor(
                schema_version=VOLUME_RENDERING_SCHEMA_VERSION,
                ready=True,
                created_at_utc=_utc_now(),
                revision=revision,
                source_series_uid=source.source_series_uid,
                source_volume_descriptor_sha256=source.source_descriptor_sha256,
                source_volume_created_at_utc=source.volume_created_at_utc,
                source_modality=source.modality,
                source_intensity_units=source.intensity_units,
                source_value_range=source.value_range,
                source_shape=source.shape,
                source_axis_order=CANONICAL_AXIS_ORDER,
                spacing_mm=source.spacing_mm,
                array_index_to_patient_lps=source.array_index_to_patient_lps,
                texture_dimensions=(source.shape[2], source.shape[1], source.shape[0]),
                texture_axis_order=TEXTURE_AXIS_ORDER,
                texture_coordinate_to_patient_lps=texture_transform,
                patient_bounds_lps_mm=patient_bounds,
                encoding=RENDERING_ENCODING,
                component_type="uint8",
                component_order=("low_byte", "high_byte"),
                bytes_per_voxel=2,
                decode_offset=decode_offset,
                decode_scale=decode_scale,
                byte_length=byte_length,
                artifact_sha256=artifact_sha256,
                artifact_path=artifact_path.relative_to(source.study_dir).as_posix(),
                metadata_path=descriptor_path.relative_to(source.study_dir).as_posix(),
            )
            manifest_descriptor = descriptor.manifest_dict()
            descriptor_tmp.write_text(
                json.dumps(manifest_descriptor, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            descriptor_tmp.replace(descriptor_path)

            payload["schema_version"] = max(
                int(payload.get("schema_version") or 0),
                STUDY_MANIFEST_SCHEMA_VERSION,
            )
            payload["volume_rendering"] = manifest_descriptor
            manifest_tmp.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            manifest_tmp.replace(manifest_path)
        except OSError as exc:
            artifact_tmp.unlink(missing_ok=True)
            descriptor_tmp.unlink(missing_ok=True)
            manifest_tmp.unlink(missing_ok=True)
            raise VolumeRenderingError("Volume rendering artifact could not be persisted") from exc
        except Exception:
            artifact_tmp.unlink(missing_ok=True)
            descriptor_tmp.unlink(missing_ok=True)
            manifest_tmp.unlink(missing_ok=True)
            raise

        return descriptor.public_dict()

    def artifact_latest(
        self,
        revision: str,
    ) -> tuple[Path, VolumeRenderingArtifactDescriptor]:
        _, payload, source = self._load_latest()
        descriptor = self._artifact_from_manifest(payload=payload, source=source)
        requested = revision.strip().lower()
        if descriptor is None or requested != descriptor.revision:
            raise VolumeRenderingValidationError(
                "Requested volume rendering revision is not available for the current "
                "patient volume"
            )
        return source.study_dir / descriptor.artifact_path, descriptor
