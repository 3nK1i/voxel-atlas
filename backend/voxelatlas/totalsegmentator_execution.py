from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from typing import Callable, Mapping, Sequence

from .totalsegmentator_runtime import (
    EXPECTED_TOTAL_CLASS_COUNT,
    EXPECTED_TOTAL_MODALITY,
    EXPECTED_TOTAL_TASK,
    EXPECTED_TOTAL_TASK_DEFINITION_SHA256,
    PINNED_TOTALSEGMENTATOR_VERSION,
    TotalSegmentatorRuntimeQualifier,
    build_totalsegmentator_invocation,
    validate_totalsegmentator_parameters,
)
from .segmentation import (
    CanonicalSegmentationSource,
    SegmentationCancellationRequested,
    SegmentationExecutionContext,
    SegmentationExecutionRequirements,
    SegmentationModelDescriptor,
    SegmentationProviderError,
    SegmentationProviderResult,
)


WEIGHTS_MANIFEST_SCHEMA_VERSION = 1
BRIDGE_REPORT_SCHEMA_VERSION = 1
EXPECTED_TOTAL_WEIGHT_IDS = (291, 292, 293, 294, 295, 298)
MINIMUM_CUDA_FREE_MEMORY_MIB = 4096
LOW_MEMORY_CUDA_TOTAL_MIB = 8192
FORCE_SPLIT_MINIMUM_VOXELS = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_FILES = 10000
MAX_PROCESS_TIMEOUT_SECONDS = 24 * 60 * 60
MAX_PROCESS_LOG_BYTES = 16 * 1024 * 1024
PROCESS_POLL_SECONDS = 0.25
PROCESS_TERMINATE_GRACE_SECONDS = 5.0
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
WEIGHT_DATASET_PATTERN = re.compile(r"^Dataset([0-9]{3})(?:_|$)")


class TotalSegmentatorExecutionError(ValueError):
    """A safe Phase 5B2 execution-contract failure."""


class ProcessExecutionError(TotalSegmentatorExecutionError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class TotalSegmentatorRuntimePaths:
    root: Path
    home: Path
    weights: Path
    config_path: Path
    weights_manifest_path: Path


@dataclass(frozen=True, slots=True)
class TotalSegmentatorCommand:
    command: tuple[str, ...]
    environment: dict[str, str]
    shell: bool = False


@dataclass(frozen=True, slots=True)
class TotalSegmentatorWeightsManifest:
    task_ids: tuple[int, ...]
    files: tuple[dict[str, object], ...]
    total_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ProcessExecutionResult:
    returncode: int
    duration_seconds: float
    stdout_path: Path
    stderr_path: Path

    def public_dict(self) -> dict[str, object]:
        return {
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 3),
        }


PopenFactory = Callable[..., object]
Clock = Callable[[], float]
Sleeper = Callable[[float], None]


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
        raise TotalSegmentatorExecutionError("Execution metadata is invalid") from exc


def _sha256_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise TotalSegmentatorExecutionError("Provider artifact is unreadable") from exc
    return digest.hexdigest()


def _validated_process_command(command: Sequence[str]) -> tuple[str, ...]:
    if not command:
        raise ProcessExecutionError("invalid_command", "Provider command is invalid")
    normalized = tuple(command)
    for index, argument in enumerate(normalized):
        if not isinstance(argument, str) or not argument or "\x00" in argument:
            raise ProcessExecutionError("invalid_command", "Provider command is invalid")
        controls = {character for character in argument if ord(character) < 32}
        if not controls:
            continue
        is_python_program = index > 0 and normalized[index - 1] == "-c"
        if not is_python_program or not controls.issubset({"\t", "\n", "\r"}):
            raise ProcessExecutionError("invalid_command", "Provider command is invalid")
    return normalized


def _strict_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise TotalSegmentatorExecutionError(f"{field} is invalid")
    return value


def _strict_int(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise TotalSegmentatorExecutionError(f"{field} is invalid")
    return value


def _strict_shape(value: object) -> tuple[int, int, int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value)
    ):
        raise TotalSegmentatorExecutionError("Volume shape is invalid")
    return (int(value[0]), int(value[1]), int(value[2]))


def _safe_directory(path: Path, field: str) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise TotalSegmentatorExecutionError(f"{field} is unsafe")


