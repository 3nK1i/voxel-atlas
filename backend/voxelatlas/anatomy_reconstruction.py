from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Protocol
from uuid import uuid4

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - numpy is a Phase 3C runtime dependency
    np = None  # type: ignore[assignment]

from .dicom_ingestion import DicomStudyRepository


ANATOMY_SCHEMA_VERSION = 1
STUDY_MANIFEST_SCHEMA_VERSION = 4
CANONICAL_COORDINATE_SYSTEM = "patient_lps"
CANONICAL_LENGTH_UNITS = "mm"
CANONICAL_REPRESENTATION = "triangle_mesh"
CANONICAL_ARTIFACT_FORMAT = "npz"
SUPPORTED_LAYERS = ("skull", "brain")


class AnatomyReconstructionError(ValueError):
    """Base class for safe patient-anatomy reconstruction contract failures."""


class AnatomyReconstructionDependencyUnavailable(AnatomyReconstructionError):
    pass


class AnatomyReconstructionValidationError(AnatomyReconstructionError):
    pass


@dataclass(frozen=True)
class CanonicalReconstructionInput:
    study_dir: Path
    volume_path: Path
    source_series_uid: str
    modality: str
    dtype: str
    shape: tuple[int, int, int]
    axis_order: tuple[str, str, str]
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

    def public_dict(self) -> dict[str, object]:
        return {
            "ready": True,
            "source_series_uid": self.source_series_uid,
            "modality": self.modality,
            "dtype": self.dtype,
            "shape": list(self.shape),
            "axis_order": list(self.axis_order),
            "spacing_mm": list(self.spacing_mm),
            "array_index_to_patient_lps": [
                list(row) for row in self.array_index_to_patient_lps
            ],
            "intensity_units": self.intensity_units,
            "value_range": list(self.value_range),
            "volume_created_at_utc": self.volume_created_at_utc,
            "source_descriptor_sha256": self.source_descriptor_sha256,
        }


@dataclass(frozen=True)
class AnatomyArtifactDescriptor:
    schema_version: int
    ready: bool
    layer: str
    created_at_utc: str
    source_series_uid: str
    source_volume_descriptor_sha256: str
    source_volume_created_at_utc: str
    source_modality: str
    coordinate_system: str
    length_units: str
    representation: str
    artifact_format: str
    artifact_path: str
    metadata_path: str
    artifact_sha256: str
    vertex_count: int
    triangle_count: int
    bounds_patient_lps_mm: tuple[float, float, float, float, float, float]
    algorithm: str
    algorithm_version: str
    parameters: dict[str, object]

    def manifest_dict(self) -> dict[str, object]:
        return asdict(self)

    def public_dict(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.manifest_dict().items()
            if key not in {"artifact_path", "metadata_path", "parameters"}
        }


@dataclass(frozen=True)
class ReconstructionMesh:
    vertices_lps_mm: object
    faces: object


class AnatomyReconstructor(Protocol):
    layer: str
    algorithm: str
    algorithm_version: str

    def reconstruct(self, source: CanonicalReconstructionInput) -> ReconstructionMesh:
        """Return a triangle mesh expressed directly in patient LPS millimetres."""
        ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, message: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnatomyReconstructionValidationError(message) from exc
    if not isinstance(payload, dict):
        raise AnatomyReconstructionValidationError(message)
    return payload


