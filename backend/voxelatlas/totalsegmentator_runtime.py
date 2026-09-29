from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Callable


TOTAL_SEGMENTATOR_PROBE_SCHEMA_VERSION = 1
PINNED_TOTALSEGMENTATOR_VERSION = "2.18.0"
MINIMUM_TOTALSEGMENTATOR_PYTHON = (3, 10)
EXPECTED_TOTAL_TASK = "total"
EXPECTED_TOTAL_MODALITY = "CT"
EXPECTED_TOTAL_CLASS_COUNT = 117
EXPECTED_TOTAL_TASK_DEFINITION_SHA256 = (
    "2f9caff9c6fc38df9a134d8258835f30cd33651da5a9d8b5dab77fbc7dac2d67"
)
TOTAL_SEGMENTATOR_PROBE_TIMEOUT_SECONDS = 30.0
MAX_PROBE_OUTPUT_BYTES = 64 * 1024
CUDA_SELECTOR_PATTERN = re.compile(r"^cuda:(0|[1-9][0-9]{0,2})$")
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class TotalSegmentatorQualificationError(ValueError):
    """Raised when a Phase 5B1 runtime or invocation contract is invalid."""


@dataclass(frozen=True, slots=True)
class TotalSegmentatorCudaDevice:
    index: int
    name: str
    total_memory_mib: int

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise TotalSegmentatorQualificationError("CUDA device index is invalid")
        if self.index < 0 or self.index > 999:
            raise TotalSegmentatorQualificationError("CUDA device index is invalid")
        if not isinstance(self.name, str):
            raise TotalSegmentatorQualificationError("CUDA device name is invalid")
        name = self.name.strip()
        if (
            not name
            or len(name) > 128
            or "/" in name
            or "\\" in name
            or any(ord(character) < 32 for character in name)
        ):
            raise TotalSegmentatorQualificationError("CUDA device name is invalid")
        if (
            isinstance(self.total_memory_mib, bool)
            or not isinstance(self.total_memory_mib, int)
            or self.total_memory_mib <= 0
        ):
            raise TotalSegmentatorQualificationError("CUDA device memory is invalid")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True, slots=True)
class TotalSegmentatorRuntimeReport:
    qualified: bool
    status_code: str
    message: str
    python_version: str | None = None
    totalsegmentator_version: str | None = None
    torch_version: str | None = None
    nnunetv2_version: str | None = None
    task: str | None = None
    task_modality: str | None = None
    task_class_count: int | None = None
    task_definition_sha256: str | None = None
    task_requires_license: bool | None = None
    cuda_available: bool | None = None
    cuda_device_count: int | None = None
    cuda_devices: tuple[TotalSegmentatorCudaDevice, ...] = ()

    def public_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["cuda_devices"] = [asdict(device) for device in self.cuda_devices]
        return result


@dataclass(frozen=True, slots=True)
class TotalSegmentatorInvocation:
    command: tuple[str, ...]
    task: str
    modality: str
    resolution: str
    output_mode: str
    device_selector: str
    force_split: bool


ProbeRunner = Callable[..., object]


_PROBE_PROGRAM = r'''
import hashlib
import importlib
import importlib.metadata
import json
import platform

torch_module = importlib.import_module("torch")
api_module = importlib.import_module("totalsegmentator.python_api")
registry_module = importlib.import_module("totalsegmentator.registry")
task = "total"
classes = registry_module.get_task_classes(task)
normalized_classes = {str(key): value for key, value in sorted(classes.items())}
task_definition = json.dumps(
    normalized_classes,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True,
).encode("utf-8")
devices = []
if torch_module.cuda.is_available():
    for index in range(torch_module.cuda.device_count()):
        properties = torch_module.cuda.get_device_properties(index)
        devices.append({
            "index": index,
            "name": properties.name,
            "total_memory_mib": int(properties.total_memory // (1024 * 1024)),
        })
payload = {
    "schema_version": 1,
    "python_version": platform.python_version(),
    "totalsegmentator_version": importlib.metadata.version("TotalSegmentator"),
    "torch_version": importlib.metadata.version("torch"),
    "nnunetv2_version": importlib.metadata.version("nnunetv2"),
    "python_api_available": callable(getattr(api_module, "totalsegmentator", None)),
    "task": task,
    "task_modality": registry_module.task_modality(task),
    "task_class_count": len(classes),
    "task_definition_sha256": hashlib.sha256(task_definition).hexdigest(),
    "task_requires_license": registry_module.requires_license(task),
    "cuda_available": torch_module.cuda.is_available(),
    "cuda_device_count": torch_module.cuda.device_count(),
    "cuda_devices": devices,
}
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
'''.strip()


def _safe_version(value: object, field: str) -> str:
    if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
        raise TotalSegmentatorQualificationError(f"{field} is invalid")
    return value


def _python_version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise TotalSegmentatorQualificationError("Python version is invalid")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _strict_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise TotalSegmentatorQualificationError(f"{field} is invalid")
    return value


