from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
from typing import Callable, Protocol


SEGMENTATION_JOB_SCHEMA_VERSION = 1
SEGMENTATION_JOB_ID_PATTERN = re.compile(r"^seg-[0-9a-f]{32}$")
SEGMENTATION_STUDY_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
SEGMENTATION_COMPONENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SEGMENTATION_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
SEGMENTATION_PARAMETER_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
SEGMENTATION_DEVICE_PATTERN = re.compile(r"^cuda:(0|[1-9][0-9]{0,2})$")
SUPPORTED_SOURCE_MODALITIES = frozenset({"CT", "MR"})
SUPPORTED_DEVICE_KINDS = frozenset({"cpu", "cuda"})
JOB_STATES = frozenset(
    {"queued", "starting", "running", "cancelling", "succeeded", "failed", "cancelled"}
)
TERMINAL_JOB_STATES = frozenset({"succeeded", "failed", "cancelled"})
NON_TERMINAL_JOB_STATES = JOB_STATES - TERMINAL_JOB_STATES
PROGRESS_STAGES = (
    "queued",
    "preparing",
    "loading_model",
    "inference",
    "postprocessing",
    "finalizing",
    "complete",
)
MAX_JSON_BYTES = 64 * 1024
MAX_PUBLIC_TEXT = 256
GPU_DISCOVERY_TIMEOUT_SECONDS = 3.0


class SegmentationError(ValueError):
    """Base class for safe Phase 5A segmentation-orchestration failures."""


class SegmentationValidationError(SegmentationError):
    pass


class SegmentationNotFoundError(SegmentationError):
    pass


class SegmentationConflictError(SegmentationError):
    pass


class SegmentationUnavailableError(SegmentationError):
    pass


class SegmentationProviderError(SegmentationError):
    """A provider failure whose message is safe to retain in a public job manifest."""


class SegmentationCancellationRequested(SegmentationError):
    pass


def _canonical_json(payload: object) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SegmentationValidationError("Value is not valid bounded JSON") from exc


def _canonical_sha256(payload: object) -> str:
    return sha256(_canonical_json(payload)).hexdigest()


def _required_text(value: object, field: str, *, maximum: int = MAX_PUBLIC_TEXT) -> str:
    if not isinstance(value, str):
        raise SegmentationValidationError(f"{field} must be text")
    result = value.strip()
    if not result or len(result) > maximum or any(ord(character) < 32 for character in result):
        raise SegmentationValidationError(f"{field} is invalid")
    return result


def _component_id(value: object, field: str) -> str:
    result = _required_text(value, field, maximum=64).lower()
    if not SEGMENTATION_COMPONENT_ID_PATTERN.fullmatch(result):
        raise SegmentationValidationError(f"{field} is invalid")
    return result


def _version(value: object, field: str) -> str:
    result = _required_text(value, field, maximum=64)
    if not SEGMENTATION_VERSION_PATTERN.fullmatch(result):
        raise SegmentationValidationError(f"{field} is invalid")
    return result