def build_controlled_runtime_paths(data_dir: Path) -> TotalSegmentatorRuntimePaths:
    if not isinstance(data_dir, Path):
        raise TotalSegmentatorExecutionError("VoxelAtlas data directory is invalid")
    resolved = data_dir.expanduser().resolve(strict=False)
    root = (
        resolved
        / "segmentation"
        / "providers"
        / "totalsegmentator"
        / PINNED_TOTALSEGMENTATOR_VERSION
    )
    return TotalSegmentatorRuntimePaths(
        root=root,
        home=root / "home",
        weights=root / "weights",
        config_path=root / "home" / "config.json",
        weights_manifest_path=root / "weights-manifest.json",
    )


def prepare_controlled_runtime(paths: TotalSegmentatorRuntimePaths) -> None:
    if not isinstance(paths, TotalSegmentatorRuntimePaths):
        raise TotalSegmentatorExecutionError("Provider runtime paths are invalid")
    for directory, field in (
        (paths.root, "Provider runtime directory"),
        (paths.home, "Provider home directory"),
        (paths.weights, "Provider weights directory"),
    ):
        _safe_directory(directory, field)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
    if paths.config_path.is_symlink() or (
        paths.config_path.exists() and not paths.config_path.is_file()
    ):
        raise TotalSegmentatorExecutionError("Provider configuration path is unsafe")
    payload = {
        "totalseg_id": "voxelatlas-controlled",
        "send_usage_stats": False,
        "prediction_counter": 0,
        "statistics_disclaimer_shown": True,
    }
    temporary = paths.config_path.with_name("config.json.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise TotalSegmentatorExecutionError("Provider configuration temporary path is unsafe")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            os.chmod(temporary, 0o600)
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, paths.config_path)
        os.chmod(paths.config_path, 0o600)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise TotalSegmentatorExecutionError("Provider configuration could not be stored") from exc