def _strict_int(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise TotalSegmentatorQualificationError(f"{field} is invalid")
    return value


def _failure(code: str, message: str) -> TotalSegmentatorRuntimeReport:
    return TotalSegmentatorRuntimeReport(
        qualified=False,
        status_code=code,
        message=message,
    )


def _parse_probe_payload(payload: object) -> TotalSegmentatorRuntimeReport:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise TotalSegmentatorQualificationError("probe schema is invalid")

    python_version = _safe_version(payload.get("python_version"), "Python version")
    python_version_info = _python_version_tuple(python_version)
    provider_version = _safe_version(
        payload.get("totalsegmentator_version"), "TotalSegmentator version"
    )
    torch_version = _safe_version(payload.get("torch_version"), "PyTorch version")
    nnunet_version = _safe_version(payload.get("nnunetv2_version"), "nnU-Net version")
    python_api_available = _strict_bool(
        payload.get("python_api_available"), "Python API availability"
    )

    task = payload.get("task")
    modality = payload.get("task_modality")
    if task not in {EXPECTED_TOTAL_TASK, "total_mr"}:
        raise TotalSegmentatorQualificationError("task identity is invalid")
    if modality not in {"CT", "MR"}:
        raise TotalSegmentatorQualificationError("task modality is invalid")
    class_count = _strict_int(payload.get("task_class_count"), "task class count", minimum=1)
    task_definition_sha256 = payload.get("task_definition_sha256")
    if not isinstance(task_definition_sha256, str) or not SHA256_PATTERN.fullmatch(
        task_definition_sha256
    ):
        raise TotalSegmentatorQualificationError("task definition fingerprint is invalid")
    requires_license = _strict_bool(
        payload.get("task_requires_license"), "task license requirement"
    )
    cuda_available = _strict_bool(payload.get("cuda_available"), "CUDA availability")
    cuda_device_count = _strict_int(payload.get("cuda_device_count"), "CUDA device count")
    raw_devices = payload.get("cuda_devices")
    if not isinstance(raw_devices, list) or len(raw_devices) != cuda_device_count:
        raise TotalSegmentatorQualificationError("CUDA device inventory is invalid")
    devices: list[TotalSegmentatorCudaDevice] = []
    seen_indices: set[int] = set()
    for raw in raw_devices:
        if not isinstance(raw, dict) or set(raw) != {"index", "name", "total_memory_mib"}:
            raise TotalSegmentatorQualificationError("CUDA device inventory is invalid")
        device = TotalSegmentatorCudaDevice(
            index=raw["index"],
            name=raw["name"],
            total_memory_mib=raw["total_memory_mib"],
        )
        if device.index in seen_indices:
            raise TotalSegmentatorQualificationError("CUDA device inventory is invalid")
        seen_indices.add(device.index)
        devices.append(device)
    if cuda_available != (cuda_device_count > 0):
        raise TotalSegmentatorQualificationError("CUDA availability is inconsistent")

    common = {
        "python_version": python_version,
        "totalsegmentator_version": provider_version,
        "torch_version": torch_version,
        "nnunetv2_version": nnunet_version,
        "task": task,
        "task_modality": modality,
        "task_class_count": class_count,
        "task_definition_sha256": task_definition_sha256,
        "task_requires_license": requires_license,
        "cuda_available": cuda_available,
        "cuda_device_count": cuda_device_count,
        "cuda_devices": tuple(sorted(devices, key=lambda item: item.index)),
    }
    checks = (
        (
            python_version_info[:2] >= MINIMUM_TOTALSEGMENTATOR_PYTHON,
            "python_version_unsupported",
            "TotalSegmentator Python version is unsupported",
        ),
        (
            provider_version == PINNED_TOTALSEGMENTATOR_VERSION,
            "version_mismatch",
            "TotalSegmentator version does not match the pinned Phase 5B baseline",
        ),
        (
            python_api_available,
            "python_api_unavailable",
            "TotalSegmentator Python API is unavailable",
        ),
        (task == EXPECTED_TOTAL_TASK, "task_mismatch", "TotalSegmentator task is not total"),
        (
            modality == EXPECTED_TOTAL_MODALITY,
            "modality_mismatch",
            "TotalSegmentator total task is not qualified as CT",
        ),
        (
            class_count == EXPECTED_TOTAL_CLASS_COUNT,
            "class_contract_mismatch",
            "TotalSegmentator total task class contract changed",
        ),
        (
            task_definition_sha256 == EXPECTED_TOTAL_TASK_DEFINITION_SHA256,
            "task_definition_mismatch",
            "TotalSegmentator total task definition changed",
        ),
        (
            not requires_license,
            "license_contract_mismatch",
            "TotalSegmentator total task license contract changed",
        ),
        (
            cuda_available and cuda_device_count > 0,
            "cuda_unavailable",
            "A CUDA device is required for the full-resolution baseline",
        ),
    )
    for accepted, code, message in checks:
        if not accepted:
            return TotalSegmentatorRuntimeReport(
                qualified=False,
                status_code=code,
                message=message,
                **common,
            )
    return TotalSegmentatorRuntimeReport(
        qualified=True,
        status_code="qualified",
        message="TotalSegmentator runtime contract is qualified",
        **common,
    )


class TotalSegmentatorRuntimeQualifier:
    def __init__(
        self,
        *,
        runner: ProbeRunner = subprocess.run,
        timeout_seconds: float = TOTAL_SEGMENTATOR_PROBE_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise TotalSegmentatorQualificationError("probe timeout is invalid")
        self._runner = runner
        self._timeout_seconds = float(timeout_seconds)

    def qualify(self, python_executable: str) -> TotalSegmentatorRuntimeReport:
        if (
            not isinstance(python_executable, str)
            or not python_executable.strip()
            or len(python_executable) > 4096
            or any(ord(character) < 32 for character in python_executable)
        ):
            return _failure("runtime_unavailable", "TotalSegmentator runtime is unavailable")
        command = [python_executable.strip(), "-I", "-c", _PROBE_PROGRAM]
        try:
            completed = self._runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                shell=False,
            )
        except FileNotFoundError:
            return _failure("runtime_unavailable", "TotalSegmentator runtime is unavailable")
        except subprocess.TimeoutExpired:
            return _failure("probe_timeout", "TotalSegmentator runtime probe timed out")
        except (OSError, subprocess.SubprocessError):
            return _failure("probe_failed", "TotalSegmentator runtime probe failed")
        except Exception:
            return _failure("probe_failed", "TotalSegmentator runtime probe failed")

        returncode = getattr(completed, "returncode", None)
        stdout = getattr(completed, "stdout", None)
        if returncode != 0:
            return _failure("probe_failed", "TotalSegmentator runtime probe failed")
        if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_PROBE_OUTPUT_BYTES:
            return _failure("invalid_probe_report", "TotalSegmentator probe report is invalid")
        try:
            lines = [line for line in stdout.splitlines() if line.strip()]
            if not lines:
                raise TotalSegmentatorQualificationError("probe report is empty")
            payload = json.loads(lines[-1])
            report = _parse_probe_payload(payload)
        except (json.JSONDecodeError, TotalSegmentatorQualificationError, UnicodeError):
            return _failure("invalid_probe_report", "TotalSegmentator probe report is invalid")
        return report


def validate_totalsegmentator_parameters(parameters: dict[str, object]) -> dict[str, object]:
    if not isinstance(parameters, dict):
        raise TotalSegmentatorQualificationError("TotalSegmentator parameters must be an object")
    if parameters:
        raise TotalSegmentatorQualificationError(
            "The Phase 5B baseline does not permit provider parameter overrides"
        )
    return {
        "task": EXPECTED_TOTAL_TASK,
        "output_mode": "multilabel_nifti",
        "resolution": "full",
    }


def _absolute_path(path: Path, field: str, suffix: str) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        raise TotalSegmentatorQualificationError(f"{field} must be an absolute path")
    rendered = str(path)
    if not rendered.endswith(suffix) or any(ord(character) < 32 for character in rendered):
        raise TotalSegmentatorQualificationError(f"{field} has an invalid format")
    return path.resolve(strict=False)


def build_totalsegmentator_invocation(
    *,
    python_executable: str,
    input_nifti: Path,
    output_nifti: Path,
    report_json: Path,
    device_selector: str,
    force_split: bool = False,
) -> TotalSegmentatorInvocation:
    if not isinstance(python_executable, str) or not python_executable.strip():
        raise TotalSegmentatorQualificationError("Python executable is invalid")
    if any(ord(character) < 32 for character in python_executable):
        raise TotalSegmentatorQualificationError("Python executable is invalid")
    if not CUDA_SELECTOR_PATTERN.fullmatch(device_selector):
        raise TotalSegmentatorQualificationError("An explicit CUDA device is required")
    if not isinstance(force_split, bool):
        raise TotalSegmentatorQualificationError("force_split must be boolean")

    source = _absolute_path(input_nifti, "TotalSegmentator input", ".nii.gz")
    output = _absolute_path(output_nifti, "TotalSegmentator output", ".nii.gz")
    report = _absolute_path(report_json, "TotalSegmentator report", ".json")
    if len({source, output, report}) != 3:
        raise TotalSegmentatorQualificationError("Provider input and outputs must not alias")

    upstream_device = f"gpu:{device_selector.split(':', 1)[1]}"
    command = (
        python_executable.strip(),
        "-I",
        "-m",
        "totalsegmentator.bin.TotalSegmentator",
        "-i",
        str(source),
        "-o",
        str(output),
        "--task",
        EXPECTED_TOTAL_TASK,
        "--ml",
        "--device",
        upstream_device,
        "--report",
        str(report),
    )
    if force_split:
        command += ("--force_split",)
    return TotalSegmentatorInvocation(
        command=command,
        task=EXPECTED_TOTAL_TASK,
        modality=EXPECTED_TOTAL_MODALITY,
        resolution="full",
        output_mode="multilabel_nifti",
        device_selector=device_selector,
        force_split=force_split,
    )