def _safe_json_object(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SegmentationValidationError(f"{field} must be a JSON object")

    def validate(item: object, *, depth: int) -> None:
        if depth > 8:
            raise SegmentationValidationError(f"{field} is too deeply nested")
        if item is None or isinstance(item, bool) or isinstance(item, int):
            return
        if isinstance(item, float):
            if not isfinite(item):
                raise SegmentationValidationError(f"{field} contains a non-finite number")
            return
        if isinstance(item, str):
            if len(item) > 4096 or any(
                ord(character) < 32 and character not in "\t" for character in item
            ):
                raise SegmentationValidationError(f"{field} contains invalid text")
            if Path(item).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", item):
                raise SegmentationValidationError(f"{field} must not contain filesystem paths")
            return
        if isinstance(item, list):
            if len(item) > 1024:
                raise SegmentationValidationError(f"{field} contains too many values")
            for child in item:
                validate(child, depth=depth + 1)
            return
        if isinstance(item, dict):
            if len(item) > 256:
                raise SegmentationValidationError(f"{field} contains too many fields")
            for key, child in item.items():
                if not isinstance(key, str) or not SEGMENTATION_PARAMETER_KEY_PATTERN.fullmatch(
                    key
                ):
                    raise SegmentationValidationError(f"{field} contains an invalid field name")
                validate(child, depth=depth + 1)
            return
        raise SegmentationValidationError(f"{field} contains an unsupported value")

    validate(value, depth=0)
    encoded = _canonical_json(value)
    if len(encoded) > MAX_JSON_BYTES:
        raise SegmentationValidationError(f"{field} exceeds the configured size limit")
    return json.loads(encoded.decode("utf-8"))


def _sha256_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        raise SegmentationValidationError(
            "Canonical patient volume artifact is unreadable"
        ) from exc
    return digest.hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


Clock = Callable[[], datetime]
DeviceDiscovery = Callable[[], tuple["SegmentationDevice", ...]]


@dataclass(frozen=True, slots=True)
class SegmentationExecutionRequirements:
    supported_devices: tuple[str, ...]
    minimum_cuda_memory_mib: int = 0

    def __post_init__(self) -> None:
        normalized = tuple(str(item).strip().lower() for item in self.supported_devices)
        if not normalized or len(normalized) != len(set(normalized)):
            raise SegmentationValidationError("supported devices must be unique and non-empty")
        if any(item not in SUPPORTED_DEVICE_KINDS for item in normalized):
            raise SegmentationValidationError("supported devices contain an invalid device kind")
        if (
            not isinstance(self.minimum_cuda_memory_mib, int)
            or isinstance(self.minimum_cuda_memory_mib, bool)
            or self.minimum_cuda_memory_mib < 0
        ):
            raise SegmentationValidationError("minimum CUDA memory must be non-negative")
        order = {"cuda": 0, "cpu": 1}
        object.__setattr__(self, "supported_devices", tuple(sorted(normalized, key=order.get)))

    def public_dict(self) -> dict[str, object]:
        return {
            "supported_devices": list(self.supported_devices),
            "minimum_cuda_memory_mib": self.minimum_cuda_memory_mib,
        }


@dataclass(frozen=True, slots=True)
class SegmentationModelDescriptor:
    provider_id: str
    provider_version: str
    model_id: str
    model_version: str
    display_name: str
    task: str
    capabilities: tuple[str, ...]
    supported_modalities: tuple[str, ...]
    available: bool
    availability_reason: str | None
    execution: SegmentationExecutionRequirements

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _component_id(self.provider_id, "provider_id"))
        object.__setattr__(
            self,
            "provider_version",
            _version(self.provider_version, "provider_version"),
        )
        object.__setattr__(self, "model_id", _component_id(self.model_id, "model_id"))
        object.__setattr__(self, "model_version", _version(self.model_version, "model_version"))
        object.__setattr__(self, "display_name", _required_text(self.display_name, "display_name"))
        object.__setattr__(self, "task", _component_id(self.task, "task"))

        capabilities = tuple(_component_id(item, "capability") for item in self.capabilities)
        if not capabilities or len(capabilities) != len(set(capabilities)):
            raise SegmentationValidationError("capabilities must be unique and non-empty")
        object.__setattr__(self, "capabilities", tuple(sorted(capabilities)))

        modalities = tuple(str(item).strip().upper() for item in self.supported_modalities)
        if (
            not modalities
            or len(modalities) != len(set(modalities))
            or any(item not in SUPPORTED_SOURCE_MODALITIES for item in modalities)
        ):
            raise SegmentationValidationError(
                "supported modalities must be unique qualified CT/MR values"
            )
        object.__setattr__(self, "supported_modalities", tuple(sorted(modalities)))

        if not isinstance(self.available, bool):
            raise SegmentationValidationError("model availability must be boolean")
        if self.available and self.availability_reason is not None:
            raise SegmentationValidationError(
                "available model must not have an availability reason"
            )
        if not self.available:
            object.__setattr__(
                self,
                "availability_reason",
                _required_text(self.availability_reason, "availability_reason"),
            )

    @property
    def identity(self) -> tuple[str, str]:
        return (self.provider_id, self.model_id)

    def public_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "display_name": self.display_name,
            "task": self.task,
            "capabilities": list(self.capabilities),
            "supported_modalities": list(self.supported_modalities),
            "available": self.available,
            "availability_reason": self.availability_reason,
            "execution": self.execution.public_dict(),
        }

    @property
    def descriptor_sha256(self) -> str:
        return _canonical_sha256(self.public_dict())


@dataclass(frozen=True, slots=True)
class SegmentationDevice:
    kind: str
    selector: str
    name: str
    index: int | None
    total_memory_mib: int | None
    free_memory_mib: int | None

    def __post_init__(self) -> None:
        kind = str(self.kind).strip().lower()
        selector = str(self.selector).strip().lower()
        if kind not in SUPPORTED_DEVICE_KINDS:
            raise SegmentationValidationError("device kind is invalid")
        if kind == "cpu":
            if (
                selector != "cpu"
                or self.index is not None
                or self.total_memory_mib is not None
                or self.free_memory_mib is not None
            ):
                raise SegmentationValidationError("CPU device descriptor is invalid")
        else:
            if not SEGMENTATION_DEVICE_PATTERN.fullmatch(selector):
                raise SegmentationValidationError("CUDA device descriptor is invalid")
            expected_index = int(selector.split(":", 1)[1])
            if isinstance(self.index, bool) or self.index != expected_index:
                raise SegmentationValidationError("CUDA device index is inconsistent")
            if (
                not isinstance(self.total_memory_mib, int)
                or isinstance(self.total_memory_mib, bool)
                or self.total_memory_mib <= 0
            ):
                raise SegmentationValidationError("device total memory is invalid")
            if (
                not isinstance(self.free_memory_mib, int)
                or isinstance(self.free_memory_mib, bool)
                or self.free_memory_mib < 0
                or self.free_memory_mib > self.total_memory_mib
            ):
                raise SegmentationValidationError("device free memory is invalid")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "selector", selector)
        object.__setattr__(self, "name", _required_text(self.name, "device name"))

    @classmethod
    def cpu(cls) -> "SegmentationDevice":
        return cls(
            kind="cpu",
            selector="cpu",
            name="CPU",
            index=None,
            total_memory_mib=None,
            free_memory_mib=None,
        )

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