def _float_tuple(value: object, expected: int, field: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != expected:
        raise AnatomyReconstructionValidationError(
            f"Canonical patient volume is missing {field}"
        )
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise AnatomyReconstructionValidationError(
            f"Canonical patient volume has invalid {field}"
        ) from exc
    if not all(isfinite(item) for item in result):
        raise AnatomyReconstructionValidationError(
            f"Canonical patient volume has invalid {field}"
        )
    return result


def _int_tuple(value: object, expected: int, field: str) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != expected:
        raise AnatomyReconstructionValidationError(
            f"Canonical patient volume is missing {field}"
        )
    try:
        result = tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise AnatomyReconstructionValidationError(
            f"Canonical patient volume has invalid {field}"
        ) from exc
    if any(item <= 0 for item in result):
        raise AnatomyReconstructionValidationError(
            f"Canonical patient volume has invalid {field}"
        )
    return result


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


def _layer_input_eligibility(layer: str, source: CanonicalReconstructionInput) -> tuple[bool, str]:
    if layer == "skull":
        if source.modality == "CT" and source.intensity_units == "HU":
            return True, "CT HU volume is eligible for skull reconstruction"
        return False, "Skull reconstruction currently requires a qualified CT HU volume"
    if layer == "brain":
        if source.modality == "MR":
            return True, "MR volume is eligible for the planned brain reconstruction provider"
        return False, "Brain reconstruction is first qualified from MR volumes in V1"
    raise AnatomyReconstructionValidationError(f"Unsupported anatomy layer: {layer}")


class AnatomyReconstructionService:
    def __init__(self, *, data_dir: Path):
        self.repository = DicomStudyRepository(data_dir)

    def _latest_manifest_path(self) -> Path:
        studies_dir = self.repository.studies_dir
        if not studies_dir.exists():
            raise AnatomyReconstructionValidationError("No stored DICOM study is available")
        manifests = list(studies_dir.glob("*/manifest.json"))
        if not manifests:
            raise AnatomyReconstructionValidationError("No stored DICOM study is available")
        return max(manifests, key=lambda item: item.stat().st_mtime_ns)

    def _load_latest(self) -> tuple[Path, dict[str, object]]:
        manifest_path = self._latest_manifest_path()
        payload = _load_json(
            manifest_path,
            "Stored DICOM study manifest is unreadable",
        )
        return manifest_path, payload

    def load_latest_input(self) -> CanonicalReconstructionInput:
        manifest_path, payload = self._load_latest()
        return self._load_input(manifest_path, payload)

    def _load_input(
        self,
        manifest_path: Path,
        payload: dict[str, object],
    ) -> CanonicalReconstructionInput:
        if np is None:
            raise AnatomyReconstructionDependencyUnavailable(
                "Anatomical reconstruction requires the numpy backend dependency"
            )

        volume = payload.get("volume")
        if not isinstance(volume, dict) or volume.get("ready") is not True:
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume must be ready before anatomical reconstruction"
            )

        if volume.get("artifact_path") != "derived/volume.npy":
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume has an invalid artifact contract"
            )
        if volume.get("metadata_path") != "derived/volume.json":
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume has an invalid metadata contract"
            )

        study_dir = manifest_path.parent
        volume_path = study_dir / "derived" / "volume.npy"
        metadata_path = study_dir / "derived" / "volume.json"
        if not volume_path.is_file() or not metadata_path.is_file():
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume artifacts are missing"
            )

        metadata = _load_json(
            metadata_path,
            "Canonical patient volume metadata is unreadable",
        )
        if metadata != volume:
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume metadata does not match the study manifest"
            )

        source_series_uid = str(volume.get("source_series_uid") or "").strip()
        modality = str(volume.get("modality") or "").strip().upper()
        dtype = str(volume.get("dtype") or "").strip()
        axis_order_raw = volume.get("axis_order")
        intensity_units = str(volume.get("intensity_units") or "").strip()
        created_at = str(volume.get("created_at_utc") or "").strip()
        if not all((source_series_uid, modality, dtype, intensity_units, created_at)):
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume provenance is incomplete"
            )
        if axis_order_raw != ["slice", "row", "column"] and axis_order_raw != (
            "slice",
            "row",
            "column",
        ):
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume axis order is unsupported"
            )

        shape = _int_tuple(volume.get("shape"), 3, "shape")
        spacing = _float_tuple(volume.get("spacing_mm"), 3, "spacing")
        if any(item <= 0 for item in spacing):
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume has invalid spacing"
            )
        value_range = _float_tuple(volume.get("value_range"), 2, "value range")

        affine_raw = volume.get("array_index_to_patient_lps")
        if not isinstance(affine_raw, (list, tuple)) or len(affine_raw) != 4:
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume is missing patient LPS affine"
            )
        affine = tuple(
            _float_tuple(row, 4, "patient LPS affine")
            for row in affine_raw
        )
        affine_array = np.asarray(affine, dtype=np.float64)
        if not np.allclose(affine_array[3], [0.0, 0.0, 0.0, 1.0], atol=1e-8):
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume has invalid patient LPS affine"
            )
        if abs(float(np.linalg.det(affine_array[:3, :3]))) <= 1e-12:
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume patient LPS affine is singular"
            )

        try:
            array = np.load(volume_path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume array is unreadable"
            ) from exc
        if tuple(array.shape) != shape or str(array.dtype) != dtype:
            raise AnatomyReconstructionValidationError(
                "Canonical patient volume array does not match its descriptor"
            )

        return CanonicalReconstructionInput(
            study_dir=study_dir,
            volume_path=volume_path,
            source_series_uid=source_series_uid,
            modality=modality,
            dtype=dtype,
            shape=shape,  # type: ignore[arg-type]
            axis_order=("slice", "row", "column"),
            spacing_mm=spacing,  # type: ignore[arg-type]
            array_index_to_patient_lps=affine,  # type: ignore[arg-type]
            intensity_units=intensity_units,
            value_range=value_range,  # type: ignore[arg-type]
            volume_created_at_utc=created_at,
            source_descriptor_sha256=_volume_identity(volume),
        )

    def _artifact_from_manifest(
        self,
        *,
        payload: dict[str, object],
        source: CanonicalReconstructionInput,
        layer: str,
    ) -> AnatomyArtifactDescriptor | None:
        anatomy = payload.get("anatomy")
        if not isinstance(anatomy, dict):
            return None
        if anatomy.get("source_volume_descriptor_sha256") != source.source_descriptor_sha256:
            return None
        layers = anatomy.get("layers")
        if not isinstance(layers, dict):
            return None
        raw = layers.get(layer)
        if not isinstance(raw, dict) or raw.get("ready") is not True:
            return None
        if raw.get("source_volume_descriptor_sha256") != source.source_descriptor_sha256:
            return None
        try:
            descriptor = AnatomyArtifactDescriptor(
                schema_version=int(raw.get("schema_version") or 0),
                ready=True,
                layer=str(raw.get("layer") or ""),
                created_at_utc=str(raw.get("created_at_utc") or ""),
                source_series_uid=str(raw.get("source_series_uid") or ""),
                source_volume_descriptor_sha256=str(
                    raw.get("source_volume_descriptor_sha256") or ""
                ),
                source_volume_created_at_utc=str(
                    raw.get("source_volume_created_at_utc") or ""
                ),
                source_modality=str(raw.get("source_modality") or ""),
                coordinate_system=str(raw.get("coordinate_system") or ""),
                length_units=str(raw.get("length_units") or ""),
                representation=str(raw.get("representation") or ""),
                artifact_format=str(raw.get("artifact_format") or ""),
                artifact_path=str(raw.get("artifact_path") or ""),
                metadata_path=str(raw.get("metadata_path") or ""),
                artifact_sha256=str(raw.get("artifact_sha256") or ""),
                vertex_count=int(raw.get("vertex_count") or 0),
                triangle_count=int(raw.get("triangle_count") or 0),
                bounds_patient_lps_mm=tuple(
                    float(item) for item in raw.get("bounds_patient_lps_mm", [])
                ),  # type: ignore[arg-type]
                algorithm=str(raw.get("algorithm") or ""),
                algorithm_version=str(raw.get("algorithm_version") or ""),
                parameters=dict(raw.get("parameters") or {}),
            )
        except (TypeError, ValueError):
            return None

        if descriptor.schema_version != ANATOMY_SCHEMA_VERSION:
            return None
        if descriptor.layer != layer:
            return None
        if descriptor.source_series_uid != source.source_series_uid:
            return None
        if descriptor.source_volume_created_at_utc != source.volume_created_at_utc:
            return None
        if descriptor.source_modality != source.modality:
            return None
        if descriptor.coordinate_system != CANONICAL_COORDINATE_SYSTEM:
            return None
        if descriptor.length_units != CANONICAL_LENGTH_UNITS:
            return None
        if descriptor.representation != CANONICAL_REPRESENTATION:
            return None
        if descriptor.artifact_format != CANONICAL_ARTIFACT_FORMAT:
            return None
        if not descriptor.created_at_utc or not descriptor.algorithm or not descriptor.algorithm_version:
            return None
        digest = descriptor.artifact_sha256.lower()
        if (
            len(digest) != 64
            or digest != descriptor.artifact_sha256
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            return None
        expected_prefix = f"derived/anatomy/{layer}/mesh-"
        if not descriptor.artifact_path.startswith(expected_prefix):
            return None
        if not descriptor.artifact_path.endswith(".npz"):
            return None
        expected_metadata_prefix = f"derived/anatomy/{layer}/descriptor-"
        if not descriptor.metadata_path.startswith(expected_metadata_prefix):
            return None
        if not descriptor.metadata_path.endswith(".json"):
            return None
        relative_artifact = Path(descriptor.artifact_path)
        relative_metadata = Path(descriptor.metadata_path)
        if relative_artifact.is_absolute() or ".." in relative_artifact.parts:
            return None
        if relative_metadata.is_absolute() or ".." in relative_metadata.parts:
            return None
        artifact = source.study_dir / relative_artifact
        metadata = source.study_dir / relative_metadata
        if not artifact.is_file() or not metadata.is_file():
            return None
        try:
            artifact_digest = _sha256_file(artifact)
        except OSError:
            return None
        if artifact_digest != descriptor.artifact_sha256:
            return None
        try:
            metadata_payload = _load_json(
                metadata,
                "Patient anatomy metadata is unreadable",
            )
        except AnatomyReconstructionValidationError:
            return None
        if metadata_payload != raw:
            return None
        if descriptor.vertex_count < 3 or descriptor.triangle_count < 1:
            return None
        bounds = descriptor.bounds_patient_lps_mm
        if len(bounds) != 6 or not all(isfinite(item) for item in bounds):
            return None
        if any(bounds[index] > bounds[index + 3] for index in range(3)):
            return None
        return descriptor

    def inspect_latest(self) -> dict[str, object]:
        manifest_path, payload = self._load_latest()
        source = self._load_input(manifest_path, payload)
        layers: dict[str, object] = {}
        ready: dict[str, bool] = {}

        for layer in SUPPORTED_LAYERS:
            eligible, reason = _layer_input_eligibility(layer, source)
            artifact = self._artifact_from_manifest(
                payload=payload,
                source=source,
                layer=layer,
            )
            artifact_ready = artifact is not None
            ready[layer] = artifact_ready
            state = "ready" if artifact_ready else ("eligible" if eligible else "source_not_supported")
            layers[layer] = {
                "layer": layer,
                "state": state,
                "input_eligible": eligible,
                "artifact_ready": artifact_ready,
                "reason": "Qualified patient anatomy artifact is ready" if artifact_ready else reason,
                "artifact": artifact.public_dict() if artifact is not None else None,
            }

        return {
            "schema_version": ANATOMY_SCHEMA_VERSION,
            "source_volume_ready": True,
            "coordinate_system": CANONICAL_COORDINATE_SYSTEM,
            "length_units": CANONICAL_LENGTH_UNITS,
            "source_volume": source.public_dict(),
            "layers": layers,
            "combined_ready": ready["skull"] and ready["brain"],
        }

    def publish_layer_latest(
        self,
        *,
        layer: str,
        vertices_lps_mm: object,
        faces: object,
        algorithm: str,
        algorithm_version: str,
        parameters: dict[str, object] | None = None,
    ) -> AnatomyArtifactDescriptor:
        if np is None:
            raise AnatomyReconstructionDependencyUnavailable(
                "Anatomical reconstruction requires the numpy backend dependency"
            )
        if layer not in SUPPORTED_LAYERS:
            raise AnatomyReconstructionValidationError(f"Unsupported anatomy layer: {layer}")

        manifest_path, payload = self._load_latest()
        source = self._load_input(manifest_path, payload)
        eligible, reason = _layer_input_eligibility(layer, source)
        if not eligible:
            raise AnatomyReconstructionValidationError(reason)

        name = algorithm.strip()
        version = algorithm_version.strip()
        if not name or not version:
            raise AnatomyReconstructionValidationError(
                "Anatomy reconstruction provenance must include algorithm and version"
            )

        try:
            vertices = np.asarray(vertices_lps_mm, dtype=np.float32)
            raw_faces = np.asarray(faces)
        except (TypeError, ValueError) as exc:
            raise AnatomyReconstructionValidationError(
                "Anatomy reconstruction produced an invalid mesh"
            ) from exc
        if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < 3:
            raise AnatomyReconstructionValidationError(
                "Anatomy reconstruction vertices must have shape Nx3"
            )
        if not np.isfinite(vertices).all():
            raise AnatomyReconstructionValidationError(
                "Anatomy reconstruction vertices must be finite"
            )
        if raw_faces.ndim != 2 or raw_faces.shape[1] != 3 or len(raw_faces) < 1:
            raise AnatomyReconstructionValidationError(
                "Anatomy reconstruction faces must have shape Mx3"
            )
        if not np.issubdtype(raw_faces.dtype, np.integer):
            raise AnatomyReconstructionValidationError(
                "Anatomy reconstruction faces must contain integer indices"
            )
        faces_array = raw_faces.astype(np.int32, copy=False)
        if int(faces_array.min()) < 0 or int(faces_array.max()) >= len(vertices):
            raise AnatomyReconstructionValidationError(
                "Anatomy reconstruction face indices are out of bounds"
            )

        minimum = vertices.min(axis=0)
        maximum = vertices.max(axis=0)
        bounds = tuple(float(item) for item in np.concatenate((minimum, maximum)))

        provenance_parameters = dict(parameters or {})
        try:
            json.dumps(provenance_parameters, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise AnatomyReconstructionValidationError(
                "Anatomy reconstruction parameters must be JSON serializable"
            ) from exc

        layer_dir = source.study_dir / "derived" / "anatomy" / layer
        layer_dir.mkdir(parents=True, exist_ok=True)
        revision = uuid4().hex[:16]
        mesh_tmp = layer_dir / f"mesh-{revision}.npz.tmp"
        descriptor_tmp = layer_dir / f"descriptor-{revision}.json.tmp"
        manifest_tmp = manifest_path.with_name("manifest.json.tmp")

        try:
            with mesh_tmp.open("wb") as handle:
                np.savez_compressed(
                    handle,
                    vertices_lps_mm=vertices,
                    faces=faces_array,
                )
                handle.flush()
            digest = _sha256_file(mesh_tmp)
            mesh_path = layer_dir / f"mesh-{digest[:16]}.npz"
            if mesh_path.exists():
                mesh_tmp.unlink(missing_ok=True)
            else:
                mesh_tmp.replace(mesh_path)
            descriptor_path = layer_dir / f"descriptor-{revision}.json"

            descriptor = AnatomyArtifactDescriptor(
                schema_version=ANATOMY_SCHEMA_VERSION,
                ready=True,
                layer=layer,
                created_at_utc=_utc_now(),
                source_series_uid=source.source_series_uid,
                source_volume_descriptor_sha256=source.source_descriptor_sha256,
                source_volume_created_at_utc=source.volume_created_at_utc,
                source_modality=source.modality,
                coordinate_system=CANONICAL_COORDINATE_SYSTEM,
                length_units=CANONICAL_LENGTH_UNITS,
                representation=CANONICAL_REPRESENTATION,
                artifact_format=CANONICAL_ARTIFACT_FORMAT,
                artifact_path=mesh_path.relative_to(source.study_dir).as_posix(),
                metadata_path=descriptor_path.relative_to(source.study_dir).as_posix(),
                artifact_sha256=digest,
                vertex_count=int(len(vertices)),
                triangle_count=int(len(faces_array)),
                bounds_patient_lps_mm=bounds,  # type: ignore[arg-type]
                algorithm=name,
                algorithm_version=version,
                parameters=provenance_parameters,
            )
            descriptor_tmp.write_text(
                json.dumps(descriptor.manifest_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            descriptor_tmp.replace(descriptor_path)

            existing = payload.get("anatomy")
            existing_layers: dict[str, object] = {}
            if (
                isinstance(existing, dict)
                and existing.get("source_volume_descriptor_sha256")
                == source.source_descriptor_sha256
                and isinstance(existing.get("layers"), dict)
            ):
                existing_layers.update(existing["layers"])  # type: ignore[arg-type]
            existing_layers[layer] = descriptor.manifest_dict()
            payload["schema_version"] = max(
                int(payload.get("schema_version") or 0),
                STUDY_MANIFEST_SCHEMA_VERSION,
            )
            payload["anatomy"] = {
                "schema_version": ANATOMY_SCHEMA_VERSION,
                "source_volume_descriptor_sha256": source.source_descriptor_sha256,
                "coordinate_system": CANONICAL_COORDINATE_SYSTEM,
                "length_units": CANONICAL_LENGTH_UNITS,
                "layers": existing_layers,
            }
            manifest_tmp.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            manifest_tmp.replace(manifest_path)
        except OSError as exc:
            mesh_tmp.unlink(missing_ok=True)
            descriptor_tmp.unlink(missing_ok=True)
            manifest_tmp.unlink(missing_ok=True)
            raise AnatomyReconstructionError(
                "Patient anatomy artifact could not be persisted"
            ) from exc
        except Exception:
            mesh_tmp.unlink(missing_ok=True)
            descriptor_tmp.unlink(missing_ok=True)
            manifest_tmp.unlink(missing_ok=True)
            raise

        return descriptor