def build_totalsegmentator_environment(
    paths: TotalSegmentatorRuntimePaths,
    *,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if base_environment is None else base_environment
    environment = {str(key): str(value) for key, value in source.items()}
    controlled = {
        "TOTALSEG_HOME_DIR": str(paths.home),
        "TOTALSEG_WEIGHTS_PATH": str(paths.weights),
        "nnUNet_results": str(paths.weights),
        "nnUNet_raw": str(paths.root / "nnunet-raw"),
        "nnUNet_preprocessed": str(paths.root / "nnunet-preprocessed"),
        "PYTHONNOUSERSITE": "1",
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
    }
    environment.update(controlled)
    return environment


def build_weights_download_invocation(
    *,
    python_executable: str,
    paths: TotalSegmentatorRuntimePaths,
) -> TotalSegmentatorCommand:
    if (
        not isinstance(python_executable, str)
        or not python_executable.strip()
        or any(ord(character) < 32 for character in python_executable)
    ):
        raise TotalSegmentatorExecutionError("Python executable is invalid")
    return TotalSegmentatorCommand(
        command=(
            python_executable.strip(),
            "-I",
            "-m",
            "totalsegmentator.bin.totalseg_download_weights",
            "--task",
            EXPECTED_TOTAL_TASK,
        ),
        environment=build_totalsegmentator_environment(paths),
    )


def _inventory_weights(weights: Path) -> tuple[tuple[int, ...], tuple[dict[str, object], ...], int]:
    _safe_directory(weights, "Provider weights directory")
    if not weights.is_dir():
        raise TotalSegmentatorExecutionError("Provider weights are unavailable")
    dataset_ids: set[int] = set()
    files: list[dict[str, object]] = []
    total_bytes = 0
    try:
        entries = sorted(weights.rglob("*"), key=lambda item: item.as_posix())
    except OSError as exc:
        raise TotalSegmentatorExecutionError("Provider weights are unreadable") from exc
    for item in entries:
        if item.is_symlink():
            raise TotalSegmentatorExecutionError("Provider weights must not contain symlinks")
        relative = item.relative_to(weights)
        first = relative.parts[0] if relative.parts else ""
        match = WEIGHT_DATASET_PATTERN.fullmatch(first.split("/", 1)[0])
        if match is None:
            match = WEIGHT_DATASET_PATTERN.match(first)
        if match is not None:
            dataset_ids.add(int(match.group(1)))
        if item.is_dir():
            continue
        if not item.is_file():
            raise TotalSegmentatorExecutionError("Provider weights contain an unsafe entry")
        size = item.stat().st_size
        if size <= 0:
            raise TotalSegmentatorExecutionError("Provider weights contain an empty artifact")
        if len(files) >= MAX_ARTIFACT_FILES:
            raise TotalSegmentatorExecutionError("Provider weight inventory is too large")
        rendered = relative.as_posix()
        if rendered.startswith("/") or ".." in relative.parts:
            raise TotalSegmentatorExecutionError("Provider weight path is unsafe")
        files.append({"path": rendered, "bytes": size, "sha256": _sha256_file(item)})
        total_bytes += size
    if tuple(sorted(dataset_ids)) != EXPECTED_TOTAL_WEIGHT_IDS:
        raise TotalSegmentatorExecutionError("The TotalSegmentator total-task weight set is incomplete")
    if not files:
        raise TotalSegmentatorExecutionError("Provider weight inventory is empty")
    return tuple(sorted(dataset_ids)), tuple(files), total_bytes


def _manifest_body(
    task_ids: tuple[int, ...], files: tuple[dict[str, object], ...], total_bytes: int
) -> dict[str, object]:
    return {
        "schema_version": WEIGHTS_MANIFEST_SCHEMA_VERSION,
        "provider": "TotalSegmentator",
        "provider_version": PINNED_TOTALSEGMENTATOR_VERSION,
        "task": EXPECTED_TOTAL_TASK,
        "task_ids": list(task_ids),
        "files": list(files),
        "total_bytes": total_bytes,
    }


def create_weights_manifest(paths: TotalSegmentatorRuntimePaths) -> TotalSegmentatorWeightsManifest:
    task_ids, files, total_bytes = _inventory_weights(paths.weights)
    body = _manifest_body(task_ids, files, total_bytes)
    digest = sha256(_canonical_json(body)).hexdigest()
    payload = {
        **body,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": digest,
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if len(encoded.encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise TotalSegmentatorExecutionError("Provider weight manifest is too large")
    temporary = paths.weights_manifest_path.with_name("weights-manifest.json.tmp")
    if paths.weights_manifest_path.is_symlink() or temporary.exists() or temporary.is_symlink():
        raise TotalSegmentatorExecutionError("Provider weight manifest path is unsafe")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            os.chmod(temporary, 0o600)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, paths.weights_manifest_path)
        os.chmod(paths.weights_manifest_path, 0o600)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise TotalSegmentatorExecutionError("Provider weight manifest could not be stored") from exc
    return TotalSegmentatorWeightsManifest(task_ids, files, total_bytes, digest)


def load_weights_manifest(paths: TotalSegmentatorRuntimePaths) -> TotalSegmentatorWeightsManifest:
    path = paths.weights_manifest_path
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise TotalSegmentatorExecutionError("Qualified provider weight manifest is unavailable")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise TotalSegmentatorExecutionError("Qualified provider weight manifest is unreadable") from exc
    task_ids, files, total_bytes = _inventory_weights(paths.weights)
    body = _manifest_body(task_ids, files, total_bytes)
    digest = sha256(_canonical_json(body)).hexdigest()
    if not isinstance(payload, dict):
        raise TotalSegmentatorExecutionError("Qualified provider weight manifest is invalid")
    stored_body = {key: payload.get(key) for key in body}
    if (
        set(payload) != set(body) | {"created_at_utc", "manifest_sha256"}
        or stored_body != body
        or payload.get("manifest_sha256") != digest
        or not isinstance(payload.get("created_at_utc"), str)
    ):
        raise TotalSegmentatorExecutionError("Qualified provider weights changed after acquisition")
    return TotalSegmentatorWeightsManifest(task_ids, files, total_bytes, digest)


def select_memory_strategy(
    *, total_memory_mib: int, free_memory_mib: int, source_shape: Sequence[int]
) -> str:
    total = _strict_int(total_memory_mib, "CUDA total memory", minimum=1)
    free = _strict_int(free_memory_mib, "CUDA free memory")
    shape = _strict_shape(source_shape)
    if free > total:
        raise TotalSegmentatorExecutionError("CUDA memory inventory is inconsistent")
    if free < MINIMUM_CUDA_FREE_MEMORY_MIB:
        raise TotalSegmentatorExecutionError("CUDA free memory is below the Phase 5B2 floor")
    voxels = shape[0] * shape[1] * shape[2]
    if total < LOW_MEMORY_CUDA_TOTAL_MIB and voxels >= FORCE_SPLIT_MINIMUM_VOXELS:
        return "force_split"
    return "direct_full_resolution"


def _validate_affine(value: object) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != 4:
        raise TotalSegmentatorExecutionError("Bridge affine is invalid")
    result: list[list[float]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != 4:
            raise TotalSegmentatorExecutionError("Bridge affine is invalid")
        converted = []
        for item in row:
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not isfinite(item):
                raise TotalSegmentatorExecutionError("Bridge affine is invalid")
            converted.append(float(item))
        result.append(converted)
    if result[3] != [0.0, 0.0, 0.0, 1.0]:
        raise TotalSegmentatorExecutionError("Bridge affine is invalid")
    return result


def validate_bridge_export_report(
    payload: object,
    *,
    expected_source_sha256: str,
    expected_descriptor_sha256: str,
    expected_shape: Sequence[int],
) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.get("schema_version") != BRIDGE_REPORT_SCHEMA_VERSION:
        raise TotalSegmentatorExecutionError("Canonical NIfTI bridge report is invalid")
    shape = _strict_shape(payload.get("shape"))
    if payload.get("operation") != "export" or shape != _strict_shape(expected_shape):
        raise TotalSegmentatorExecutionError("Canonical NIfTI bridge report is inconsistent")
    if payload.get("dtype") != "float32" or payload.get("axis_order") != ["slice", "row", "column"]:
        raise TotalSegmentatorExecutionError("Canonical NIfTI bridge source contract changed")
    if (
        payload.get("source_artifact_sha256") != _strict_sha256(expected_source_sha256, "Source digest")
        or payload.get("source_descriptor_sha256")
        != _strict_sha256(expected_descriptor_sha256, "Descriptor digest")
    ):
        raise TotalSegmentatorExecutionError("Canonical NIfTI bridge source changed")
    _strict_sha256(payload.get("output_nifti_sha256"), "NIfTI digest")
    _validate_affine(payload.get("array_index_to_patient_ras"))
    _strict_int(payload.get("output_bytes"), "NIfTI size", minimum=1)
    return json.loads(_canonical_json(payload).decode("utf-8"))


def validate_mask_inspection_report(
    payload: object,
    *,
    expected_input_sha256: str,
    expected_shape: Sequence[int],
) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.get("schema_version") != BRIDGE_REPORT_SCHEMA_VERSION:
        raise TotalSegmentatorExecutionError("Segmentation mask inspection report is invalid")
    shape = _strict_shape(payload.get("shape"))
    if payload.get("operation") != "inspect" or shape != _strict_shape(expected_shape):
        raise TotalSegmentatorExecutionError("Segmentation mask geometry changed")
    if payload.get("input_nifti_sha256") != _strict_sha256(expected_input_sha256, "Input digest"):
        raise TotalSegmentatorExecutionError("Segmentation mask input changed")
    _strict_sha256(payload.get("mask_nifti_sha256"), "Mask digest")
    if payload.get("affine_matches_input") is not True or payload.get("integer_labels") is not True:
        raise TotalSegmentatorExecutionError("Segmentation mask geometry or labels are invalid")
    minimum = _strict_int(payload.get("minimum_label"), "Minimum label")
    maximum = _strict_int(payload.get("maximum_label"), "Maximum label")
    if minimum != 0 or maximum > EXPECTED_TOTAL_CLASS_COUNT or maximum < minimum:
        raise TotalSegmentatorExecutionError("Segmentation mask labels are outside the task contract")
    labels = payload.get("present_labels")
    if (
        not isinstance(labels, list)
        or labels != sorted(set(labels))
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > EXPECTED_TOTAL_CLASS_COUNT for item in labels)
    ):
        raise TotalSegmentatorExecutionError("Segmentation mask label inventory is invalid")
    _strict_int(payload.get("nonzero_voxels"), "Nonzero voxel count")
    _strict_int(payload.get("output_bytes"), "Mask size", minimum=1)
    return json.loads(_canonical_json(payload).decode("utf-8"))


def validate_provider_run_report(
    payload: object, *, expected_input: Path, expected_output: Path
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise TotalSegmentatorExecutionError("TotalSegmentator run report is invalid")
    checks = (
        (payload.get("totalsegmentator_version") == PINNED_TOTALSEGMENTATOR_VERSION),
        (payload.get("task") == EXPECTED_TOTAL_TASK),
        (payload.get("modality") == EXPECTED_TOTAL_MODALITY),
        (payload.get("license_required") is False),
        (payload.get("device") == "gpu"),
        (payload.get("fast") is False),
        (payload.get("fastest") is False),
        (payload.get("save_lowres") is False),
        (payload.get("multilabel") is True),
        (payload.get("output_type") == "nifti"),
        (payload.get("roi_subset") is None),
        (payload.get("input") == str(expected_input.resolve(strict=False))),
        (payload.get("output") == str(expected_output.resolve(strict=False))),
        (payload.get("num_classes") == EXPECTED_TOTAL_CLASS_COUNT),
    )
    if not all(checks):
        raise TotalSegmentatorExecutionError("TotalSegmentator run contract changed")
    classes = payload.get("classes")
    expected_keys = [str(index) for index in range(1, EXPECTED_TOTAL_CLASS_COUNT + 1)]
    if not isinstance(classes, dict) or sorted(classes, key=int) != expected_keys:
        raise TotalSegmentatorExecutionError("TotalSegmentator class report changed")
    runtime = payload.get("runtime_seconds")
    if isinstance(runtime, bool) or not isinstance(runtime, (int, float)) or not isfinite(runtime) or runtime < 0:
        raise TotalSegmentatorExecutionError("TotalSegmentator runtime report is invalid")
    output_files = payload.get("output_files")
    if not isinstance(output_files, list) or any(not isinstance(item, str) for item in output_files):
        raise TotalSegmentatorExecutionError("TotalSegmentator output report is invalid")
    return {
        "provider_version": PINNED_TOTALSEGMENTATOR_VERSION,
        "task": EXPECTED_TOTAL_TASK,
        "modality": EXPECTED_TOTAL_MODALITY,
        "device": "cuda",
        "resolution": "full",
        "output_mode": "multilabel_nifti",
        "class_count": EXPECTED_TOTAL_CLASS_COUNT,
        "task_definition_sha256": EXPECTED_TOTAL_TASK_DEFINITION_SHA256,
        "runtime_seconds": float(runtime),
    }


class SupervisedProcessRunner:
    def __init__(
        self,
        *,
        popen: PopenFactory = subprocess.Popen,
        monotonic: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        self._popen = popen
        self._monotonic = monotonic
        self._sleeper = sleeper

    @staticmethod
    def _stop_process(process: object) -> None:
        pid = getattr(process, "pid", None)
        if isinstance(pid, int) and pid > 0:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)  # type: ignore[attr-defined]
                return
            except Exception:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                    process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)  # type: ignore[attr-defined]
                    return
                except Exception:
                    pass
        try:
            process.terminate()  # type: ignore[attr-defined]
            process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)  # type: ignore[attr-defined]
        except Exception:
            try:
                process.kill()  # type: ignore[attr-defined]
                process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)  # type: ignore[attr-defined]
            except Exception:
                pass

    def run(
        self,
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        working_directory: Path,
        timeout_seconds: float,
        cancellation_check: Callable[[], bool],
        log_prefix: str = "provider",
        max_log_bytes: int = MAX_PROCESS_LOG_BYTES,
    ) -> ProcessExecutionResult:
        normalized_command = _validated_process_command(command)
        if timeout_seconds <= 0 or timeout_seconds > MAX_PROCESS_TIMEOUT_SECONDS:
            raise ProcessExecutionError("invalid_timeout", "Provider timeout is invalid")
        if max_log_bytes <= 0 or max_log_bytes > MAX_PROCESS_LOG_BYTES:
            raise ProcessExecutionError("invalid_log_limit", "Provider log limit is invalid")
        directory = working_directory.resolve(strict=False)
        _safe_directory(directory, "Provider working directory")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        stdout_path = directory / f"{log_prefix}.stdout.log"
        stderr_path = directory / f"{log_prefix}.stderr.log"
        if any(path.exists() or path.is_symlink() for path in (stdout_path, stderr_path)):
            raise ProcessExecutionError("unsafe_log", "Provider log path is unsafe")
        start = self._monotonic()
        try:
            with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
                os.chmod(stdout_path, 0o600)
                os.chmod(stderr_path, 0o600)
                process = self._popen(
                    list(normalized_command),
                    cwd=str(directory),
                    env=dict(environment),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    shell=False,
                    start_new_session=True,
                )
                while process.poll() is None:  # type: ignore[attr-defined]
                    if cancellation_check():
                        self._stop_process(process)
                        raise ProcessExecutionError("cancelled", "Provider execution was cancelled")
                    if self._monotonic() - start >= timeout_seconds:
                        self._stop_process(process)
                        raise ProcessExecutionError("timeout", "Provider execution timed out")
                    try:
                        log_bytes = stdout_path.stat().st_size + stderr_path.stat().st_size
                    except OSError:
                        log_bytes = max_log_bytes + 1
                    if log_bytes > max_log_bytes:
                        self._stop_process(process)
                        raise ProcessExecutionError(
                            "log_limit", "Provider execution exceeded its log limit"
                        )
                    self._sleeper(PROCESS_POLL_SECONDS)
                returncode = int(process.returncode)  # type: ignore[attr-defined]
                if stdout_path.stat().st_size + stderr_path.stat().st_size > max_log_bytes:
                    raise ProcessExecutionError(
                        "log_limit", "Provider execution exceeded its log limit"
                    )
        except ProcessExecutionError:
            raise
        except FileNotFoundError as exc:
            raise ProcessExecutionError("runtime_unavailable", "Provider runtime is unavailable") from exc
        except OSError as exc:
            raise ProcessExecutionError("process_failed", "Provider process could not be executed") from exc
        duration = max(0.0, self._monotonic() - start)
        if returncode != 0:
            raise ProcessExecutionError("nonzero_exit", "Provider process failed")
        return ProcessExecutionResult(returncode, duration, stdout_path, stderr_path)