def discover_cuda_devices() -> tuple[SegmentationDevice, ...]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,memory.free",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=GPU_DISCOVERY_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return ()

    discovered: dict[int, SegmentationDevice] = {}
    for raw_line in result.stdout.splitlines():
        parts = [part.strip() for part in raw_line.split(",")]
        if len(parts) != 4:
            continue
        try:
            index = int(parts[0])
            total_memory = int(parts[2])
            free_memory = int(parts[3])
            device = SegmentationDevice(
                kind="cuda",
                selector=f"cuda:{index}",
                name=parts[1],
                index=index,
                total_memory_mib=total_memory,
                free_memory_mib=free_memory,
            )
        except (ValueError, SegmentationValidationError):
            continue
        discovered.setdefault(index, device)
    return tuple(discovered[index] for index in sorted(discovered))


class SegmentationDeviceSelector:
    def __init__(self, *, discovery: DeviceDiscovery = discover_cuda_devices) -> None:
        self._discovery = discovery

    def discover(self) -> tuple[SegmentationDevice, ...]:
        try:
            raw = tuple(self._discovery())
        except Exception:  # noqa: BLE001 - discovery failures are reported as no CUDA devices.
            raw = ()
        unique: dict[int, SegmentationDevice] = {}
        for device in raw:
            if (
                not isinstance(device, SegmentationDevice)
                or device.kind != "cuda"
                or device.index is None
            ):
                continue
            unique.setdefault(device.index, device)
        return tuple(unique[index] for index in sorted(unique))

    def list_public(self) -> list[dict[str, object]]:
        return [SegmentationDevice.cpu().public_dict()] + [
            item.public_dict() for item in self.discover()
        ]

    def select(
        self,
        model: SegmentationModelDescriptor,
        request: str,
    ) -> SegmentationDevice:
        requested = _required_text(request, "device", maximum=16).lower()
        if (
            requested != "auto"
            and requested != "cpu"
            and not SEGMENTATION_DEVICE_PATTERN.fullmatch(requested)
        ):
            raise SegmentationValidationError("device must be auto, cpu, or cuda:<index>")

        supported = set(model.execution.supported_devices)
        if requested == "cpu":
            if "cpu" not in supported:
                raise SegmentationUnavailableError(
                    "The selected model does not permit CPU execution"
                )
            return SegmentationDevice.cpu()

        devices = self.discover()
        minimum = model.execution.minimum_cuda_memory_mib
        if requested.startswith("cuda:"):
            if "cuda" not in supported:
                raise SegmentationUnavailableError(
                    "The selected model does not permit CUDA execution"
                )
            match = next((item for item in devices if item.selector == requested), None)
            if match is None:
                raise SegmentationUnavailableError(
                    f"Requested CUDA device {requested} is unavailable"
                )
            available_memory = match.free_memory_mib if match.free_memory_mib is not None else 0
            if available_memory < minimum:
                raise SegmentationUnavailableError(
                    f"Requested CUDA device {requested} does not meet model memory requirements"
                )
            return match

        compatible = []
        if "cuda" in supported:
            compatible = [
                item
                for item in devices
                if (item.free_memory_mib if item.free_memory_mib is not None else 0) >= minimum
            ]
        if compatible:
            return sorted(
                compatible,
                key=lambda item: (
                    -(item.free_memory_mib or 0),
                    -(item.total_memory_mib or 0),
                    item.index if item.index is not None else 1000,
                ),
            )[0]
        if "cpu" in supported:
            return SegmentationDevice.cpu()
        raise SegmentationUnavailableError("No compatible execution device is available")


@dataclass(frozen=True, slots=True)
class CanonicalSegmentationSource:
    study_id: str
    study_instance_uid: str
    source_series_uid: str
    modality: str
    volume_created_at_utc: str
    descriptor_sha256: str
    artifact_sha256: str
    manifest_path: Path
    study_dir: Path
    volume_path: Path


