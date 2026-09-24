"""6J-C3B: isolated MR-only supervised executor; no provider registration.

Model execution is NEVER initiated by import, qualification, or normal app startup.
A future C4 job adapter must supply a study-bound source and an explicit authorization;
C5 separately qualifies real MRI inference and hardware requirements.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
from typing import Callable

from .mri_runtime_qualification import MRIRuntimeQualifier, MRI_MAPPING_JSON_SHA256
from .mri_task_contract import TOTAL_SEGMENTATOR_MRI_STRUCTURES
from .mri_weights_qualification import (MRIAssetError, MRIAssetPaths, mri_environment,
                                        paths_for, qualify_installed_mri_mapping,
                                        verify_mri_weights)
from .totalsegmentator_execution import (ProcessExecutionError, SupervisedProcessRunner)

TASK = "total_mr"
VERSION = "2.18.0"
SCHEMA = 1
MAX_REPORT_BYTES = 128 * 1024
MAX_JOB_SECONDS = 6 * 60 * 60
CUDA_ATTEMPT_FREE_MIB = 4096  # preflight only; does not qualify model memory use
LOW_MEMORY_TOTAL_MIB = 8192
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_JOB = re.compile(r"[A-Za-z0-9_-]{8,80}\Z")


class MRIWorkerError(ValueError):
    """Generic, non-patient-specific execution failure."""


@dataclass(frozen=True)
class MRIWorkerRequest:
    data_dir: Path
    job_id: str
    source_npy: Path
    source_descriptor: Path
    source_sha256: str
    descriptor_sha256: str
    device_index: int
    mode: str = "fastest"


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing_private_file(path: Path, data_dir: Path) -> None:
    if (not isinstance(path, Path) or not path.is_absolute() or path.is_symlink()
            or not path.is_file() or not path.is_relative_to(data_dir)):
        raise MRIWorkerError("Canonical MR input is unavailable or unsafe")
    cursor = path.parent
    while cursor != data_dir:
        if cursor.is_symlink() or not cursor.is_dir():
            raise MRIWorkerError("Canonical MR input path is unsafe")
        cursor = cursor.parent
    if data_dir.is_symlink():
        raise MRIWorkerError("MRI data root is unsafe")


def _require_request(request: MRIWorkerRequest) -> tuple[dict[str, object], tuple[int, int, int]]:
    if not isinstance(request, MRIWorkerRequest):
        raise MRIWorkerError("MRI worker request is invalid")
    if (not isinstance(request.data_dir, Path) or not request.data_dir.is_absolute()
            or request.data_dir.is_symlink() or not request.data_dir.is_dir()
            or not isinstance(request.job_id, str) or not _JOB.fullmatch(request.job_id)
            or type(request.device_index) is not int or request.device_index < 0 or request.device_index > 15
            or request.mode not in {"default", "fast", "fastest"}
            or not isinstance(request.source_sha256, str) or not _SHA.fullmatch(request.source_sha256)
            or not isinstance(request.descriptor_sha256, str) or not _SHA.fullmatch(request.descriptor_sha256)):
        raise MRIWorkerError("MRI worker request is invalid")
    data_dir = request.data_dir.resolve(strict=True)
    if request.data_dir != data_dir or request.source_npy != request.source_npy.resolve(strict=True) or request.source_descriptor != request.source_descriptor.resolve(strict=True):
        raise MRIWorkerError("MRI source path is not canonical")
    _existing_private_file(request.source_npy, data_dir)
    _existing_private_file(request.source_descriptor, data_dir)
    if _hash(request.source_npy) != request.source_sha256:
        raise MRIWorkerError("Canonical MR source changed")
    if request.source_descriptor.stat().st_size > 1024 * 1024:
        raise MRIWorkerError("Canonical MR descriptor is invalid")
    try:
        descriptor = json.loads(request.source_descriptor.read_text(encoding="utf-8"))
        from_json = json.dumps(descriptor, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")
        shape = descriptor["shape"]
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise MRIWorkerError("Canonical MR descriptor is invalid") from exc
    if (type(descriptor) is not dict or descriptor.get("ready") is not True
            or descriptor.get("modality") != "MR" or descriptor.get("dtype") != "float32"
            or descriptor.get("axis_order") != ["slice", "row", "column"]
            or not isinstance(shape, list) or len(shape) != 3
            or any(type(n) is not int or n <= 0 for n in shape)
            or sha256(from_json).hexdigest() != request.descriptor_sha256):
        raise MRIWorkerError("Canonical MR source qualification changed")
    return descriptor, tuple(shape)


def mri_command(*, python_executable: Path, input_nifti: Path, mask_nifti: Path,
                report_json: Path, device_index: int, mode: str) -> tuple[str, ...]:
    """Build task-pinned CLI; never reuses the CT `total` command builder."""
    if (not isinstance(python_executable, Path) or not python_executable.is_absolute()
            or python_executable.is_symlink() or not python_executable.is_file()
            or not os.access(python_executable, os.X_OK)
            or type(device_index) is not int or not 0 <= device_index <= 15
            or mode not in {"default", "fast", "fastest"}):
        raise MRIWorkerError("MRI invocation configuration is invalid")
    paths = (input_nifti, mask_nifti, report_json)
    if (any(not isinstance(p, Path) or not p.is_absolute() or p.is_symlink() for p in paths)
            or len(set(paths)) != 3 or not str(input_nifti).endswith(".nii.gz")
            or not str(mask_nifti).endswith(".nii.gz") or report_json.suffix != ".json"):
        raise MRIWorkerError("MRI invocation paths are invalid")
    base = (str(python_executable), "-I", "-m", "totalsegmentator.bin.TotalSegmentator",
            "-i", str(input_nifti), "-o", str(mask_nifti), "--task", TASK,
            "--ml", "--device", f"gpu:{device_index}", "--report", str(report_json))
    return base + (() if mode == "default" else ("--fast",) if mode == "fast" else ("--fastest",))


def _read_report(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_REPORT_BYTES:
        raise MRIWorkerError("MRI worker report is unavailable")
    try:
        # TotalSegmentator --report writes an indented JSON object. Parse the
        # entire bounded file, never just the final line or an appended object.
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise MRIWorkerError("MRI worker report is invalid") from exc
    if type(result) is not dict:
        raise MRIWorkerError("MRI worker report is invalid")
    return result


def _valid_export(report: dict[str, object], request: MRIWorkerRequest,
                  expected_shape: tuple[int, int, int], input_path: Path) -> None:
    if (report.get("schema_version") != SCHEMA or report.get("operation") != "export"
            or report.get("task") != TASK or report.get("modality") != "MR"
            or report.get("shape") != list(expected_shape)
            or report.get("source_artifact_sha256") != request.source_sha256
            or report.get("source_descriptor_sha256") != request.descriptor_sha256
            or report.get("dtype") != "float32"
            or report.get("axis_order") != ["slice", "row", "column"]
            or not isinstance(report.get("output_nifti_sha256"), str)
            or not _SHA.fullmatch(report["output_nifti_sha256"])
            or input_path.is_symlink() or not input_path.is_file()
            or _hash(input_path) != report["output_nifti_sha256"]):
        raise MRIWorkerError("MRI NIfTI export provenance is invalid")


def _valid_provider(report: dict[str, object], input_path: Path, mask_path: Path,
                    mode: str) -> None:
    classes = report.get("classes")
    expected_classes = {str(k): v for k, v in TOTAL_SEGMENTATOR_MRI_STRUCTURES.items()}
    elapsed = report.get("runtime_seconds")
    if (report.get("totalsegmentator_version") != VERSION or report.get("task") != TASK
            or report.get("modality") != "MR" or report.get("device") != "gpu"
            or report.get("multilabel") is not True or report.get("output_type") != "nifti"
            or report.get("roi_subset") is not None
            or report.get("input") != str(input_path) or report.get("output") != str(mask_path)
            or report.get("num_classes") != 50 or classes != expected_classes
            or report.get("fast") is not (mode == "fast")
            or report.get("fastest") is not (mode == "fastest")
            or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
        raise MRIWorkerError("MRI model execution report is inconsistent")


def _valid_inspection(report: dict[str, object], expected_shape: tuple[int, int, int],
                      input_path: Path, mask_path: Path) -> None:
    labels = report.get("present_labels")
    if (report.get("schema_version") != SCHEMA or report.get("operation") != "inspect"
            or report.get("task") != TASK or report.get("modality") != "MR"
            or report.get("shape") != list(expected_shape)
            or report.get("affine_matches_input") is not True or report.get("integer_labels") is not True
            or report.get("input_nifti_sha256") != _hash(input_path)
            or report.get("mask_nifti_sha256") != _hash(mask_path)
            or type(report.get("nonzero_voxels")) is not int or report["nonzero_voxels"] <= 0
            or not isinstance(labels, list) or not labels
            or labels != sorted(set(labels))
            or any(type(x) is not int or x < 0 or x > 50 for x in labels)
            or type(report.get("minimum_label")) is not int
            or type(report.get("maximum_label")) is not int
            or labels[0] != report["minimum_label"] or labels[-1] != report["maximum_label"]):
        raise MRIWorkerError("MRI segmentation mask qualification failed")


_CUDA_PROBE = r'''
import json
import torch
import sys
idx = int(sys.argv[1])
if not torch.cuda.is_available() or not 0 <= idx < torch.cuda.device_count():
    raise SystemExit(2)
torch.cuda.set_device(idx)
free, total = torch.cuda.mem_get_info(idx)
probe = torch.ones((256, 256), device=f"cuda:{idx}")
checksum = float((probe * probe).sum().item())
print(json.dumps({"schema": 1, "index": idx, "total_mib": total // (1024*1024),
 "free_mib": free // (1024*1024), "test_sum": checksum}, separators=(",", ":")))
'''.strip()


class MRIWorkerExecutor:
    """No app/job/UI binding: invoke only with explicit C5-controlled authorization."""

    def __init__(self, *, python_executable: Path, bridge_script: Path,
                 process_runner: SupervisedProcessRunner | None = None,
                 runtime_check: Callable[[str], bool] | None = None,
                 weights_check: Callable[[MRIAssetPaths], dict[str, object]] = verify_mri_weights,
                 installed_mapping_check: Callable[[str], bool] = qualify_installed_mri_mapping,
                 max_inference_seconds: float = MAX_JOB_SECONDS) -> None:
        if (not isinstance(python_executable, Path) or not python_executable.is_absolute()
                or python_executable.is_symlink() or not python_executable.is_file()
                or not os.access(python_executable, os.X_OK)
                or not isinstance(bridge_script, Path) or not bridge_script.is_absolute()
                or bridge_script.is_symlink() or not bridge_script.is_file()
                or type(max_inference_seconds) not in (int, float)
                or not 0 < max_inference_seconds <= MAX_JOB_SECONDS):
            raise MRIWorkerError("MRI worker runtime configuration is invalid")
        self.python = python_executable
        self.bridge = bridge_script
        self.runner = process_runner or SupervisedProcessRunner()
        self.runtime_check = runtime_check or (lambda p: MRIRuntimeQualifier().qualify(p).runtime_qualified)
        self.weights_check = weights_check
        self.installed_mapping_check = installed_mapping_check
        self.max_inference_seconds = float(max_inference_seconds)

    def execute(self, request: MRIWorkerRequest, *, cancellation_check: Callable[[], bool],
                explicit_model_authorization: bool = False) -> dict[str, object]:
        if explicit_model_authorization is not True:
            raise MRIWorkerError("MRI model execution is not authorized")
        if not callable(cancellation_check) or cancellation_check():
            raise MRIWorkerError("MRI execution was cancelled")
        _, shape = _require_request(request)
        paths = paths_for(request.data_dir)
        if (not self.runtime_check(str(self.python)) or
                not self.installed_mapping_check(str(self.python))):
            raise MRIWorkerError("MRI runtime or task mapping is unqualified")
        try:
            sealed = self.weights_check(paths)
        except (MRIAssetError, OSError, ValueError) as exc:
            raise MRIWorkerError("MRI model assets are unqualified") from exc
        if (type(sealed) is not dict or sealed.get("task") != TASK
                or not isinstance(sealed.get("manifest_sha256"), str)
                or not _SHA.fullmatch(sealed["manifest_sha256"])
                or sealed.get("mode_ids") != {"default": [850, 851], "fast": [852], "fastest": [853]}):
            raise MRIWorkerError("MRI model asset identity changed")
        workspace = request.data_dir / "segmentation" / "jobs" / request.job_id / "provider" / "totalsegmentator-mri"
        # Reject existing workspace, symlinks and path substitutions, including empty prior runs.
        cursor = workspace.parent
        while cursor != request.data_dir:
            if cursor.is_symlink() or (cursor.exists() and not cursor.is_dir()):
                raise MRIWorkerError("MRI worker directory is unsafe")
            cursor = cursor.parent
        if workspace.exists() or workspace.is_symlink():
            raise MRIWorkerError("MRI worker workspace already exists")
        workspace.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(workspace, 0o700)
        for child in ("input", "output", "logs"):
            target = workspace / child
            target.mkdir(mode=0o700)
        inputs = workspace / "input" / "canonical-mri.nii.gz"
        mask = workspace / "output" / "labels.nii.gz"
        report_file = workspace / "output" / "provider-report.json"
        environment = mri_environment(paths)
        # Constrain worker to one selected GPU; upstream selector stays gpu:0.
        environment["CUDA_VISIBLE_DEVICES"] = str(request.device_index)
        def stage(command: tuple[str, ...], name: str, timeout: float = 1800., *, report_stdout: bool = True) -> dict[str, object]:
            try:
                result = self.runner.run(command, environment=environment,
                                         working_directory=workspace / "logs",
                                         timeout_seconds=timeout,
                                         cancellation_check=cancellation_check,
                                         log_prefix=name, max_log_bytes=128*1024 if name != "model" else 8*1024*1024)
                return _read_report(result.stdout_path) if report_stdout else {}
            except ProcessExecutionError as exc:
                raise MRIWorkerError("MRI worker " + ("cancelled" if exc.code == "cancelled" else "process failed")) from exc
        cuda = stage((str(self.python), "-I", "-c", _CUDA_PROBE, "0"), "cuda", 120.)
        if (cuda.get("schema") != 1 or cuda.get("index") != 0
                or type(cuda.get("free_mib")) is not int
                or type(cuda.get("total_mib")) is not int
                or type(cuda.get("test_sum")) not in (int, float)
                or not math.isfinite(cuda["test_sum"]) or cuda["test_sum"] <= 0
                or cuda["free_mib"] < CUDA_ATTEMPT_FREE_MIB
                or cuda["total_mib"] < CUDA_ATTEMPT_FREE_MIB):
            raise MRIWorkerError("MRI GPU preflight did not meet minimum attempt conditions")
        if cuda["total_mib"] <= LOW_MEMORY_TOTAL_MIB and request.mode != "fastest":
            raise MRIWorkerError("MRI low-memory GPU requires the 6 mm trial mode")
        exported = stage((str(self.python), "-I", str(self.bridge), "export", "--source-npy",
                          str(request.source_npy), "--metadata-json", str(request.source_descriptor),
                          "--output-nifti", str(inputs)), "export")
        _valid_export(exported, request, shape, inputs)
        if _hash(request.source_npy) != request.source_sha256:
            raise MRIWorkerError("Canonical MR source changed after export")
        command = mri_command(python_executable=self.python, input_nifti=inputs,
                              mask_nifti=mask, report_json=report_file,
                              device_index=0, mode=request.mode)
        stage(command, "model", self.max_inference_seconds, report_stdout=False)
        if mask.is_symlink() or not mask.is_file() or mask.stat().st_size <= 0:
            raise MRIWorkerError("MRI segmentation model output is unavailable")
        _valid_provider(_read_report(report_file), inputs, mask, request.mode)
        inspected = stage((str(self.python), "-I", str(self.bridge), "inspect", "--input-nifti",
                           str(inputs), "--mask-nifti", str(mask)), "inspect")
        _valid_inspection(inspected, shape, inputs, mask)
        if cancellation_check():
            raise MRIWorkerError("MRI execution was cancelled")
        # Caller may persist this only after independent C4 study/job binding checks.
        return {"schema": 1, "task": TASK, "modality": "MR", "mode": request.mode,
                "model_version": VERSION, "model_mapping_sha256": MRI_MAPPING_JSON_SHA256,
                "weights_manifest_sha256": sealed["manifest_sha256"],
                "input_nifti_sha256": _hash(inputs), "mask_nifti_sha256": _hash(mask),
                "mask_artifact": "provider/totalsegmentator-mri/output/labels.nii.gz",
                "nonzero_voxels": inspected["nonzero_voxels"],
                "present_labels": inspected["present_labels"],
                "cuda": {"selected_index": request.device_index,
                         "free_mib_at_start": cuda["free_mib"], "total_mib": cuda["total_mib"]},
                "clinical_validation": "not_claimed"}