_CUDA_PREFLIGHT_PROGRAM = r'''
import importlib
import json
import sys

torch = importlib.import_module("torch")
index = int(sys.argv[1])
if not torch.cuda.is_available() or index >= torch.cuda.device_count():
    raise SystemExit(2)
torch.cuda.set_device(index)
free_bytes, total_bytes = torch.cuda.mem_get_info(index)
probe = torch.ones((256, 256), device=f"cuda:{index}")
result = float((probe * probe).sum().item())
properties = torch.cuda.get_device_properties(index)
print(json.dumps({
    "schema_version": 1,
    "index": index,
    "name": properties.name,
    "free_memory_mib": int(free_bytes // (1024 * 1024)),
    "total_memory_mib": int(total_bytes // (1024 * 1024)),
    "compute_capability": [properties.major, properties.minor],
    "execution_result": result,
}, sort_keys=True, separators=(",", ":")))
'''.strip()


def _last_json_line(path: Path, field: str, *, maximum_bytes: int = 128 * 1024) -> object:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum_bytes:
            raise TotalSegmentatorExecutionError(f"{field} is invalid")
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            raise TotalSegmentatorExecutionError(f"{field} is invalid")
        return json.loads(lines[-1])
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TotalSegmentatorExecutionError(f"{field} is invalid") from exc