class CanonicalSegmentationSourceRepository:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.studies_dir = self.data_dir / "studies"

    def latest(self) -> CanonicalSegmentationSource:
        if self.studies_dir.is_symlink() or not self.studies_dir.is_dir():
            raise SegmentationValidationError("No stored DICOM study is available")
        manifests = [
            item
            for item in self.studies_dir.glob("*/manifest.json")
            if item.is_file() and not item.is_symlink()
        ]
        if not manifests:
            raise SegmentationValidationError("No stored DICOM study is available")
        return self._load_manifest(max(manifests, key=lambda item: item.stat().st_mtime_ns))

    def load(self, study_id: str) -> CanonicalSegmentationSource:
        if not SEGMENTATION_STUDY_ID_PATTERN.fullmatch(str(study_id)):
            raise SegmentationValidationError("Stored source study identity is invalid")
        if self.studies_dir.is_symlink() or not self.studies_dir.is_dir():
            raise SegmentationConflictError("The segmentation source study is no longer available")
        study_dir = self.studies_dir / study_id
        manifest_path = study_dir / "manifest.json"
        if study_dir.is_symlink():
            raise SegmentationConflictError("The segmentation source study is no longer available")
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise SegmentationConflictError("The segmentation source study is no longer available")
        return self._load_manifest(manifest_path)

    def _load_manifest(self, manifest_path: Path) -> CanonicalSegmentationSource:
        study_dir = manifest_path.parent
        study_id = study_dir.name
        if not SEGMENTATION_STUDY_ID_PATTERN.fullmatch(study_id):
            raise SegmentationValidationError("Stored DICOM study identity is invalid")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SegmentationValidationError("Stored DICOM study manifest is unreadable") from exc
        if not isinstance(payload, dict) or payload.get("study_id") != study_id:
            raise SegmentationValidationError("Stored DICOM study manifest is invalid")

        descriptor = payload.get("volume")
        if not isinstance(descriptor, dict) or descriptor.get("ready") is not True:
            raise SegmentationValidationError(
                "Canonical patient volume must be ready before segmentation"
            )
        if (
            descriptor.get("artifact_path") != "derived/volume.npy"
            or descriptor.get("metadata_path") != "derived/volume.json"
        ):
            raise SegmentationValidationError(
                "Canonical patient volume has an invalid artifact contract"
            )

        volume_path = study_dir / "derived" / "volume.npy"
        metadata_path = study_dir / "derived" / "volume.json"
        if (
            volume_path.is_symlink()
            or metadata_path.is_symlink()
            or not volume_path.is_file()
            or not metadata_path.is_file()
        ):
            raise SegmentationValidationError("Canonical patient volume artifacts are missing")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SegmentationValidationError(
                "Canonical patient volume metadata is unreadable"
            ) from exc
        if metadata != descriptor:
            raise SegmentationValidationError(
                "Canonical patient volume metadata does not match the study manifest"
            )

        study_instance_uid = _required_text(
            payload.get("study_instance_uid"), "source study identity", maximum=128
        )
        source_series_uid = _required_text(
            descriptor.get("source_series_uid"), "source series identity", maximum=128
        )
        modality = _required_text(descriptor.get("modality"), "source modality", maximum=16).upper()
        if modality not in SUPPORTED_SOURCE_MODALITIES:
            raise SegmentationValidationError("Canonical patient volume modality is unsupported")
        created_at = _required_text(
            descriptor.get("created_at_utc"), "canonical volume creation time", maximum=64
        )

        return CanonicalSegmentationSource(
            study_id=study_id,
            study_instance_uid=study_instance_uid,
            source_series_uid=source_series_uid,
            modality=modality,
            volume_created_at_utc=created_at,
            descriptor_sha256=_canonical_sha256(descriptor),
            artifact_sha256=_sha256_file(volume_path),
            manifest_path=manifest_path,
            study_dir=study_dir,
            volume_path=volume_path,
        )


