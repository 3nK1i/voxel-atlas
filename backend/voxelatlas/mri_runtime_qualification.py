"""6J-C1: isolated, read-only TotalSegmentator total_mr runtime qualification.

Checks task identity and CUDA visibility without touching studies, downloading weights,
registering a provider, or authorizing segmentation execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
import subprocess
from typing import Callable

from .mri_task_contract import TOTAL_SEGMENTATOR_MRI_STRUCTURES


MRI_RUNTIME_SCHEMA_VERSION = 1
MRI_MAPPING_JSON_SHA256 = "6774138ed2bb2f6056d33a01e716ffd51a07399539a8b24ebe42887c0a77f20b"
MRI_RUNTIME_TIMEOUT_SECONDS = 60.0
MAX_PROBE_BYTES = 64 * 1024
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


def _canonical_mapping(mapping: dict[int, str]) -> bytes:
    return json.dumps(
        {str(k): v for k, v in sorted(mapping.items())},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


if hashlib.sha256(_canonical_mapping(TOTAL_SEGMENTATOR_MRI_STRUCTURES)).hexdigest() != MRI_MAPPING_JSON_SHA256:
    raise RuntimeError("Pinned MRI class map no longer matches inspected runtime definition")


@dataclass(frozen=True, slots=True)
class MRIRuntimeQualificationReport:
    runtime_qualified: bool
    status_code: str
    message: str
    task: str = "total_mr"
    task_modality: str = "MR"
    task_class_count: int | None = None
    task_mapping_sha256: str | None = None
    totalsegmentator_version: str | None = None
    python_version: str | None = None
    cuda_device_count: int | None = None
    cuda_total_memory_mib: tuple[int, ...] = ()
    # A qualified runtime is insufficient: weights, memory policy, image bridge,
    # and execution have not been qualified in C1.
    execution_ready: bool = False

    def public_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["cuda_total_memory_mib"] = list(self.cuda_total_memory_mib)
        return data


def _fail(code: str, message: str) -> MRIRuntimeQualificationReport:
    return MRIRuntimeQualificationReport(False, code, message)


_PROBE_PROGRAM = r'''
import hashlib
import importlib.metadata
import json
import platform

from totalsegmentator import registry
import torch

classes = registry.get_task_classes("total_mr")
normalized = {str(k): str(v) for k, v in sorted(classes.items())}
canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
visible = bool(torch.cuda.is_available())
count = int(torch.cuda.device_count()) if visible else 0
memory = [int(torch.cuda.get_device_properties(i).total_memory // (1024 * 1024)) for i in range(count)]
print(json.dumps({
    "schema_version": 1,
    "python_version": platform.python_version(),
    "totalsegmentator_version": importlib.metadata.version("TotalSegmentator"),
    "torch_version": importlib.metadata.version("torch"),
    "nnunetv2_version": importlib.metadata.version("nnunetv2"),
    "python_api_available": callable(__import__("totalsegmentator.python_api", fromlist=["totalsegmentator"]).totalsegmentator),
    "task": "total_mr",
    "task_modality": registry.task_modality("total_mr"),
    "task_class_count": len(classes),
    "task_mapping_sha256": hashlib.sha256(canonical).hexdigest(),
    "cuda_available": visible,
    "cuda_device_count": count,
    "cuda_total_memory_mib": memory,
}, sort_keys=True, separators=(",", ":")))
'''.strip()


def qualify_mri_runtime_payload(payload: object) -> MRIRuntimeQualificationReport:
    """Validate one structured result from the isolated MRI interpreter."""
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] != MRI_RUNTIME_SCHEMA_VERSION:
        return _fail("invalid_probe_report", "MRI runtime probe schema is invalid")
    python_version = payload.get("python_version")
    version = payload.get("totalsegmentator_version")
    if not isinstance(python_version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", python_version):
        return _fail("invalid_probe_report", "MRI runtime Python version is invalid")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        return _fail("invalid_probe_report", "MRI runtime provider version is invalid")
    if tuple(map(int, python_version.split(".")))[:2] < (3, 10):
        return _fail("python_version_unsupported", "MRI runtime Python version is unsupported")
    if version != "2.18.0":
        return _fail("version_mismatch", "MRI runtime TotalSegmentator version does not match the pinned contract")
    if payload.get("task") != "total_mr" or payload.get("task_modality") != "MR":
        return _fail("task_mismatch", "MRI runtime task identity or modality is invalid")
    if type(payload.get("task_class_count")) is not int or payload["task_class_count"] != 50:
        return _fail("class_contract_mismatch", "MRI runtime task class count is invalid")
    if payload.get("task_mapping_sha256") != MRI_MAPPING_JSON_SHA256:
        return _fail("mapping_mismatch", "MRI runtime anatomical mapping differs from pinned total_mr")
    if payload.get("python_api_available") is not True:
        return _fail("python_api_unavailable", "MRI runtime Python API is unavailable")
    for field in ("torch_version", "nnunetv2_version"):
        if not isinstance(payload.get(field), str) or not _VERSION.fullmatch(payload[field]):
            return _fail("invalid_probe_report", "MRI runtime dependency version is invalid")
    visible = payload.get("cuda_available")
    count = payload.get("cuda_device_count")
    memory = payload.get("cuda_total_memory_mib")
    if (type(visible) is not bool or type(count) is not int or count < 0 or count > 16
            or not isinstance(memory, list) or len(memory) != count
            or any(type(item) is not int or item <= 0 for item in memory)
            or visible != (count > 0)):
        return _fail("invalid_probe_report", "MRI runtime CUDA inventory is invalid")
    if not visible:
        return _fail("cuda_unavailable", "MRI runtime has no visible CUDA device")
    return MRIRuntimeQualificationReport(
        runtime_qualified=True,
        status_code="runtime_qualified_weights_unverified",
        message="MRI task and CUDA runtime verified; weights and execution remain unqualified",
        task_class_count=50,
        task_mapping_sha256=MRI_MAPPING_JSON_SHA256,
        totalsegmentator_version=version,
        python_version=python_version,
        cuda_device_count=count,
        cuda_total_memory_mib=tuple(memory),
        execution_ready=False,
    )


class MRIRuntimeQualifier:
    def __init__(self, *, runner: Callable[..., object] = subprocess.run,
                 timeout_seconds: float = MRI_RUNTIME_TIMEOUT_SECONDS) -> None:
        if not (0 < timeout_seconds <= 120):
            raise ValueError("MRI runtime probe timeout is invalid")
        self._runner = runner
        self._timeout = timeout_seconds

    def qualify(self, python_executable: str) -> MRIRuntimeQualificationReport:
        if (not isinstance(python_executable, str) or not python_executable.strip()
                or len(python_executable) > 4096 or any(ord(c) < 32 for c in python_executable)):
            return _fail("runtime_unavailable", "MRI runtime Python is unavailable")
        command = [python_executable, "-I", "-c", _PROBE_PROGRAM]
        try:
            result = self._runner(command, check=False, capture_output=True,
                                  text=True, timeout=self._timeout, shell=False)
        except FileNotFoundError:
            return _fail("runtime_unavailable", "MRI runtime Python is unavailable")
        except subprocess.TimeoutExpired:
            return _fail("probe_timeout", "MRI runtime qualification timed out")
        except (OSError, subprocess.SubprocessError):
            return _fail("probe_failed", "MRI runtime qualification failed")
        if getattr(result, "returncode", None) != 0:
            return _fail("probe_failed", "MRI runtime qualification failed")
        stdout = getattr(result, "stdout", None)
        if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_PROBE_BYTES:
            return _fail("invalid_probe_report", "MRI runtime probe output is invalid")
        try:
            lines = [line for line in stdout.splitlines() if line.strip()]
            return qualify_mri_runtime_payload(json.loads(lines[-1]))
        except (IndexError, json.JSONDecodeError, UnicodeError):
            return _fail("invalid_probe_report", "MRI runtime probe output is invalid")