def _load_json_file(path: Path, field: str, *, maximum_bytes: int = 1024 * 1024) -> object:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum_bytes:
            raise TotalSegmentatorExecutionError(f"{field} is invalid")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TotalSegmentatorExecutionError(f"{field} is invalid") from exc


def _validate_cuda_preflight(payload: object, *, expected_index: int) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise TotalSegmentatorExecutionError("CUDA execution preflight report is invalid")
    index = _strict_int(payload.get("index"), "CUDA index")
    total = _strict_int(payload.get("total_memory_mib"), "CUDA total memory", minimum=1)
    free = _strict_int(payload.get("free_memory_mib"), "CUDA free memory")
    capability = payload.get("compute_capability")
    name = payload.get("name")
    result = payload.get("execution_result")
    if (
        index != expected_index
        or free > total
        or not isinstance(name, str)
        or not name.strip()
        or len(name) > 128
        or "/" in name
        or "\\" in name
        or not isinstance(capability, list)
        or len(capability) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in capability)
        or isinstance(result, bool)
        or not isinstance(result, (int, float))
        or not isfinite(result)
        or result <= 0
    ):
        raise TotalSegmentatorExecutionError("CUDA execution preflight report is invalid")
    return {
        "index": index,
        "name": name.strip(),
        "total_memory_mib": total,
        "free_memory_mib": free,
        "compute_capability": capability,
    }