@dataclass(frozen=True, slots=True)
class SegmentationProviderResult:
    outcome: dict[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome", _safe_json_object(self.outcome, "provider outcome"))


class SegmentationExecutionContext:
    def __init__(
        self,
        *,
        job_id: str,
        source: CanonicalSegmentationSource,
        model: SegmentationModelDescriptor,
        device: SegmentationDevice,
        parameters: dict[str, object],
        progress_reporter: Callable[..., dict[str, object]],
        cancellation_check: Callable[[], bool],
    ) -> None:
        self.job_id = job_id
        self.source = source
        self.model = model
        self.device = device
        self.parameters = json.loads(_canonical_json(parameters).decode("utf-8"))
        self._progress_reporter = progress_reporter
        self._cancellation_check = cancellation_check

    def report_progress(self, *, stage: str, percent: float, message: str) -> None:
        self._progress_reporter(stage=stage, percent=percent, message=message)

    @property
    def cancellation_requested(self) -> bool:
        return bool(self._cancellation_check())

    def raise_if_cancelled(self) -> None:
        if self.cancellation_requested:
            raise SegmentationCancellationRequested("Segmentation cancellation requested")


class SegmentationProvider(Protocol):
    descriptor: SegmentationModelDescriptor

    def validate_parameters(self, parameters: dict[str, object]) -> dict[str, object]: ...

    def run(self, context: SegmentationExecutionContext) -> SegmentationProviderResult: ...


class SegmentationModelRegistry:
    def __init__(self, descriptors: tuple[SegmentationModelDescriptor, ...] = ()) -> None:
        self._models: dict[tuple[str, str], SegmentationModelDescriptor] = {}
        self._providers: dict[tuple[str, str], SegmentationProvider] = {}
        for descriptor in descriptors:
            self.register_descriptor(descriptor)

    def register_descriptor(self, descriptor: SegmentationModelDescriptor) -> None:
        if not isinstance(descriptor, SegmentationModelDescriptor):
            raise SegmentationValidationError("model registry accepts validated descriptors only")
        if descriptor.identity in self._models:
            raise SegmentationValidationError(
                "model registry contains a duplicate provider/model identity"
            )
        self._models[descriptor.identity] = descriptor

    def register_provider(self, provider: SegmentationProvider) -> None:
        descriptor = getattr(provider, "descriptor", None)
        if not isinstance(descriptor, SegmentationModelDescriptor):
            raise SegmentationValidationError("runtime provider descriptor is invalid")
        if not descriptor.available:
            raise SegmentationValidationError("runtime provider descriptor must be available")
        self.register_descriptor(descriptor)
        self._providers[descriptor.identity] = provider

    def descriptor(self, provider_id: str, model_id: str) -> SegmentationModelDescriptor:
        identity = (
            _component_id(provider_id, "provider_id"),
            _component_id(model_id, "model_id"),
        )
        descriptor = self._models.get(identity)
        if descriptor is None:
            raise SegmentationNotFoundError("Segmentation model is not registered")
        return descriptor

    def provider(self, provider_id: str, model_id: str) -> SegmentationProvider:
        descriptor = self.descriptor(provider_id, model_id)
        if not descriptor.available:
            raise SegmentationUnavailableError(
                descriptor.availability_reason or "Segmentation model is unavailable"
            )
        provider = self._providers.get(descriptor.identity)
        if provider is None:
            raise SegmentationUnavailableError("Segmentation provider runtime is unavailable")
        return provider

    def list_public(self) -> list[dict[str, object]]:
        return [
            self._models[identity].public_dict()
            for identity in sorted(self._models)
        ]


def build_default_segmentation_registry() -> SegmentationModelRegistry:
    planned = SegmentationModelDescriptor(
        provider_id="totalsegmentator",
        provider_version="unqualified",
        model_id="total",
        model_version="unqualified",
        display_name="TotalSegmentator total task",
        task="multi_structure",
        capabilities=("anatomical_segmentation", "full_resolution"),
        supported_modalities=("CT",),
        available=False,
        availability_reason="Runtime unavailable until qualified Phase 5B integration",
        execution=SegmentationExecutionRequirements(
            supported_devices=("cuda",),
            minimum_cuda_memory_mib=0,
        ),
    )
    return SegmentationModelRegistry((planned,))


class SegmentationJobService:
    def __init__(
        self,
        *,
        data_dir: Path,
        registry: SegmentationModelRegistry | None = None,
        device_discovery: DeviceDiscovery = discover_cuda_devices,
        id_factory: Callable[[], str] | None = None,
        clock: Clock = _utc_now,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.segmentation_root = self.data_dir / "segmentation"
        self.jobs_root = self.segmentation_root / "jobs"
        self.registry = build_default_segmentation_registry() if registry is None else registry
        self.device_selector = SegmentationDeviceSelector(discovery=device_discovery)
        self.sources = CanonicalSegmentationSourceRepository(self.data_dir)
        self._id_factory = id_factory or (lambda: secrets.token_hex(16))
        self._clock = clock
        self._lock = threading.RLock()
        self._recover_interrupted_jobs()

    @staticmethod
    def canonical_json_sha256(payload: object) -> str:
        return _canonical_sha256(payload)

    def list_models(self) -> list[dict[str, object]]:
        return self.registry.list_public()

    def list_devices(self) -> list[dict[str, object]]:
        return self.device_selector.list_public()

    def _now(self) -> str:
        current = self._clock()
        if not isinstance(current, datetime):
            raise RuntimeError("segmentation clock must return a datetime")
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).isoformat()

    def _new_job_id(self) -> str:
        for _ in range(16):
            raw = str(self._id_factory()).strip().lower()
            candidate = raw if raw.startswith("seg-") else f"seg-{raw}"
            if not SEGMENTATION_JOB_ID_PATTERN.fullmatch(candidate):
                raise SegmentationValidationError(
                    "job identifier generator returned an invalid value"
                )
            if not (self.jobs_root / candidate).exists():
                return candidate
        raise SegmentationConflictError("Unable to allocate a unique segmentation job identifier")

    @staticmethod
    def _validate_job_id(job_id: str) -> str:
        value = str(job_id).strip().lower()
        if not SEGMENTATION_JOB_ID_PATTERN.fullmatch(value):
            raise SegmentationValidationError("Segmentation job identifier is invalid")
        return value

    def _job_dir(self, job_id: str) -> Path:
        return self.jobs_root / self._validate_job_id(job_id)

    def _ensure_jobs_root(self) -> None:
        if self.segmentation_root.is_symlink() or (
            self.segmentation_root.exists() and not self.segmentation_root.is_dir()
        ):
            raise SegmentationValidationError("Segmentation data directory is unsafe")
        self.segmentation_root.mkdir(parents=True, exist_ok=True)
        if self.jobs_root.is_symlink() or (
            self.jobs_root.exists() and not self.jobs_root.is_dir()
        ):
            raise SegmentationValidationError("Segmentation job repository is unsafe")
        self.jobs_root.mkdir(exist_ok=True)

    def _write_manifest(self, manifest: dict[str, object]) -> None:
        job_id = self._validate_job_id(str(manifest.get("job_id") or ""))
        job_dir = self._job_dir(job_id)
        if job_dir.is_symlink() or not job_dir.is_dir():
            raise SegmentationValidationError("Segmentation job directory is unavailable")
        manifest_path = job_dir / "manifest.json"
        temporary = job_dir / f"manifest.{secrets.token_hex(8)}.tmp"
        encoded = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                os.chmod(temporary, 0o600)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, manifest_path)
            try:
                directory_fd = os.open(job_dir, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except (OSError, TypeError, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            raise SegmentationValidationError(
                "Segmentation job manifest could not be stored"
            ) from exc

    def _load_manifest(self, job_id: str) -> dict[str, object]:
        validated = self._validate_job_id(job_id)
        job_dir = self.jobs_root / validated
        manifest_path = job_dir / "manifest.json"
        if job_dir.is_symlink() or manifest_path.is_symlink() or not manifest_path.is_file():
            raise SegmentationNotFoundError("Segmentation job was not found")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SegmentationValidationError("Segmentation job manifest is unreadable") from exc
        if not isinstance(manifest, dict):
            raise SegmentationValidationError("Segmentation job manifest is invalid")
        if manifest.get("schema_version") != SEGMENTATION_JOB_SCHEMA_VERSION:
            raise SegmentationValidationError("Segmentation job manifest schema is unsupported")
        if manifest.get("job_id") != validated or manifest.get("state") not in JOB_STATES:
            raise SegmentationValidationError("Segmentation job manifest is invalid")
        provenance = manifest.get("provenance")
        digest = str(manifest.get("provenance_sha256") or "")
        if not isinstance(provenance, dict) or digest != _canonical_sha256(provenance):
            raise SegmentationValidationError("Segmentation job immutable provenance check failed")
        progress = manifest.get("progress")
        if not isinstance(progress, dict) or progress.get("stage") not in PROGRESS_STAGES:
            raise SegmentationValidationError("Segmentation job progress is invalid")
        try:
            percent = float(progress.get("percent"))
        except (TypeError, ValueError) as exc:
            raise SegmentationValidationError("Segmentation job progress is invalid") from exc
        if not isfinite(percent) or not 0.0 <= percent <= 100.0:
            raise SegmentationValidationError("Segmentation job progress is invalid")
        terminal_provenance = manifest.get("terminal_provenance")
        terminal_digest = manifest.get("terminal_provenance_sha256")
        if manifest["state"] in TERMINAL_JOB_STATES:
            expected_terminal = {
                "created_at_utc": manifest.get("created_at_utc"),
                "started_at_utc": manifest.get("started_at_utc"),
                "completed_at_utc": manifest.get("completed_at_utc"),
                "terminal_state": manifest.get("state"),
                "outcome": manifest.get("outcome"),
            }
            if (
                terminal_provenance != expected_terminal
                or terminal_digest != _canonical_sha256(expected_terminal)
            ):
                raise SegmentationValidationError(
                    "Segmentation job immutable terminal provenance check failed"
                )
        elif terminal_provenance is not None or terminal_digest is not None:
            raise SegmentationValidationError(
                "Non-terminal segmentation job contains invalid terminal provenance"
            )
        return manifest

    @staticmethod
    def _public_manifest(manifest: dict[str, object]) -> dict[str, object]:
        public = json.loads(_canonical_json(manifest).decode("utf-8"))
        public.pop("schema_version", None)
        return public

    @staticmethod
    def _seal_terminal_manifest(manifest: dict[str, object]) -> None:
        if manifest.get("state") not in TERMINAL_JOB_STATES:
            raise SegmentationValidationError("Only terminal segmentation jobs can be sealed")
        terminal_provenance = {
            "created_at_utc": manifest.get("created_at_utc"),
            "started_at_utc": manifest.get("started_at_utc"),
            "completed_at_utc": manifest.get("completed_at_utc"),
            "terminal_state": manifest.get("state"),
            "outcome": manifest.get("outcome"),
        }
        manifest["terminal_provenance"] = terminal_provenance
        manifest["terminal_provenance_sha256"] = _canonical_sha256(terminal_provenance)

    def create_job(
        self,
        *,
        provider_id: str,
        model_id: str,
        device_request: str,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        with self._lock:
            model = self.registry.descriptor(provider_id, model_id)
            provider = self.registry.provider(provider_id, model_id)
            if provider.descriptor.descriptor_sha256 != model.descriptor_sha256:
                raise SegmentationConflictError("The registered model changed before job creation")
            source = self.sources.latest()
            if source.modality not in model.supported_modalities:
                raise SegmentationConflictError(
                    f"Model {model.provider_id}/{model.model_id} does not support "
                    f"{source.modality} input"
                )
            requested_parameters = _safe_json_object(parameters, "segmentation parameters")
            try:
                validated_parameters = provider.validate_parameters(requested_parameters)
            except SegmentationError:
                raise
            except Exception as exc:
                raise SegmentationValidationError(
                    "Segmentation provider rejected the requested parameters"
                ) from exc
            normalized_parameters = _safe_json_object(
                validated_parameters, "segmentation parameters"
            )
            selected_device = self.device_selector.select(model, device_request)
            created_at = self._now()
            job_id = self._new_job_id()
            provenance: dict[str, object] = {
                "source_study_id": source.study_id,
                "source_study_instance_uid": source.study_instance_uid,
                "source_series_uid": source.source_series_uid,
                "source_modality": source.modality,
                "canonical_volume_created_at_utc": source.volume_created_at_utc,
                "canonical_volume_descriptor_sha256": source.descriptor_sha256,
                "canonical_volume_artifact_sha256": source.artifact_sha256,
                "provider_id": model.provider_id,
                "provider_version": model.provider_version,
                "model_id": model.model_id,
                "model_version": model.model_version,
                "model_descriptor_sha256": model.descriptor_sha256,
                "parameters": normalized_parameters,
                "selected_device": selected_device.public_dict(),
                "created_at_utc": created_at,
            }
            manifest: dict[str, object] = {
                "schema_version": SEGMENTATION_JOB_SCHEMA_VERSION,
                "job_id": job_id,
                "state": "queued",
                "created_at_utc": created_at,
                "started_at_utc": None,
                "completed_at_utc": None,
                "cancellation_requested": False,
                "progress": {
                    "stage": "queued",
                    "percent": 0.0,
                    "message": "Queued for provider execution",
                    "updated_at_utc": created_at,
                },
                "provenance": provenance,
                "provenance_sha256": _canonical_sha256(provenance),
                "outcome": None,
                "terminal_provenance": None,
                "terminal_provenance_sha256": None,
            }
            self._ensure_jobs_root()
            job_dir = self.jobs_root / job_id
            try:
                job_dir.mkdir(mode=0o700)
                self._write_manifest(manifest)
            except Exception:
                if job_dir.is_dir() and not any(job_dir.iterdir()):
                    job_dir.rmdir()
                raise
            return self._public_manifest(manifest)

    def get_job(self, job_id: str) -> dict[str, object]:
        with self._lock:
            return self._public_manifest(self._load_manifest(job_id))

    def list_jobs(self) -> list[dict[str, object]]:
        with self._lock:
            if self.segmentation_root.is_symlink() or self.jobs_root.is_symlink():
                raise SegmentationValidationError("Segmentation job repository is unsafe")
            if not self.jobs_root.is_dir():
                return []
            jobs = []
            for path in self.jobs_root.iterdir():
                if not path.is_dir() or not SEGMENTATION_JOB_ID_PATTERN.fullmatch(path.name):
                    continue
                try:
                    jobs.append(self._load_manifest(path.name))
                except SegmentationError:
                    continue
            jobs.sort(
                key=lambda item: (str(item.get("created_at_utc") or ""), str(item["job_id"])),
                reverse=True,
            )
            return [self._public_manifest(item) for item in jobs]

    def _assert_bindings(
        self, manifest: dict[str, object]
    ) -> tuple[CanonicalSegmentationSource, SegmentationModelDescriptor, SegmentationProvider]:
        provenance = manifest["provenance"]
        assert isinstance(provenance, dict)
        source = self.sources.load(str(provenance.get("source_study_id") or ""))
        if (
            source.descriptor_sha256 != provenance.get("canonical_volume_descriptor_sha256")
            or source.artifact_sha256 != provenance.get("canonical_volume_artifact_sha256")
            or source.source_series_uid != provenance.get("source_series_uid")
        ):
            raise SegmentationConflictError(
                "The canonical volume changed after the segmentation job was created"
            )
        model = self.registry.descriptor(
            str(provenance.get("provider_id") or ""),
            str(provenance.get("model_id") or ""),
        )
        if model.descriptor_sha256 != provenance.get("model_descriptor_sha256"):
            raise SegmentationConflictError(
                "The registered model changed after the segmentation job was created"
            )
        provider = self.registry.provider(model.provider_id, model.model_id)
        if provider.descriptor.descriptor_sha256 != model.descriptor_sha256:
            raise SegmentationConflictError(
                "The registered model changed after the segmentation job was created"
            )
        return source, model, provider

    def begin_job(self, job_id: str) -> dict[str, object]:
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest["state"] != "queued":
                raise SegmentationConflictError(
                    f"Segmentation job cannot start from {manifest['state']} state"
                )
            self._assert_bindings(manifest)
            now = self._now()
            manifest["state"] = "starting"
            manifest["started_at_utc"] = now
            manifest["progress"] = {
                "stage": "preparing",
                "percent": 0.0,
                "message": "Preparing provider execution",
                "updated_at_utc": now,
            }
            self._write_manifest(manifest)
            return self._public_manifest(manifest)

    def mark_running(self, job_id: str) -> dict[str, object]:
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest["state"] != "starting":
                raise SegmentationConflictError(
                    f"Segmentation job cannot enter running state from {manifest['state']} state"
                )
            manifest["state"] = "running"
            self._write_manifest(manifest)
            return self._public_manifest(manifest)

    def report_progress(
        self,
        job_id: str,
        *,
        stage: str,
        percent: float,
        message: str,
    ) -> dict[str, object]:
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest["state"] not in {"starting", "running", "cancelling"}:
                raise SegmentationConflictError(
                    f"Segmentation progress cannot change from {manifest['state']} state"
                )
            normalized_stage = _component_id(stage, "progress stage")
            if normalized_stage not in PROGRESS_STAGES:
                raise SegmentationValidationError("Segmentation progress stage is unsupported")
            if isinstance(percent, bool):
                raise SegmentationValidationError("Segmentation progress percent is invalid")
            try:
                normalized_percent = float(percent)
            except (TypeError, ValueError) as exc:
                raise SegmentationValidationError(
                    "Segmentation progress percent is invalid"
                ) from exc
            if not isfinite(normalized_percent) or not 0.0 <= normalized_percent <= 100.0:
                raise SegmentationValidationError("Segmentation progress percent is invalid")
            current = manifest["progress"]
            assert isinstance(current, dict)
            current_stage = str(current.get("stage"))
            current_percent = float(current.get("percent"))
            if (
                PROGRESS_STAGES.index(normalized_stage) < PROGRESS_STAGES.index(current_stage)
                or normalized_percent < current_percent
            ):
                raise SegmentationConflictError("Segmentation progress must be monotonic")
            manifest["progress"] = {
                "stage": normalized_stage,
                "percent": normalized_percent,
                "message": _required_text(message, "progress message"),
                "updated_at_utc": self._now(),
            }
            self._write_manifest(manifest)
            return self._public_manifest(manifest)

    def cancel_job(self, job_id: str) -> dict[str, object]:
        with self._lock:
            manifest = self._load_manifest(job_id)
            state = str(manifest["state"])
            if state in TERMINAL_JOB_STATES or state == "cancelling":
                return self._public_manifest(manifest)
            now = self._now()
            manifest["cancellation_requested"] = True
            if state == "queued":
                manifest["state"] = "cancelled"
                manifest["completed_at_utc"] = now
                manifest["outcome"] = {
                    "code": "cancelled",
                    "message": "Cancelled before provider execution",
                }
                self._seal_terminal_manifest(manifest)
            elif state in {"starting", "running"}:
                manifest["state"] = "cancelling"
            else:
                raise SegmentationConflictError(
                    f"Segmentation job cannot be cancelled from {state} state"
                )
            self._write_manifest(manifest)
            return self._public_manifest(manifest)

    def mark_cancelled(self, job_id: str) -> dict[str, object]:
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest["state"] == "cancelled":
                return self._public_manifest(manifest)
            if manifest["state"] != "cancelling":
                raise SegmentationConflictError(
                    f"Segmentation job cannot finish cancellation from {manifest['state']} state"
                )
            manifest["state"] = "cancelled"
            manifest["completed_at_utc"] = self._now()
            manifest["outcome"] = {
                "code": "cancelled",
                "message": "Provider execution cancelled cooperatively",
            }
            self._seal_terminal_manifest(manifest)
            self._write_manifest(manifest)
            return self._public_manifest(manifest)

    def complete_job(
        self,
        job_id: str,
        result: SegmentationProviderResult,
    ) -> dict[str, object]:
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest["state"] == "cancelling":
                return self.mark_cancelled(job_id)
            if manifest["state"] != "running":
                raise SegmentationConflictError(
                    f"Segmentation job cannot succeed from {manifest['state']} state"
                )
            if not isinstance(result, SegmentationProviderResult):
                raise SegmentationValidationError("Provider returned an invalid result contract")
            now = self._now()
            manifest["state"] = "succeeded"
            manifest["completed_at_utc"] = now
            manifest["progress"] = {
                "stage": "complete",
                "percent": 100.0,
                "message": "Provider execution completed",
                "updated_at_utc": now,
            }
            manifest["outcome"] = result.outcome
            self._seal_terminal_manifest(manifest)
            self._write_manifest(manifest)
            return self._public_manifest(manifest)

    def fail_job(
        self,
        job_id: str,
        *,
        code: str,
        message: str,
    ) -> dict[str, object]:
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest["state"] in TERMINAL_JOB_STATES:
                return self._public_manifest(manifest)
            manifest["state"] = "failed"
            manifest["completed_at_utc"] = self._now()
            manifest["outcome"] = {
                "code": _component_id(code, "failure code"),
                "message": _required_text(message, "failure message"),
            }
            self._seal_terminal_manifest(manifest)
            self._write_manifest(manifest)
            return self._public_manifest(manifest)

    def is_cancellation_requested(self, job_id: str) -> bool:
        with self._lock:
            return bool(self._load_manifest(job_id).get("cancellation_requested"))

    def run_job(self, job_id: str) -> dict[str, object]:
        self.begin_job(job_id)
        self.mark_running(job_id)
        with self._lock:
            manifest = self._load_manifest(job_id)
            source, model, provider = self._assert_bindings(manifest)
            provenance = manifest["provenance"]
            assert isinstance(provenance, dict)
            selected_raw = provenance.get("selected_device")
            if not isinstance(selected_raw, dict):
                raise SegmentationValidationError("Selected execution device provenance is invalid")
            device = SegmentationDevice(
                kind=str(selected_raw.get("kind") or ""),
                selector=str(selected_raw.get("selector") or ""),
                name=str(selected_raw.get("name") or ""),
                index=selected_raw.get("index"),
                total_memory_mib=selected_raw.get("total_memory_mib"),
                free_memory_mib=selected_raw.get("free_memory_mib"),
            )
            parameters = provenance.get("parameters")
            if not isinstance(parameters, dict):
                raise SegmentationValidationError("Segmentation parameter provenance is invalid")
        context = SegmentationExecutionContext(
            job_id=job_id,
            source=source,
            model=model,
            device=device,
            parameters=parameters,
            progress_reporter=lambda **values: self.report_progress(job_id, **values),
            cancellation_check=lambda: self.is_cancellation_requested(job_id),
        )
        try:
            result = provider.run(context)
            if context.cancellation_requested:
                return self.mark_cancelled(job_id)
            return self.complete_job(job_id, result)
        except SegmentationCancellationRequested:
            current = self.get_job(job_id)
            if current["state"] != "cancelling":
                self.cancel_job(job_id)
            return self.mark_cancelled(job_id)
        except SegmentationProviderError:
            return self.fail_job(
                job_id,
                code="provider_failure",
                message="Segmentation provider execution failed",
            )
        except Exception:  # noqa: BLE001 - unexpected provider details never enter public state.
            return self.fail_job(
                job_id,
                code="provider_failure",
                message="Segmentation provider execution failed",
            )

    def _recover_interrupted_jobs(self) -> None:
        if self.segmentation_root.is_symlink() or self.jobs_root.is_symlink():
            raise SegmentationValidationError("Segmentation job repository is unsafe")
        if not self.jobs_root.is_dir():
            return
        with self._lock:
            for job_dir in self.jobs_root.iterdir():
                if not job_dir.is_dir() or not SEGMENTATION_JOB_ID_PATTERN.fullmatch(job_dir.name):
                    continue
                try:
                    manifest = self._load_manifest(job_dir.name)
                except SegmentationError:
                    continue
                if manifest["state"] not in NON_TERMINAL_JOB_STATES:
                    continue
                manifest["state"] = "failed"
                manifest["completed_at_utc"] = self._now()
                manifest["outcome"] = {
                    "code": "interrupted",
                    "message": "Job interrupted by service restart",
                }
                self._seal_terminal_manifest(manifest)
                self._write_manifest(manifest)
