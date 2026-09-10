from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import struct
import subprocess
import tempfile
from typing import Callable

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover
    np = None  # type: ignore[assignment]

from .segmentation_surface_runtime import (
    SegmentationSurfaceRuntimeQualifier,
    SegmentationSurfaceRuntimeReport,
)
from .volume_rendering import (
    CanonicalVolumeRenderingSource,
    VolumeRenderingService,
    VolumeRenderingValidationError,
)


VOLUME_SURFACE_SCHEMA_VERSION = 1
VOLUME_SURFACE_MEDIA_TYPE = "application/x-voxelatlas-volume-surface-v1"
VOLUME_SURFACE_MAGIC = b"VXVS"
VOLUME_SURFACE_HEADER = struct.Struct("<4s7I")
VOLUME_SURFACE_FLAGS = 1
VOLUME_SURFACE_EXTRACTION = "marching_cubes_isovalue"
VOLUME_SURFACE_QUALITY = "native"
DEFAULT_CT_BONE_ISOVALUE_HU = 300.0
MAX_VOLUME_SURFACE_VERTICES = 2_000_000
MAX_VOLUME_SURFACE_TRIANGLES = 4_000_000
MAX_VOLUME_SURFACE_PAYLOAD_BYTES = 160 * 1024 * 1024
MAX_VOLUME_SURFACE_WORKER_REPORT_BYTES = 64 * 1024
MAX_VOLUME_SURFACE_WORKER_TIMEOUT_SECONDS = 240.0
MAX_VOLUME_SURFACE_DEGENERATE_TRIANGLE_FRACTION = 1e-4
WORKER_FAILURE_CODES = frozenset({
    "request_contract_invalid",
    "volume_shape_invalid",
    "patient_lps_affine_invalid",
    "source_value_range_invalid",
    "isovalue_invalid",
    "runtime_changed",
    "source_volume_changed",
    "source_volume_contract_changed",
    "no_extractable_surface",
    "geometry_budget_exceeded",
    "orientation_reference_invalid",
    "cleanup_input_invalid",
    "degenerate_face_budget_exceeded",
    "cleanup_failed",
    "orientation_ambiguous",
    "normals_invalid",
    "payload_budget_exceeded",
    "worker_execution_failed",
})

WorkerRunner = Callable[..., object]


class VolumeSurfaceError(ValueError):
    """Base class for direct canonical-volume surface failures."""


class VolumeSurfaceUnavailableError(VolumeSurfaceError):
    pass


class VolumeSurfaceValidationError(VolumeSurfaceError):
    pass


@dataclass(frozen=True, slots=True)
class VolumeDerivedSurface:
    study_id: str
    source_series_uid: str
    source_type: str
    source_modality: str
    intensity_units: str
    isovalue: float
    quality: str
    extraction: str
    coordinate_system: str
    vertex_count: int
    triangle_count: int
    bounds_lps_mm: tuple[float, float, float, float, float, float]
    payload_sha256: str
    payload: bytes
    surface_id: str
    provenance_sha256: str
    runtime_fingerprint_sha256: str
    raw_vertex_count: int = 0
    raw_triangle_count: int = 0
    degenerate_triangle_count: int = 0
    degenerate_triangle_fraction: float = 0.0
    unreferenced_vertex_count: int = 0
    schema_version: int = VOLUME_SURFACE_SCHEMA_VERSION
    media_type: str = VOLUME_SURFACE_MEDIA_TYPE


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
        raise VolumeSurfaceValidationError("Volume-derived surface metadata is invalid") from exc


def _canonical_sha256(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise VolumeSurfaceValidationError("Canonical patient volume is unreadable") from exc
    return digest.hexdigest()


def _worker_failure_reason(stdout: object) -> str:
    if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_VOLUME_SURFACE_WORKER_REPORT_BYTES:
        return "worker_execution_failed"
    try:
        lines = [line for line in stdout.splitlines() if line.strip()]
        report = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError, UnicodeError):
        return "worker_execution_failed"
    if not isinstance(report, dict) or report.get("status") != "failed":
        return "worker_execution_failed"
    code = report.get("error_code")
    if not isinstance(code, str) or code not in WORKER_FAILURE_CODES:
        return "worker_execution_failed"
    return code