def _load_source_shape(source: CanonicalSegmentationSource) -> tuple[int, int, int]:
    payload = _load_json_file(source.metadata_path, "Canonical volume metadata")
    if not isinstance(payload, dict) or payload.get("modality") != EXPECTED_TOTAL_MODALITY:
        raise TotalSegmentatorExecutionError("Canonical CT volume metadata is invalid")
    return _strict_shape(payload.get("shape"))


class TotalSegmentatorProvider:
    """Qualified, subprocess-isolated Phase 5B2 TotalSegmentator provider."""

    descriptor = SegmentationModelDescriptor(
        provider_id="totalsegmentator",
        provider_version=PINNED_TOTALSEGMENTATOR_VERSION,
        model_id="total",
        model_version=PINNED_TOTALSEGMENTATOR_VERSION,
        display_name="TotalSegmentator total task",
        task="multi_structure",
        capabilities=("anatomical_segmentation", "full_resolution"),
        supported_modalities=("CT",),
        available=True,
        availability_reason=None,
        execution=SegmentationExecutionRequirements(
            supported_devices=("cuda",),
            minimum_cuda_memory_mib=MINIMUM_CUDA_FREE_MEMORY_MIB,
        ),
    )

    def __init__(
        self,
        *,
        data_dir: Path,
        python_executable: str,
        bridge_script: Path,
        process_runner: SupervisedProcessRunner | None = None,
        runtime_qualifier: TotalSegmentatorRuntimeQualifier | None = None,
        inference_timeout_seconds: float = 6 * 60 * 60,
    ) -> None:
        self.paths = build_controlled_runtime_paths(data_dir)
        self.python_executable = str(python_executable).strip()
        self.bridge_script = bridge_script.resolve(strict=False)
        if (
            not self.python_executable
            or any(ord(character) < 32 for character in self.python_executable)
            or not self.bridge_script.is_absolute()
            or self.bridge_script.is_symlink()
            or not self.bridge_script.is_file()
        ):
            raise TotalSegmentatorExecutionError("Provider runtime configuration is invalid")
        if inference_timeout_seconds <= 0 or inference_timeout_seconds > MAX_PROCESS_TIMEOUT_SECONDS:
            raise TotalSegmentatorExecutionError("Provider inference timeout is invalid")
        self.process_runner = process_runner or SupervisedProcessRunner()
        self.runtime_qualifier = runtime_qualifier or TotalSegmentatorRuntimeQualifier()
        self.inference_timeout_seconds = float(inference_timeout_seconds)

    def validate_parameters(self, parameters: dict[str, object]) -> dict[str, object]:
        try:
            return validate_totalsegmentator_parameters(parameters)
        except ValueError as exc:
            raise TotalSegmentatorExecutionError(str(exc)) from exc

    def _run_command(
        self,
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        directory: Path,
        timeout: float,
        context: SegmentationExecutionContext,
        log_prefix: str,
        max_log_bytes: int = MAX_PROCESS_LOG_BYTES,
    ) -> ProcessExecutionResult:
        try:
            return self.process_runner.run(
                command,
                environment=environment,
                working_directory=directory,
                timeout_seconds=timeout,
                cancellation_check=lambda: context.cancellation_requested,
                log_prefix=log_prefix,
                max_log_bytes=max_log_bytes,
            )
        except ProcessExecutionError as exc:
            if exc.code == "cancelled":
                raise SegmentationCancellationRequested("Segmentation cancellation requested") from exc
            raise SegmentationProviderError("TotalSegmentator subprocess failed") from exc

    def run(self, context: SegmentationExecutionContext) -> SegmentationProviderResult:
        if context.model.descriptor_sha256 != self.descriptor.descriptor_sha256:
            raise SegmentationProviderError("TotalSegmentator model binding changed")
        if context.source.modality != EXPECTED_TOTAL_MODALITY:
            raise SegmentationProviderError("TotalSegmentator input must be CT")
        if context.device.kind != "cuda" or context.device.index is None:
            raise SegmentationProviderError("TotalSegmentator requires an explicit CUDA device")
        if context.parameters != validate_totalsegmentator_parameters({}):
            raise SegmentationProviderError("TotalSegmentator parameter provenance changed")
        context.raise_if_cancelled()

        prepare_controlled_runtime(self.paths)
        weights = load_weights_manifest(self.paths)
        runtime = self.runtime_qualifier.qualify(self.python_executable)
        if not runtime.qualified or not any(
            device.index == context.device.index for device in runtime.cuda_devices
        ):
            raise SegmentationProviderError("Qualified TotalSegmentator runtime changed")
        environment = build_totalsegmentator_environment(self.paths)

        job_root = (
            self.paths.root.parents[2]
            / "jobs"
            / context.job_id
            / "provider"
            / "totalsegmentator"
        )
        expected_jobs_root = self.paths.root.parents[2] / "jobs"
        if job_root.parents[2] != expected_jobs_root or job_root.is_symlink():
            raise SegmentationProviderError("Provider job directory is unsafe")
        input_dir = job_root / "input"
        output_dir = job_root / "output"
        logs_dir = job_root / "logs"
        for directory in (job_root, input_dir, output_dir, logs_dir):
            _safe_directory(directory, "Provider job directory")
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(directory, 0o700)

        context.report_progress(stage="preparing", percent=5.0, message="Checking CUDA execution")
        preflight_result = self._run_command(
            (
                self.python_executable,
                "-I",
                "-c",
                _CUDA_PREFLIGHT_PROGRAM,
                str(context.device.index),
            ),
            environment=environment,
            directory=logs_dir,
            timeout=60.0,
            context=context,
            log_prefix="cuda-preflight",
            max_log_bytes=128 * 1024,
        )
        cuda = _validate_cuda_preflight(
            _last_json_line(preflight_result.stdout_path, "CUDA execution preflight report"),
            expected_index=context.device.index,
        )
        source_shape = _load_source_shape(context.source)
        memory_strategy = select_memory_strategy(
            total_memory_mib=int(cuda["total_memory_mib"]),
            free_memory_mib=int(cuda["free_memory_mib"]),
            source_shape=source_shape,
        )

        input_nifti = input_dir / "canonical-volume.nii.gz"
        output_nifti = output_dir / "labels.nii.gz"
        provider_report_path = output_dir / "provider-report.json"
        context.report_progress(
            stage="preparing", percent=12.0, message="Exporting canonical CT volume"
        )
        bridge_result = self._run_command(
            (
                self.python_executable,
                "-I",
                str(self.bridge_script),
                "export",
                "--source-npy",
                str(context.source.volume_path),
                "--metadata-json",
                str(context.source.metadata_path),
                "--output-nifti",
                str(input_nifti),
            ),
            environment=environment,
            directory=logs_dir,
            timeout=30 * 60,
            context=context,
            log_prefix="nifti-export",
            max_log_bytes=128 * 1024,
        )
        export = validate_bridge_export_report(
            _last_json_line(bridge_result.stdout_path, "Canonical NIfTI bridge report"),
            expected_source_sha256=context.source.artifact_sha256,
            expected_descriptor_sha256=context.source.descriptor_sha256,
            expected_shape=source_shape,
        )
        if _sha256_file(input_nifti) != export["output_nifti_sha256"]:
            raise SegmentationProviderError("Canonical NIfTI export changed")

        context.report_progress(
            stage="loading_model", percent=20.0, message="Loading qualified segmentation model"
        )
        invocation = build_totalsegmentator_invocation(
            python_executable=self.python_executable,
            input_nifti=input_nifti,
            output_nifti=output_nifti,
            report_json=provider_report_path,
            device_selector=context.device.selector,
            force_split=memory_strategy == "force_split",
        )
        context.report_progress(
            stage="inference", percent=25.0, message="Running full-resolution CT segmentation"
        )
        execution = self._run_command(
            invocation.command,
            environment=environment,
            directory=logs_dir,
            timeout=self.inference_timeout_seconds,
            context=context,
            log_prefix="totalsegmentator",
        )
        if not output_nifti.is_file() or output_nifti.is_symlink():
            raise SegmentationProviderError("TotalSegmentator output is missing")
        provider_report = validate_provider_run_report(
            _load_json_file(provider_report_path, "TotalSegmentator run report"),
            expected_input=input_nifti,
            expected_output=output_nifti,
        )

        context.report_progress(
            stage="postprocessing", percent=90.0, message="Validating segmentation mask"
        )
        inspection_result = self._run_command(
            (
                self.python_executable,
                "-I",
                str(self.bridge_script),
                "inspect",
                "--input-nifti",
                str(input_nifti),
                "--mask-nifti",
                str(output_nifti),
            ),
            environment=environment,
            directory=logs_dir,
            timeout=30 * 60,
            context=context,
            log_prefix="mask-inspection",
            max_log_bytes=128 * 1024,
        )
        inspection = validate_mask_inspection_report(
            _last_json_line(inspection_result.stdout_path, "Segmentation mask inspection report"),
            expected_input_sha256=str(export["output_nifti_sha256"]),
            expected_shape=source_shape,
        )
        if _sha256_file(output_nifti) != inspection["mask_nifti_sha256"]:
            raise SegmentationProviderError("Segmentation mask changed after inspection")
        context.report_progress(
            stage="finalizing", percent=98.0, message="Recording execution provenance"
        )
        return SegmentationProviderResult(
            outcome={
                "code": "qualified_execution",
                "message": "Full-resolution non-clinical CT segmentation completed",
                "provider": provider_report,
                "weights_manifest_sha256": weights.sha256,
                "memory_strategy": memory_strategy,
                "cuda": {
                    "selector": context.device.selector,
                    "name": cuda["name"],
                    "total_memory_mib": cuda["total_memory_mib"],
                    "free_memory_mib_at_start": cuda["free_memory_mib"],
                    "compute_capability": cuda["compute_capability"],
                },
                "input_nifti_sha256": export["output_nifti_sha256"],
                "mask_nifti_sha256": inspection["mask_nifti_sha256"],
                "mask_bytes": inspection["output_bytes"],
                "present_labels": inspection["present_labels"],
                "nonzero_voxels": inspection["nonzero_voxels"],
                "mask_artifact": "provider/totalsegmentator/output/labels.nii.gz",
                "provider_runtime_seconds": provider_report["runtime_seconds"],
                "supervisor_runtime_seconds": execution.public_dict()["duration_seconds"],
                "clinical_validation": "not_claimed",
            }
        )
