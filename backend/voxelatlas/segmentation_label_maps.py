from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
from typing import Callable

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - numpy is a backend dependency
    np = None  # type: ignore[assignment]

from .segmentation import (
    CanonicalSegmentationSource,
    CanonicalSegmentationSourceRepository,
    SegmentationConflictError,
    SegmentationJobService,
    SegmentationNotFoundError,
    SegmentationValidationError,
)


LABEL_MAP_SCHEMA_VERSION = 1
LABEL_MAP_WORKER_SCHEMA_VERSION = 1
LABEL_MAP_ID_PATTERN = re.compile(r"^map-[0-9a-f]{32}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
AXIS_ORDER = ("slice", "row", "column")
CANONICAL_COORDINATE_SYSTEM = "patient_lps"
CANONICAL_LENGTH_UNITS = "mm"
CANONICAL_DTYPE = "uint16"
MAX_WORKER_REPORT_BYTES = 256 * 1024
MAX_IMPORT_TIMEOUT_SECONDS = 60 * 60
NIFTI_GEOMETRY_ATOL_MM = 1e-4
INDEX_TRANSFORM_ATOL = 1e-5


WorkerRunner = Callable[..., object]
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        raise SegmentationValidationError("Label-map metadata is invalid") from exc


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


def _sha256_value(value: object, field: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise SegmentationValidationError(f"{field} is invalid")
    return value


def _positive_int(value: object, field: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SegmentationValidationError(f"{field} is invalid")
    if maximum is not None and value > maximum:
        raise SegmentationValidationError(f"{field} is invalid")
    return value


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SegmentationValidationError(f"{field} is invalid")
    return value


def _shape(value: object) -> tuple[int, int, int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value)
    ):
        raise SegmentationValidationError("Canonical label-map shape is invalid")
    return (int(value[0]), int(value[1]), int(value[2]))


def _float_tuple(value: object, count: int, field: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise SegmentationValidationError(f"{field} is invalid")
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise SegmentationValidationError(f"{field} is invalid") from exc
    if not all(isfinite(item) for item in result):
        raise SegmentationValidationError(f"{field} is invalid")
    return result


def _matrix(value: object, field: str) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise SegmentationValidationError(f"{field} is invalid")
    matrix = tuple(_float_tuple(row, 4, field) for row in value)
    if matrix[3] != (0.0, 0.0, 0.0, 1.0):
        raise SegmentationValidationError(f"{field} is invalid")
    if np is None:
        raise SegmentationValidationError("Canonical label-map import requires numpy")
    array = np.asarray(matrix, dtype=np.float64)
    if abs(float(np.linalg.det(array[:3, :3]))) <= 1e-12:
        raise SegmentationValidationError(f"{field} is singular")
    return matrix


def _labels(value: object, *, maximum: int) -> tuple[int, ...]:
    if (
        not isinstance(value, list)
        or not value
        or value != sorted(set(value))
        or value[0] != 0
        or any(
            isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > maximum
            for item in value
        )
    ):
        raise SegmentationValidationError("Segmentation label inventory is invalid")
    return tuple(value)


def _safe_repository(root: Path) -> None:
    segmentation = root.parent
    if segmentation.is_symlink() or (segmentation.exists() and not segmentation.is_dir()):
        raise SegmentationValidationError("Segmentation artifact repository is unsafe")
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise SegmentationValidationError("Segmentation label-map repository is unsafe")


def _safe_relative_artifact(value: object, *, job_root: Path) -> Path:
    if not isinstance(value, str):
        raise SegmentationValidationError("Provider mask artifact contract is invalid")
    relative = Path(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or len(relative.parts) < 3
        or relative.parts[0] != "provider"
        or not (value.endswith(".nii") or value.endswith(".nii.gz"))
        or any(ord(character) < 32 for character in value)
    ):
        raise SegmentationValidationError("Provider mask artifact contract is invalid")
    path = job_root / relative
    if path.is_symlink() or not path.is_file():
        raise SegmentationValidationError("Provider mask artifact is unavailable")
    try:
        resolved_root = job_root.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise SegmentationValidationError("Provider mask artifact is unavailable") from exc
    if resolved_root not in resolved.parents:
        raise SegmentationValidationError("Provider mask artifact contract is unsafe")
    return path


def _load_source_metadata(source: CanonicalSegmentationSource) -> dict[str, object]:
    try:
        payload = json.loads(source.metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SegmentationValidationError("Canonical source metadata is unreadable") from exc
    if not isinstance(payload, dict) or _canonical_sha256(payload) != source.descriptor_sha256:
        raise SegmentationValidationError("Canonical source metadata changed after segmentation")
    expected_shape = _shape(payload.get("shape"))
    if payload.get("axis_order") != list(AXIS_ORDER):
        raise SegmentationValidationError("Canonical source axis order is unsupported")
    spacing = _float_tuple(payload.get("spacing_mm"), 3, "Canonical source spacing")
    if any(item <= 0 for item in spacing):
        raise SegmentationValidationError("Canonical source spacing is invalid")
    _matrix(payload.get("array_index_to_patient_lps"), "Canonical source Patient LPS affine")
    if np is None:
        raise SegmentationValidationError("Canonical label-map import requires numpy")
    try:
        array = np.load(source.volume_path, mmap_mode="r", allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise SegmentationValidationError("Canonical source artifact is unreadable") from exc
    if tuple(array.shape) != expected_shape or str(array.dtype) != str(payload.get("dtype") or ""):
        raise SegmentationValidationError("Canonical source artifact changed after segmentation")
    return payload


def _validate_report(
    report: object,
    *,
    source: CanonicalSegmentationSource,
    source_metadata: dict[str, object],
    provider_mask_sha256: str,
    expected_labels: tuple[int, ...],
    maximum_label: int,
    output_path: Path,
) -> dict[str, object]:
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != LABEL_MAP_WORKER_SCHEMA_VERSION
        or report.get("operation") != "canonicalize_label_map"
    ):
        raise SegmentationValidationError("Label-map worker report is invalid")
    if report.get("source_artifact_sha256") != source.artifact_sha256:
        raise SegmentationValidationError("Canonical source changed during label-map import")
    if report.get("source_descriptor_sha256") != source.descriptor_sha256:
        raise SegmentationValidationError(
            "Canonical source metadata changed during label-map import"
        )
    if report.get("provider_mask_sha256") != provider_mask_sha256:
        raise SegmentationValidationError("Provider mask changed during label-map import")
    if report.get("dtype") != CANONICAL_DTYPE:
        raise SegmentationValidationError("Canonical label-map dtype is invalid")
    if report.get("axis_order") != list(AXIS_ORDER):
        raise SegmentationValidationError("Canonical label-map axis order is invalid")
    if report.get("coordinate_system") != CANONICAL_COORDINATE_SYSTEM:
        raise SegmentationValidationError("Canonical label-map coordinate system is invalid")
    if report.get("length_units") != CANONICAL_LENGTH_UNITS:
        raise SegmentationValidationError("Canonical label-map length units are invalid")
    if report.get("resampled") is not False or report.get("interpolation") != "none":
        raise SegmentationValidationError("Phase 5C does not permit silent label-map resampling")

    expected_shape = _shape(source_metadata.get("shape"))
    if _shape(report.get("shape")) != expected_shape:
        raise SegmentationValidationError("Canonical label-map shape changed")
    source_affine = _matrix(
        source_metadata.get("array_index_to_patient_lps"),
        "Canonical source Patient LPS affine",
    )
    output_affine = _matrix(
        report.get("array_index_to_patient_lps"),
        "Canonical label-map Patient LPS affine",
    )
    model_affine = _matrix(
        report.get("model_index_to_patient_lps"),
        "Model Patient LPS affine",
    )
    source_to_model = _matrix(
        report.get("source_to_model_index"),
        "Source-to-model transform",
    )
    model_to_source = _matrix(
        report.get("model_to_source_index"),
        "Model-to-source transform",
    )
    assert np is not None
    source_array = np.asarray(source_affine, dtype=np.float64)
    model_array = np.asarray(model_affine, dtype=np.float64)
    if not np.allclose(
        output_affine,
        source_affine,
        rtol=0.0,
        atol=NIFTI_GEOMETRY_ATOL_MM,
    ):
        raise SegmentationValidationError("Canonical label-map Patient LPS geometry changed")
    if not np.allclose(
        model_array,
        source_array,
        rtol=0.0,
        atol=NIFTI_GEOMETRY_ATOL_MM,
    ):
        raise SegmentationValidationError("Model Patient LPS geometry changed")
    expected_source_to_model = np.linalg.inv(model_array) @ source_array
    expected_model_to_source = np.linalg.inv(source_array) @ model_array
    if not np.allclose(
        source_to_model,
        expected_source_to_model,
        rtol=0.0,
        atol=INDEX_TRANSFORM_ATOL,
    ):
        raise SegmentationValidationError("Source-to-model transform is invalid")
    if not np.allclose(
        model_to_source,
        expected_model_to_source,
        rtol=0.0,
        atol=INDEX_TRANSFORM_ATOL,
    ):
        raise SegmentationValidationError("Model-to-source transform is invalid")
    if not np.allclose(
        np.asarray(source_to_model) @ np.asarray(model_to_source),
        np.eye(4),
        rtol=0.0,
        atol=INDEX_TRANSFORM_ATOL,
    ):
        raise SegmentationValidationError("Label-map transforms are not invertible")

    labels = _labels(report.get("present_labels"), maximum=maximum_label)
    if labels != expected_labels:
        raise SegmentationValidationError("Segmentation label inventory changed during import")
    minimum = _nonnegative_int(report.get("minimum_label"), "Minimum label")
    maximum = _nonnegative_int(report.get("maximum_label"), "Maximum label")
    if minimum != labels[0] or maximum != labels[-1]:
        raise SegmentationValidationError("Segmentation label range is invalid")
    nonzero = _nonnegative_int(report.get("nonzero_voxels"), "Nonzero voxel count")
    output_bytes = _positive_int(
        report.get("canonical_label_map_bytes"), "Canonical label-map byte count"
    )
    digest = _sha256_value(
        report.get("canonical_label_map_sha256"), "Canonical label-map digest"
    )
    if output_path.is_symlink() or not output_path.is_file():
        raise SegmentationValidationError("Canonical label-map worker output is unavailable")
    if output_path.stat().st_size != output_bytes or _sha256_file(output_path) != digest:
        raise SegmentationValidationError("Canonical label-map worker output changed")
    try:
        array = np.load(output_path, mmap_mode="r", allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise SegmentationValidationError(
            "Canonical label-map worker output is unreadable"
        ) from exc
    if tuple(array.shape) != expected_shape or str(array.dtype) != CANONICAL_DTYPE:
        raise SegmentationValidationError("Canonical label-map worker output is invalid")
    actual_labels = tuple(int(item) for item in np.unique(array))
    if actual_labels != labels or int(np.count_nonzero(array)) != nonzero:
        raise SegmentationValidationError(
            "Canonical label-map worker output label inventory changed"
        )

    return {
        "artifact_sha256": digest,
        "artifact_bytes": output_bytes,
        "shape": list(expected_shape),
        "dtype": CANONICAL_DTYPE,
        "axis_order": list(AXIS_ORDER),
        "coordinate_system": CANONICAL_COORDINATE_SYSTEM,
        "length_units": CANONICAL_LENGTH_UNITS,
        "spacing_mm": list(_float_tuple(source_metadata.get("spacing_mm"), 3, "spacing")),
        "array_index_to_patient_lps": [list(row) for row in source_affine],
        "model_index_to_patient_lps": [list(row) for row in model_affine],
        "source_to_model_index": [list(row) for row in source_to_model],
        "model_to_source_index": [list(row) for row in model_to_source],
        "resampled": False,
        "interpolation": "none",
        "present_labels": list(labels),
        "nonzero_voxels": nonzero,
    }


class SegmentationLabelMapService:
    """Provider-neutral immutable canonical label-map repository for Phase 5C."""

    def __init__(
        self,
        *,
        data_dir: Path,
        worker_runner: WorkerRunner = subprocess.run,
        clock: Clock = _utc_now,
        job_service: SegmentationJobService | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.segmentation_root = self.data_dir / "segmentation"
        self.maps_root = self.segmentation_root / "label-maps"
        _safe_repository(self.maps_root)
        self._worker_runner = worker_runner
        self._clock = clock
        self._job_service = (
            job_service
            if job_service is not None
            else SegmentationJobService(data_dir=self.data_dir)
        )

    def _ensure_root(self) -> None:
        _safe_repository(self.maps_root)
        self.segmentation_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.maps_root.mkdir(exist_ok=True, mode=0o700)
        os.chmod(self.maps_root, 0o700)

    @staticmethod
    def _validate_id(label_map_id: str) -> str:
        value = str(label_map_id).strip().lower()
        if LABEL_MAP_ID_PATTERN.fullmatch(value) is None:
            raise SegmentationValidationError("Canonical label-map identifier is invalid")
        return value

    def _job_contract(
        self, job_id: str
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
        CanonicalSegmentationSource,
        dict[str, object],
        Path,
        str,
        tuple[int, ...],
        int,
    ]:
        job = self._job_service.get_job(job_id)
        if job.get("state") != "succeeded":
            raise SegmentationValidationError(
                "Only succeeded segmentation jobs can produce canonical label maps"
            )
        provenance = job.get("provenance")
        outcome = job.get("outcome")
        if not isinstance(provenance, dict) or not isinstance(outcome, dict):
            raise SegmentationValidationError("Succeeded segmentation job is incomplete")
        terminal_digest = _sha256_value(
            job.get("terminal_provenance_sha256"), "Segmentation terminal provenance digest"
        )
        if outcome.get("code") != "qualified_execution":
            raise SegmentationValidationError("Segmentation job output is not qualified for import")
        if outcome.get("clinical_validation") != "not_claimed":
            raise SegmentationValidationError("Segmentation clinical-validation boundary changed")
        source_id = str(provenance.get("source_study_id") or "")
        source = CanonicalSegmentationSourceRepository(self.data_dir).load(source_id)
        if (
            source.descriptor_sha256 != provenance.get("canonical_volume_descriptor_sha256")
            or source.artifact_sha256 != provenance.get("canonical_volume_artifact_sha256")
            or source.source_series_uid != provenance.get("source_series_uid")
            or source.study_instance_uid != provenance.get("source_study_instance_uid")
        ):
            raise SegmentationValidationError("Canonical source changed after segmentation")
        source_metadata = _load_source_metadata(source)
        provider = outcome.get("provider")
        if not isinstance(provider, dict):
            raise SegmentationValidationError("Segmentation provider provenance is incomplete")
        maximum_label = _positive_int(
            provider.get("class_count"), "Segmentation class count", maximum=65535
        )
        task_definition = _sha256_value(
            provider.get("task_definition_sha256"), "Segmentation task definition digest"
        )
        del task_definition
        expected_labels = _labels(outcome.get("present_labels"), maximum=maximum_label)
        expected_mask_sha256 = _sha256_value(
            outcome.get("mask_nifti_sha256"), "Provider mask digest"
        )
        job_root = self.segmentation_root / "jobs" / str(job["job_id"])
        mask_path = _safe_relative_artifact(outcome.get("mask_artifact"), job_root=job_root)
        if _sha256_file(mask_path) != expected_mask_sha256:
            raise SegmentationValidationError("Provider mask artifact changed after segmentation")
        return (
            job,
            provenance,
            outcome,
            source,
            source_metadata,
            mask_path,
            terminal_digest,
            expected_labels,
            maximum_label,
        )

    def _find_existing(self, job_id: str, mask_sha256: str) -> dict[str, object] | None:
        if not self.maps_root.is_dir():
            return None
        for path in sorted(self.maps_root.iterdir()):
            if not path.is_dir() or LABEL_MAP_ID_PATTERN.fullmatch(path.name) is None:
                continue
            descriptor = self._load(path.name)
            if (
                descriptor.get("segmentation_job_id") == job_id
                and descriptor.get("provider_mask_sha256") == mask_sha256
            ):
                return descriptor
        return None

    def _invoke_worker(
        self,
        *,
        python_executable: str,
        worker_script: Path,
        source: CanonicalSegmentationSource,
        mask_path: Path,
        output_path: Path,
        maximum_label: int,
        timeout_seconds: float,
    ) -> object:
        if (
            not isinstance(python_executable, str)
            or not python_executable.strip()
            or len(python_executable) > 4096
            or any(ord(character) < 32 for character in python_executable)
        ):
            raise SegmentationValidationError("Label-map worker Python is invalid")
        worker = Path(worker_script)
        if (
            not worker.is_absolute()
            or worker.suffix != ".py"
            or worker.is_symlink()
            or not worker.is_file()
        ):
            raise SegmentationValidationError("Label-map worker script is invalid")
        if timeout_seconds <= 0 or timeout_seconds > MAX_IMPORT_TIMEOUT_SECONDS:
            raise SegmentationValidationError("Label-map worker timeout is invalid")
        command = [
            python_executable.strip(),
            "-I",
            str(worker.resolve(strict=True)),
            "--source-npy",
            str(source.volume_path.resolve(strict=True)),
            "--source-json",
            str(source.metadata_path.resolve(strict=True)),
            "--mask-nifti",
            str(mask_path.resolve(strict=True)),
            "--output-npy",
            str(output_path.resolve(strict=False)),
            "--maximum-label",
            str(maximum_label),
        ]
        try:
            completed = self._worker_runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=float(timeout_seconds),
                shell=False,
                cwd=str(output_path.parent),
            )
        except subprocess.TimeoutExpired as exc:
            raise SegmentationValidationError("Canonical label-map import timed out") from exc
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            raise SegmentationValidationError("Canonical label-map worker is unavailable") from exc
        if getattr(completed, "returncode", None) != 0:
            raise SegmentationValidationError("Canonical label-map worker failed")
        stdout = getattr(completed, "stdout", None)
        if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_WORKER_REPORT_BYTES:
            raise SegmentationValidationError("Canonical label-map worker report is invalid")
        try:
            lines = [line for line in stdout.splitlines() if line.strip()]
            if not lines:
                raise ValueError("empty")
            return json.loads(lines[-1])
        except (ValueError, json.JSONDecodeError, UnicodeError) as exc:
            raise SegmentationValidationError(
                "Canonical label-map worker report is invalid"
            ) from exc

    def import_succeeded_job(
        self,
        *,
        job_id: str,
        python_executable: str,
        worker_script: Path,
        timeout_seconds: float = 30 * 60,
        expected_nonzero_voxels: int | None = None,
    ) -> dict[str, object]:
        (
            job,
            provenance,
            outcome,
            source,
            source_metadata,
            mask_path,
            terminal_digest,
            expected_labels,
            maximum_label,
        ) = self._job_contract(job_id)
        if expected_nonzero_voxels is not None and (
            type(expected_nonzero_voxels) is not int or expected_nonzero_voxels <= 0
            or outcome.get("nonzero_voxels") != expected_nonzero_voxels
        ):
            raise SegmentationValidationError("Expected provider nonzero count is invalid")
        mask_digest = str(outcome["mask_nifti_sha256"])
        existing = self._find_existing(str(job["job_id"]), mask_digest)
        if existing is not None:
            return existing

        self._ensure_root()
        stage = self.maps_root / f".import-{secrets.token_hex(16)}"
        stage.mkdir(mode=0o700)
        output_path = stage / "labels.npy"
        try:
            report = self._invoke_worker(
                python_executable=python_executable,
                worker_script=worker_script,
                source=source,
                mask_path=mask_path,
                output_path=output_path,
                maximum_label=maximum_label,
                timeout_seconds=timeout_seconds,
            )
            artifact = _validate_report(
                report,
                source=source,
                source_metadata=source_metadata,
                provider_mask_sha256=mask_digest,
                expected_labels=expected_labels,
                maximum_label=maximum_label,
                output_path=output_path,
            )
            if (expected_nonzero_voxels is not None
                    and artifact["nonzero_voxels"] != expected_nonzero_voxels):
                raise SegmentationValidationError(
                    "Canonical MRI nonzero count differs from accepted provider mask"
                )
            provider = outcome["provider"]
            assert isinstance(provider, dict)
            label_provenance: dict[str, object] = {
                "source_study_id": source.study_id,
                "source_study_instance_uid": source.study_instance_uid,
                "source_series_uid": source.source_series_uid,
                "source_modality": source.modality,
                "source_volume_created_at_utc": source.volume_created_at_utc,
                "source_volume_descriptor_sha256": source.descriptor_sha256,
                "source_volume_artifact_sha256": source.artifact_sha256,
                "segmentation_job_id": job["job_id"],
                "segmentation_terminal_provenance_sha256": terminal_digest,
                "provider_id": provenance.get("provider_id"),
                "provider_version": provenance.get("provider_version"),
                "model_id": provenance.get("model_id"),
                "model_version": provenance.get("model_version"),
                "model_descriptor_sha256": provenance.get("model_descriptor_sha256"),
                "task": provider.get("task"),
                "task_definition_sha256": provider.get("task_definition_sha256"),
                "class_count": maximum_label,
                "provider_mask_sha256": mask_digest,
                "model_index_to_patient_lps": artifact["model_index_to_patient_lps"],
                "source_to_model_index": artifact["source_to_model_index"],
                "model_to_source_index": artifact["model_to_source_index"],
                "resampled": False,
                "interpolation": "none",
                "clinical_validation": "not_claimed",
            }
            identity = {
                "provenance": label_provenance,
                "artifact_sha256": artifact["artifact_sha256"],
            }
            identity_sha256 = _canonical_sha256(identity)
            label_map_id = f"map-{identity_sha256[:32]}"
            created = self._clock()
            if not isinstance(created, datetime):
                raise SegmentationValidationError("Label-map clock is invalid")
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            manifest = {
                "schema_version": LABEL_MAP_SCHEMA_VERSION,
                "label_map_id": label_map_id,
                "state": "ready",
                "created_at_utc": created.astimezone(timezone.utc).isoformat(),
                "identity_sha256": identity_sha256,
                "provenance": label_provenance,
                "provenance_sha256": _canonical_sha256(label_provenance),
                "artifact": artifact
                | {
                    "representation": "label_map",
                    "artifact_format": "npy",
                    "artifact_path": "labels.npy",
                    "metadata_path": "manifest.json",
                },
            }
            manifest_path = stage / "manifest.json"
            with manifest_path.open("x", encoding="utf-8") as handle:
                os.chmod(manifest_path, 0o600)
                handle.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(output_path, 0o600)
            final = self.maps_root / label_map_id
            if final.exists():
                shutil.rmtree(stage)
                return self._load(label_map_id)
            os.replace(stage, final)
            return self._load(label_map_id)
        except Exception:
            if stage.exists() and stage.is_dir() and not stage.is_symlink():
                shutil.rmtree(stage, ignore_errors=True)
            raise

    def _load(self, label_map_id: str) -> dict[str, object]:
        value = self._validate_id(label_map_id)
        root = self.maps_root / value
        manifest_path = root / "manifest.json"
        artifact_path = root / "labels.npy"
        if (
            root.is_symlink()
            or not root.is_dir()
            or manifest_path.is_symlink()
            or not manifest_path.is_file()
            or artifact_path.is_symlink()
            or not artifact_path.is_file()
        ):
            raise SegmentationNotFoundError("Canonical label map was not found")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SegmentationValidationError("Canonical label-map manifest is unreadable") from exc
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != LABEL_MAP_SCHEMA_VERSION
            or manifest.get("label_map_id") != value
            or manifest.get("state") != "ready"
        ):
            raise SegmentationValidationError("Canonical label-map manifest is invalid")
        provenance = manifest.get("provenance")
        artifact = manifest.get("artifact")
        if (
            not isinstance(provenance, dict)
            or manifest.get("provenance_sha256") != _canonical_sha256(provenance)
            or not isinstance(artifact, dict)
        ):
            raise SegmentationValidationError("Canonical label-map provenance changed")
        if (
            artifact.get("artifact_path") != "labels.npy"
            or artifact.get("metadata_path") != "manifest.json"
        ):
            raise SegmentationValidationError("Canonical label-map artifact contract is invalid")
        digest = _sha256_value(artifact.get("artifact_sha256"), "Canonical label-map digest")
        if _sha256_file(artifact_path) != digest:
            raise SegmentationValidationError("Canonical label-map artifact changed")
        expected_identity = _canonical_sha256(
            {"provenance": provenance, "artifact_sha256": digest}
        )
        if (
            manifest.get("identity_sha256") != expected_identity
            or value != f"map-{expected_identity[:32]}"
        ):
            raise SegmentationValidationError("Canonical label-map identity changed")

        source = CanonicalSegmentationSourceRepository(self.data_dir).load(
            str(provenance.get("source_study_id") or "")
        )
        if (
            source.descriptor_sha256 != provenance.get("source_volume_descriptor_sha256")
            or source.artifact_sha256 != provenance.get("source_volume_artifact_sha256")
            or source.source_series_uid != provenance.get("source_series_uid")
        ):
            raise SegmentationConflictError("Canonical label-map source binding changed")
        job = self._job_service.get_job(
            str(provenance.get("segmentation_job_id") or "")
        )
        outcome = job.get("outcome")
        if (
            job.get("state") != "succeeded"
            or job.get("terminal_provenance_sha256")
            != provenance.get("segmentation_terminal_provenance_sha256")
            or not isinstance(outcome, dict)
            or outcome.get("mask_nifti_sha256") != provenance.get("provider_mask_sha256")
        ):
            raise SegmentationConflictError("Canonical label-map job binding changed")

        shape = _shape(artifact.get("shape"))
        labels = _labels(
            artifact.get("present_labels"),
            maximum=_positive_int(provenance.get("class_count"), "class count", maximum=65535),
        )
        if artifact.get("dtype") != CANONICAL_DTYPE:
            raise SegmentationValidationError("Canonical label-map dtype changed")
        if np is None:
            raise SegmentationValidationError("Canonical label-map inspection requires numpy")
        try:
            array = np.load(artifact_path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise SegmentationValidationError("Canonical label-map artifact is unreadable") from exc
        if tuple(array.shape) != shape or str(array.dtype) != CANONICAL_DTYPE:
            raise SegmentationValidationError("Canonical label-map artifact descriptor changed")
        if tuple(int(item) for item in np.unique(array)) != labels:
            raise SegmentationValidationError(
                "Canonical label-map artifact label inventory changed"
            )
        if int(np.count_nonzero(array)) != _nonnegative_int(
            artifact.get("nonzero_voxels"), "nonzero voxel count"
        ):
            raise SegmentationValidationError("Canonical label-map nonzero count changed")
        if artifact_path.stat().st_size != _positive_int(
            artifact.get("artifact_bytes"), "artifact byte count"
        ):
            raise SegmentationValidationError("Canonical label-map artifact size changed")
        _matrix(artifact.get("array_index_to_patient_lps"), "Patient LPS affine")
        _matrix(provenance.get("source_to_model_index"), "Source-to-model transform")
        _matrix(provenance.get("model_to_source_index"), "Model-to-source transform")
        return self._public(manifest)

    @staticmethod
    def _public(manifest: dict[str, object]) -> dict[str, object]:
        provenance = manifest["provenance"]
        artifact = manifest["artifact"]
        assert isinstance(provenance, dict) and isinstance(artifact, dict)
        return {
            "label_map_id": manifest["label_map_id"],
            "state": "ready",
            "created_at_utc": manifest["created_at_utc"],
            "identity_sha256": manifest["identity_sha256"],
            "provenance_sha256": manifest["provenance_sha256"],
            "source_study_id": provenance["source_study_id"],
            "source_study_instance_uid": provenance["source_study_instance_uid"],
            "source_series_uid": provenance["source_series_uid"],
            "source_modality": provenance["source_modality"],
            "source_volume_descriptor_sha256": provenance[
                "source_volume_descriptor_sha256"
            ],
            "source_volume_artifact_sha256": provenance["source_volume_artifact_sha256"],
            "segmentation_job_id": provenance["segmentation_job_id"],
            "segmentation_terminal_provenance_sha256": provenance[
                "segmentation_terminal_provenance_sha256"
            ],
            "provider_id": provenance["provider_id"],
            "provider_version": provenance["provider_version"],
            "model_id": provenance["model_id"],
            "model_version": provenance["model_version"],
            "model_descriptor_sha256": provenance["model_descriptor_sha256"],
            "task": provenance["task"],
            "task_definition_sha256": provenance["task_definition_sha256"],
            "class_count": provenance["class_count"],
            "provider_mask_sha256": provenance["provider_mask_sha256"],
            "coordinate_system": artifact["coordinate_system"],
            "length_units": artifact["length_units"],
            "representation": artifact["representation"],
            "artifact_format": artifact["artifact_format"],
            "artifact_sha256": artifact["artifact_sha256"],
            "artifact_bytes": artifact["artifact_bytes"],
            "shape": artifact["shape"],
            "dtype": artifact["dtype"],
            "axis_order": artifact["axis_order"],
            "spacing_mm": artifact["spacing_mm"],
            "array_index_to_patient_lps": artifact["array_index_to_patient_lps"],
            "model_index_to_patient_lps": provenance["model_index_to_patient_lps"],
            "source_to_model_index": provenance["source_to_model_index"],
            "model_to_source_index": provenance["model_to_source_index"],
            "resampled": provenance["resampled"],
            "interpolation": provenance["interpolation"],
            "present_labels": artifact["present_labels"],
            "nonzero_voxels": artifact["nonzero_voxels"],
            "clinical_validation": provenance["clinical_validation"],
        }

    def get(self, label_map_id: str) -> dict[str, object]:
        _safe_repository(self.maps_root)
        return self._load(label_map_id)

    def list(self, *, study_id: str | None = None) -> list[dict[str, object]]:
        _safe_repository(self.maps_root)
        if study_id is not None and re.fullmatch(r"[0-9a-f]{32}", str(study_id)) is None:
            raise SegmentationValidationError("Stored source study identity is invalid")
        if not self.maps_root.is_dir():
            return []
        descriptors: list[dict[str, object]] = []
        for path in self.maps_root.iterdir():
            if not path.is_dir() or LABEL_MAP_ID_PATTERN.fullmatch(path.name) is None:
                continue
            try:
                descriptor = self._load(path.name)
            except (
                SegmentationValidationError,
                SegmentationConflictError,
                SegmentationNotFoundError,
            ):
                continue
            if study_id is None or descriptor["source_study_id"] == study_id:
                descriptors.append(descriptor)
        descriptors.sort(
            key=lambda item: (str(item["created_at_utc"]), str(item["label_map_id"])),
            reverse=True,
        )
        return descriptors
