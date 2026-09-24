"""C5D: isolated, one-shot MRI model trial entrypoint, never imported by the app.

--check is strictly read-only for study/job artifacts. --execute requires a
separately supplied explicit authorization phrase; it is NOT part of C5D
validation and must not be used before the C5E execution decision.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.mri_provider_qualification import qualify_mri_provider
from voxelatlas.mri_source_qualification import qualify_mri_stored_source
from voxelatlas.mri_worker_execution import MRIWorkerExecutor
from voxelatlas.segmentation import (
    CanonicalSegmentationSourceRepository, SegmentationDevice,
    SegmentationExecutionRequirements, SegmentationJobService,
    SegmentationModelDescriptor, SegmentationModelRegistry, discover_cuda_devices,
)
from voxelatlas.mri_job_binding import MRIStudyBoundProvider

BRANCH = "phase6-accurate-surfaces"
BASE_HEAD = "47dc027cebc0eadab284af26b7a2f3b542e95400"
MRI_PYTHON = Path.home() / "anaconda3/envs/voxelatlas-totalseg-2.18/bin/python"
BRIDGE = ROOT / "scripts/phase6j_c3a_mri_nifti_worker.py"
MIN_FREE_MIB = 4096
MIN_DISK_BYTES = 10 * (1024 ** 3)  # attempt headroom, not a successful-run guarantee
AUTHORIZATION = "AUTHORIZE-ONE-PHASE6J-C5E-MRI-FASTEST-TRIAL"


class TrialBlocked(Exception):
    """No study identifiers, file paths or patient data in public failures."""


def _git(*args: str) -> str:
    result = subprocess.run(("git", *args), cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            check=False, timeout=20)
    if result.returncode:
        raise TrialBlocked("C5D_REPOSITORY=BLOCKED")
    return result.stdout.strip()


def check_repository(*, execute: bool) -> None:
    if (_git("rev-parse", "--show-toplevel") != str(ROOT)
            or _git("branch", "--show-current") != BRANCH):
        raise TrialBlocked("C5D_REPOSITORY=BLOCKED")
    if subprocess.run(("git", "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"),
                      cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                      check=False, timeout=20).returncode:
        raise TrialBlocked("C5D_BASE_CHECKPOINT=BLOCKED")
    if execute:
        if (_git("status", "--porcelain=v1", "--untracked-files=all")
                or _git("rev-parse", "HEAD") != _git("rev-parse", f"origin/{BRANCH}")):
            raise TrialBlocked("C5D_UNCOMMITTED_OR_UNPUSHED=BLOCKED")
        remote = subprocess.run(("git", "ls-remote", "--heads", "origin", BRANCH),
                                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, check=False, timeout=30)
        if remote.returncode or remote.stdout.split("\t", 1)[0] != _git("rev-parse", "HEAD"):
            raise TrialBlocked("C5D_REMOTE_CHECKPOINT=BLOCKED")


def _preview_running() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.25)
        return connection.connect_ex(("127.0.0.1", 8011)) == 0


def _select_gpu(devices: tuple[SegmentationDevice, ...]) -> SegmentationDevice:
    matches = [device for device in devices if device.kind == "cuda" and device.index == 0]
    if len(matches) != 1:
        raise TrialBlocked("C5D_GPU=BLOCKED")
    device = matches[0]
    if ("RTX 2060" not in device.name or not isinstance(device.total_memory_mib, int)
            or device.total_memory_mib > 8192 or device.total_memory_mib < MIN_FREE_MIB
            or not isinstance(device.free_memory_mib, int)
            or device.free_memory_mib < MIN_FREE_MIB):
        raise TrialBlocked("C5D_GPU_MEMORY_OR_IDENTITY=BLOCKED")
    return device


def _no_active_jobs(data_dir: Path) -> None:
    """Do not let JobService recovery mark another live job as interrupted."""
    segmentation_root = data_dir / "segmentation"
    jobs_root = segmentation_root / "jobs"
    if segmentation_root.is_symlink() or jobs_root.is_symlink():
        raise TrialBlocked("C5D_OTHER_JOBS=BLOCKED")
    if not jobs_root.exists():
        return
    if not jobs_root.is_dir():
        raise TrialBlocked("C5D_OTHER_JOBS=BLOCKED")
    for job in jobs_root.iterdir():
        if job.is_symlink():
            raise TrialBlocked("C5D_OTHER_JOBS=BLOCKED")
        if not job.is_dir():
            continue
        manifest = job / "manifest.json"
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 64 * 1024:
            raise TrialBlocked("C5D_OTHER_JOBS=BLOCKED")
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise TrialBlocked("C5D_OTHER_JOBS=BLOCKED") from exc
        if not isinstance(payload, dict) or payload.get("state") not in {"succeeded", "failed", "cancelled"}:
            raise TrialBlocked("C5D_OTHER_JOBS=BLOCKED")


def _canonical_mri_python(python: Path) -> Path:
    """Resolve Conda's bin/python alias only to an executable in the same bin dir.

    Never pass the user-facing symlink to the supervised worker, which must
    continue to reject symlink executables. Reject broken, external, or
    non-executable targets without changing the Conda installation.
    """
    try:
        if (not isinstance(python, Path) or not python.is_absolute()
                or not python.is_file() or not os.access(python, os.X_OK)):
            raise TrialBlocked("C5D_RUNTIME_OR_PREVIEW=BLOCKED")
        parent = python.parent.resolve(strict=True)
        canonical = python.resolve(strict=True)
        if (not parent.is_dir() or canonical.parent != parent
                or canonical.is_symlink() or not canonical.is_file()
                or not os.access(canonical, os.X_OK)):
            raise TrialBlocked("C5D_RUNTIME_OR_PREVIEW=BLOCKED")
    except (OSError, RuntimeError, ValueError) as exc:
        raise TrialBlocked("C5D_RUNTIME_OR_PREVIEW=BLOCKED") from exc
    return canonical


def preflight(*, data_dir: Path, python: Path = MRI_PYTHON,
              bridge: Path = BRIDGE,
              gpu_discovery=discover_cuda_devices,
              provider_qualification=qualify_mri_provider):
    """No model execution or job creation. Return qualified immutable source/GPU."""
    if (_preview_running() or data_dir.is_symlink() or not data_dir.is_dir()
            or data_dir.resolve(strict=True) != data_dir
            or bridge.is_symlink() or not bridge.is_file()
            or bridge.resolve(strict=True) != bridge):
        raise TrialBlocked("C5D_RUNTIME_OR_PREVIEW=BLOCKED")
    effective_python = _canonical_mri_python(python)
    _no_active_jobs(data_dir)
    disk = shutil.disk_usage(data_dir)
    if disk.free < MIN_DISK_BYTES:
        raise TrialBlocked("C5D_DISK_HEADROOM=BLOCKED")
    try:
        source = CanonicalSegmentationSourceRepository(data_dir).latest()
        if source.modality != "MR" or qualify_mri_stored_source(source)[0] is not True:
            raise TrialBlocked("C5D_STORED_MRI_SOURCE=BLOCKED")
        device = _select_gpu(tuple(gpu_discovery()))
        status = provider_qualification(data_dir=data_dir, python_executable=str(effective_python), source=source)
        if (status.prerequisites_qualified is not True
                or status.execution_authorized is not False
                or status.source_qualified is not True):
            raise TrialBlocked("C5D_MODEL_PREREQUISITES=BLOCKED")
        # Fail if the source/series was altered during the slower weights probe.
        if (CanonicalSegmentationSourceRepository(data_dir).load(source.study_id) != source
                or qualify_mri_stored_source(source)[0] is not True):
            raise TrialBlocked("C5D_SOURCE_CHANGED_DURING_PREFLIGHT=BLOCKED")
    except TrialBlocked:
        raise
    except Exception as exc:
        raise TrialBlocked("C5D_QUALIFICATION=BLOCKED") from exc
    return source, device


def _descriptor() -> SegmentationModelDescriptor:
    # Local-only available descriptor; the normal app's MR descriptor stays unavailable.
    return SegmentationModelDescriptor(
        provider_id="totalsegmentator", provider_version="2.18.0",
        model_id="total_mr", model_version="2.18.0",
        display_name="Isolated one-shot MRI qualification trial",
        task="multi_structure", capabilities=("anatomical_segmentation",),
        supported_modalities=("MR",), available=True, availability_reason=None,
        execution=SegmentationExecutionRequirements(supported_devices=("cuda",)),
    )


def execute_once(*, data_dir: Path, python: Path = MRI_PYTHON,
                 bridge: Path = BRIDGE, gpu_discovery=discover_cuda_devices):
    # Advisory lock on the existing data directory: no new file or stale lock.
    # Prevents concurrent executions of THIS controlled runner, not other GPU jobs.
    handle = os.open(data_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise TrialBlocked("C5D_TRIAL_ALREADY_RUNNING=BLOCKED") from exc
        effective_python = _canonical_mri_python(python)
        source, device = preflight(data_dir=data_dir, python=python, bridge=bridge,
                                   gpu_discovery=gpu_discovery)
        # A changed interpreter alias after qualification is not authorized.
        if _canonical_mri_python(python) != effective_python:
            raise TrialBlocked("C5D_RUNTIME_OR_PREVIEW=BLOCKED")
        registry = SegmentationModelRegistry()
        # Re-discover device on job creation, then the worker probes CUDA again.
        jobs = SegmentationJobService(data_dir=data_dir, registry=registry,
                                       device_discovery=lambda: (_select_gpu(tuple(gpu_discovery())),))
        provider = MRIStudyBoundProvider(
            data_dir=data_dir, job_service=jobs, descriptor=_descriptor(),
            executor=MRIWorkerExecutor(python_executable=effective_python, bridge_script=bridge),
            execution_permission=lambda: True,  # This local process only, never app config.
        )
        registry.register_provider(provider)
        if (_preview_running() or jobs.sources.load(source.study_id) != source
                or qualify_mri_stored_source(source)[0] is not True):
            raise TrialBlocked("C5D_SOURCE_CHANGED_BEFORE_JOB=BLOCKED")
        job = jobs.create_job(provider_id="totalsegmentator", model_id="total_mr",
                              device_request="cuda:0", parameters={"mode": "fastest"},
                              source_study_id=source.study_id)
        job_id = job["job_id"]
        cancellation = threading.Event()
        finished = threading.Event()
        def request_cancel(_number, _frame):
            cancellation.set()
        def cancel_watcher():
            while not finished.is_set():
                if cancellation.wait(0.25):
                    try:
                        jobs.cancel_job(job_id)
                    except Exception:
                        pass
                    return
        previous_int = signal.signal(signal.SIGINT, request_cancel)
        previous_term = signal.signal(signal.SIGTERM, request_cancel)
        watcher = threading.Thread(target=cancel_watcher, daemon=True)
        watcher.start()
        try:
            if cancellation.is_set():
                jobs.cancel_job(job_id)
                raise TrialBlocked("C5D_TRIAL_CANCELLED=YES")
            # Single synchronous job, no retry, no second model invocation.
            try:
                result = jobs.run_job(job_id)
            except Exception:
                # run_job can raise before its provider-error handler; seal this
                # attempt as failed rather than leaving a running job behind.
                try:
                    jobs.fail_job(job_id, code="trial_failed",
                                  message="Isolated MRI trial did not complete")
                except Exception:
                    pass
                raise
            if cancellation.is_set():
                raise TrialBlocked("C5D_TRIAL_CANCELLED=YES")
            if result.get("state") != "succeeded" or result.get("outcome", {}).get("code") != "qualified_execution":
                raise TrialBlocked("C5D_TRIAL_RESULT=FAILED_OR_BLOCKED")
            return result
        finally:
            finished.set()
            signal.signal(signal.SIGINT, previous_int)
            signal.signal(signal.SIGTERM, previous_term)
            watcher.join(timeout=1.0)
    finally:
        os.close(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Isolated single MRI trial (normal app stays disabled)")
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--check", action="store_true", help="qualify prerequisites; NO inference")
    options.add_argument("--execute", action="store_true", help="one explicitly authorized model trial")
    parser.add_argument("--authorization", default=None, help="required for one explicitly authorized run")
    args = parser.parse_args(argv)
    if args.check and args.authorization is not None:
        print("C5D_AUTHORIZATION_ARGUMENT=BLOCKED")
        return 2
    if args.execute and args.authorization != AUTHORIZATION:
        print("C5D_MODEL_AUTHORIZATION=NOT_GRANTED")
        return 2
    try:
        check_repository(execute=args.execute)
        root = ROOT / "data"
        if args.check:
            preflight(data_dir=root)
            print("C5D_PREFLIGHT=PASS")
            print("C5D_MODEL_INFERENCE=NOT_RUN")
            print("C5D_STUDY_ARTIFACTS=UNCHANGED")
        else:
            execute_once(data_dir=root)
            print("C5D_ONE_SHOT_TRIAL=SUCCEEDED")
            print("C5D_RESULT_VALIDATION=WORKER_AND_STUDY_BOUND_CHECKS_PASS")
            print("C5D_CLINICAL_VALIDATION=NOT_CLAIMED")
        return 0
    except TrialBlocked as exc:
        print(str(exc))
        print("C5D_STATUS=BLOCKED")
        return 1
    except Exception:
        # Never print study IDs, full paths, model logs or exception details.
        print("C5D_STATUS=FAILED_CLOSED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