def _validated_isovalue(source: CanonicalVolumeRenderingSource, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VolumeSurfaceValidationError("Volume surface isovalue must be numeric")
    isovalue = float(value)
    if not isfinite(isovalue):
        raise VolumeSurfaceValidationError("Volume surface isovalue must be finite")
    low, high = source.value_range
    if not low < isovalue < high:
        raise VolumeSurfaceValidationError(
            "Volume surface isovalue must be strictly inside the canonical volume value range"
        )
    return isovalue


def _decode_payload(payload: bytes) -> tuple[int, int, tuple[float, float, float, float, float, float]]:
    if np is None:
        raise VolumeSurfaceValidationError("Volume surface validation requires numpy")
    if len(payload) < VOLUME_SURFACE_HEADER.size:
        raise VolumeSurfaceValidationError("Volume surface payload is truncated")
    try:
        magic, version, vertex_count, index_count, pos_bytes, normal_bytes, index_bytes, flags = (
            VOLUME_SURFACE_HEADER.unpack_from(payload)
        )
    except struct.error as exc:
        raise VolumeSurfaceValidationError("Volume surface payload header is invalid") from exc
    if (
        magic != VOLUME_SURFACE_MAGIC
        or version != VOLUME_SURFACE_SCHEMA_VERSION
        or flags != VOLUME_SURFACE_FLAGS
        or vertex_count <= 0
        or index_count <= 0
        or index_count % 3 != 0
        or vertex_count > MAX_VOLUME_SURFACE_VERTICES
        or index_count // 3 > MAX_VOLUME_SURFACE_TRIANGLES
        or pos_bytes != vertex_count * 3 * 4
        or normal_bytes != vertex_count * 3 * 4
        or index_bytes != index_count * 4
        or len(payload) != VOLUME_SURFACE_HEADER.size + pos_bytes + normal_bytes + index_bytes
        or len(payload) > MAX_VOLUME_SURFACE_PAYLOAD_BYTES
    ):
        raise VolumeSurfaceValidationError("Volume surface payload contract is invalid")
    offset = VOLUME_SURFACE_HEADER.size
    positions = np.frombuffer(payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape(-1, 3)
    offset += pos_bytes
    normals = np.frombuffer(payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape(-1, 3)
    offset += normal_bytes
    indices = np.frombuffer(payload, dtype="<u4", count=index_count, offset=offset)
    if (
        not np.all(np.isfinite(positions))
        or not np.all(np.isfinite(normals))
        or np.any(indices >= vertex_count)
    ):
        raise VolumeSurfaceValidationError("Volume surface payload geometry is invalid")
    lengths = np.linalg.norm(normals.astype(np.float64), axis=1)
    if np.any(lengths <= 1e-6) or not np.all(np.isfinite(lengths)):
        raise VolumeSurfaceValidationError("Volume surface normals are invalid")
    bounds = tuple(
        float(item) for item in np.concatenate((positions.min(axis=0), positions.max(axis=0)))
    )
    return int(vertex_count), int(index_count // 3), bounds  # type: ignore[return-value]


class VolumeSurfaceService:
    """Native Patient-LPS isosurfaces derived directly from the canonical patient volume."""

    def __init__(
        self,
        *,
        data_dir: Path,
        volume_rendering_service: VolumeRenderingService | None = None,
        worker_python: str | None = None,
        worker_script: Path | None = None,
        runtime_qualifier: SegmentationSurfaceRuntimeQualifier | None = None,
        runner: WorkerRunner = subprocess.run,
        timeout_seconds: float = MAX_VOLUME_SURFACE_WORKER_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 900:
            raise ValueError("volume surface worker timeout is invalid")
        self.volume_rendering_service = volume_rendering_service or VolumeRenderingService(
            data_dir=data_dir
        )
        self.worker_python = str(worker_python or "").strip() or None
        self.worker_script = worker_script
        self.runtime_qualifier = runtime_qualifier or SegmentationSurfaceRuntimeQualifier()
        self.runner = runner
        self.timeout_seconds = float(timeout_seconds)
        self._cache: dict[tuple[str, str, str, str], VolumeDerivedSurface] = {}

    def _source_latest(self) -> CanonicalVolumeRenderingSource:
        try:
            source = self.volume_rendering_service.source_latest()
        except VolumeRenderingValidationError as exc:
            raise VolumeSurfaceValidationError(str(exc)) from exc
        if not isinstance(source.study_dir, Path) or not source.study_dir.name:
            raise VolumeSurfaceValidationError("Canonical patient volume study identity is invalid")
        if source.volume_path.is_symlink() or not source.volume_path.is_file():
            raise VolumeSurfaceValidationError("Canonical patient volume artifact is unsafe")
        return source

    @staticmethod
    def _assert_ct_source(source: CanonicalVolumeRenderingSource) -> None:
        if source.modality != "CT" or source.intensity_units != "HU":
            raise VolumeSurfaceUnavailableError(
                "Phase 6D1 qualifies direct volume-derived surfaces for CT HU volumes only; "
                "MRI intensity is not silently thresholded"
            )

    def descriptor_latest(self) -> dict[str, object]:
        source = self._source_latest()
        low, high = source.value_range
        ct_qualified = source.modality == "CT" and source.intensity_units == "HU"
        runtime_configured = self.worker_python is not None
        bone_available = low < DEFAULT_CT_BONE_ISOVALUE_HU < high
        available = ct_qualified and runtime_configured and low < high
        reason = None
        if not ct_qualified:
            reason = "CT HU volume-derived surfaces are qualified in Phase 6D1; MRI is not silently thresholded"
        elif not runtime_configured:
            reason = "Volume surface runtime is not configured"
        elif not low < high:
            reason = "Canonical volume intensity range is not suitable for isosurface extraction"
        return {
            "schema_version": VOLUME_SURFACE_SCHEMA_VERSION,
            "available": available,
            "reason": reason,
            "study_id": source.study_dir.name,
            "source_type": "canonical_volume",
            "source_series_uid": source.source_series_uid,
            "source_modality": source.modality,
            "source_intensity_units": source.intensity_units,
            "source_value_range": [float(low), float(high)],
            "default_isovalue": DEFAULT_CT_BONE_ISOVALUE_HU if bone_available else None,
            "presets": ([{
                "id": "bone",
                "label": "Bone",
                "isovalue": DEFAULT_CT_BONE_ISOVALUE_HU,
                "units": "HU",
            }] if ct_qualified and bone_available else []),
            "custom_isovalue_supported": bool(ct_qualified),
            "quality": VOLUME_SURFACE_QUALITY,
            "extraction": VOLUME_SURFACE_EXTRACTION,
            "coordinate_system": "patient_lps",
            "length_units": "mm",
            "segmentation_required": False,
            "source_volume_immutable": True,
            "runtime_configured": runtime_configured,
            "clinical_validation": "not_claimed",
        }

    def _runtime(self) -> SegmentationSurfaceRuntimeReport:
        report = self.runtime_qualifier.qualify(self.worker_python)
        if not report.qualified or not report.runtime_fingerprint_sha256:
            raise VolumeSurfaceUnavailableError(report.message)
        return report

    def surface_latest(self, *, isovalue: float) -> VolumeDerivedSurface:
        source = self._source_latest()
        self._assert_ct_source(source)
        level = _validated_isovalue(source, isovalue)
        if self.worker_script is None or not self.worker_script.is_file() or self.worker_script.is_symlink():
            raise VolumeSurfaceUnavailableError("Volume surface worker is unavailable")
        runtime = self._runtime()
        assert runtime.runtime_fingerprint_sha256 is not None
        source_sha = _sha256_file(source.volume_path)
        cache_key = (
            source.study_dir.name,
            source_sha,
            level.hex(),
            runtime.runtime_fingerprint_sha256,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        request = {
            "schema_version": VOLUME_SURFACE_SCHEMA_VERSION,
            "operation": "extract_volume_isosurface",
            "extraction": VOLUME_SURFACE_EXTRACTION,
            "source_type": "canonical_volume",
            "source_volume": "immutable",
            "source_modality": source.modality,
            "source_intensity_units": source.intensity_units,
            "source_value_range": [float(item) for item in source.value_range],
            "source_descriptor_sha256": source.source_descriptor_sha256,
            "expected_volume_sha256": source_sha,
            "shape": [int(item) for item in source.shape],
            "array_index_to_patient_lps": [
                [float(item) for item in row] for row in source.array_index_to_patient_lps
            ],
            "isovalue": level,
            "coordinate_system": "patient_lps",
            "expected_runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
            "max_vertices": MAX_VOLUME_SURFACE_VERTICES,
            "max_triangles": MAX_VOLUME_SURFACE_TRIANGLES,
            "max_payload_bytes": MAX_VOLUME_SURFACE_PAYLOAD_BYTES,
            "clinical_validation": "not_claimed",
        }

        with tempfile.TemporaryDirectory(prefix="voxelatlas-volume-surface-") as tmp:
            temp_root = Path(tmp)
            request_path = temp_root / "request.json"
            output_path = temp_root / "surface.vxvs"
            request_path.write_bytes(_canonical_json(request))
            command = [
                str(self.worker_python),
                "-I",
                str(self.worker_script),
                "--volume-npy",
                str(source.volume_path),
                "--request-json",
                str(request_path),
                "--output-surface",
                str(output_path),
            ]
            try:
                completed = self.runner(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    shell=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise VolumeSurfaceUnavailableError("Volume surface worker failed") from exc
            except Exception as exc:
                raise VolumeSurfaceUnavailableError("Volume surface worker failed") from exc
            if getattr(completed, "returncode", None) != 0:
                reason = _worker_failure_reason(getattr(completed, "stdout", ""))
                raise VolumeSurfaceUnavailableError(
                    f"Volume surface worker failed: {reason}"
                )
            stdout = getattr(completed, "stdout", "")
            if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_VOLUME_SURFACE_WORKER_REPORT_BYTES:
                raise VolumeSurfaceValidationError("Volume surface worker report is invalid")
            try:
                lines = [line for line in stdout.splitlines() if line.strip()]
                report = json.loads(lines[-1])
            except (IndexError, json.JSONDecodeError, UnicodeError) as exc:
                raise VolumeSurfaceValidationError("Volume surface worker report is invalid") from exc
            if not output_path.is_file() or output_path.is_symlink():
                raise VolumeSurfaceValidationError("Volume surface worker output is missing")
            payload = output_path.read_bytes()

        if _sha256_file(source.volume_path) != source_sha:
            raise VolumeSurfaceValidationError("Canonical patient volume changed during surface extraction")
        vertex_count, triangle_count, bounds = _decode_payload(payload)
        payload_sha = sha256(payload).hexdigest()
        expected_report = {
            "schema_version": VOLUME_SURFACE_SCHEMA_VERSION,
            "operation": "extract_volume_isosurface",
            "extraction": VOLUME_SURFACE_EXTRACTION,
            "isovalue": level,
            "intensity_units": source.intensity_units,
            "vertex_count": vertex_count,
            "triangle_count": triangle_count,
            "payload_bytes": len(payload),
            "payload_sha256": payload_sha,
            "coordinate_system": "patient_lps",
            "runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
            "python_version": runtime.python_version,
            "numpy_version": runtime.numpy_version,
            "scikit_image_version": runtime.scikit_image_version,
            "source_volume": "immutable",
            "clinical_validation": "not_claimed",
        }
        if not isinstance(report, dict):
            raise VolumeSurfaceValidationError("Volume surface worker report is invalid")
        for key, expected in expected_report.items():
            if report.get(key) != expected:
                raise VolumeSurfaceValidationError("Volume surface worker report is invalid")
        try:
            report_bounds = tuple(float(item) for item in report.get("bounds_lps_mm", []))
            raw_vertex_count = int(report.get("raw_vertex_count"))
            raw_triangle_count = int(report.get("raw_triangle_count"))
            degenerate_triangle_count = int(report.get("degenerate_triangle_count"))
            degenerate_triangle_fraction = float(report.get("degenerate_triangle_fraction"))
            unreferenced_vertex_count = int(report.get("unreferenced_vertex_count"))
            cleanup_epsilon = float(report.get("degenerate_double_area_epsilon_mm2"))
            cleanup_limit = float(report.get("max_degenerate_triangle_fraction"))
        except (TypeError, ValueError) as exc:
            raise VolumeSurfaceValidationError("Volume surface worker report is invalid") from exc
        if len(report_bounds) != 6 or any(abs(a - b) > 1e-5 for a, b in zip(report_bounds, bounds)):
            raise VolumeSurfaceValidationError("Volume surface worker report is invalid")
        if (
            raw_vertex_count < vertex_count
            or raw_triangle_count <= 0
            or raw_triangle_count < triangle_count
            or degenerate_triangle_count < 0
            or degenerate_triangle_count != raw_triangle_count - triangle_count
            or unreferenced_vertex_count != raw_vertex_count - vertex_count
            or not isfinite(degenerate_triangle_fraction)
            or abs(degenerate_triangle_fraction - (degenerate_triangle_count / raw_triangle_count)) > 1e-15
            or degenerate_triangle_fraction > MAX_VOLUME_SURFACE_DEGENERATE_TRIANGLE_FRACTION
            or cleanup_epsilon != 1e-12
            or cleanup_limit != MAX_VOLUME_SURFACE_DEGENERATE_TRIANGLE_FRACTION
        ):
            raise VolumeSurfaceValidationError("Volume surface worker cleanup report is invalid")

        provenance = {
            "schema_version": VOLUME_SURFACE_SCHEMA_VERSION,
            "source_type": "canonical_volume",
            "source_study_id": source.study_dir.name,
            "source_series_uid": source.source_series_uid,
            "source_modality": source.modality,
            "source_intensity_units": source.intensity_units,
            "source_value_range": [float(item) for item in source.value_range],
            "source_volume_descriptor_sha256": source.source_descriptor_sha256,
            "source_volume_artifact_sha256": source_sha,
            "source_volume_created_at_utc": source.volume_created_at_utc,
            "isovalue": level,
            "quality": VOLUME_SURFACE_QUALITY,
            "extraction": VOLUME_SURFACE_EXTRACTION,
            "coordinate_system": "patient_lps",
            "runtime_fingerprint_sha256": runtime.runtime_fingerprint_sha256,
            "cleanup": {
                "raw_vertex_count": raw_vertex_count,
                "raw_triangle_count": raw_triangle_count,
                "degenerate_triangle_count": degenerate_triangle_count,
                "degenerate_triangle_fraction": degenerate_triangle_fraction,
                "unreferenced_vertex_count": unreferenced_vertex_count,
                "degenerate_double_area_epsilon_mm2": cleanup_epsilon,
                "max_degenerate_triangle_fraction": cleanup_limit,
            },
            "payload_sha256": payload_sha,
            "source_volume": "immutable",
            "segmentation_required": False,
            "clinical_validation": "not_claimed",
        }
        provenance_sha = _canonical_sha256(provenance)
        surface_id = "vsurf-" + sha256(
            f"{provenance_sha}:{payload_sha}".encode("ascii")
        ).hexdigest()[:32]
        surface = VolumeDerivedSurface(
            study_id=source.study_dir.name,
            source_series_uid=source.source_series_uid,
            source_type="canonical_volume",
            source_modality=source.modality,
            intensity_units=source.intensity_units,
            isovalue=level,
            quality=VOLUME_SURFACE_QUALITY,
            extraction=VOLUME_SURFACE_EXTRACTION,
            coordinate_system="patient_lps",
            vertex_count=vertex_count,
            triangle_count=triangle_count,
            bounds_lps_mm=bounds,
            payload_sha256=payload_sha,
            payload=payload,
            surface_id=surface_id,
            provenance_sha256=provenance_sha,
            runtime_fingerprint_sha256=runtime.runtime_fingerprint_sha256,
            raw_vertex_count=raw_vertex_count,
            raw_triangle_count=raw_triangle_count,
            degenerate_triangle_count=degenerate_triangle_count,
            degenerate_triangle_fraction=degenerate_triangle_fraction,
            unreferenced_vertex_count=unreferenced_vertex_count,
        )
        self._cache[cache_key] = surface
        return surface
