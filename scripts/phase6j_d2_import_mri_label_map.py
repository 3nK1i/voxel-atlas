#!/usr/bin/env python3
"""One qualified existing MRI mask -> canonical map; never executes a model."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.mri_label_map_import import QualifiedMRIResultImporter  # noqa: E402
from voxelatlas.segmentation import SegmentationJobService  # noqa: E402
from voxelatlas.segmentation_label_maps import SegmentationLabelMapService  # noqa: E402

BRANCH = "phase6-accurate-surfaces"
BASE = "3d9e7561ed0fa146e9ad2123ead3b1915498f719"
PYTHON = Path.home() / "anaconda3/envs/voxelatlas-totalseg-2.18/bin/python"
WORKER = ROOT / "scripts/phase5c_label_map_worker.py"
CONFIRMATION = "IMPORT-EXISTING-ACCEPTED-MRI-MASK-NO-INFERENCE"


class Blocked(Exception):
    pass


def _git(*args: str) -> str:
    result = subprocess.run(("git", *args), cwd=ROOT, check=False,
                            capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise Blocked("repository")
    return result.stdout.strip()


def _no_active_jobs(data: Path) -> None:
    jobs = data / "segmentation" / "jobs"
    if jobs.is_symlink() or (jobs.exists() and not jobs.is_dir()):
        raise Blocked("jobs")
    if not jobs.exists():
        raise Blocked("jobs")
    for directory in jobs.iterdir():
        if directory.is_symlink():
            raise Blocked("jobs")
        if not directory.is_dir():
            continue
        manifest = directory / "manifest.json"
        if (manifest.is_symlink() or not manifest.is_file()
                or manifest.stat().st_size > 65536):
            raise Blocked("jobs")
        try:
            job = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise Blocked("jobs") from exc
        if not isinstance(job, dict) or job.get("state") not in {"succeeded", "failed", "cancelled"}:
            raise Blocked("jobs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D2: qualify/import one existing MRI mask; no inference")
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--check", action="store_true", help="read-only qualification")
    options.add_argument("--import", dest="do_import", action="store_true", help="explicit canonical label-map import")
    parser.add_argument("--confirmation", help="required only for explicit import")
    args = parser.parse_args(argv)
    if (args.check and args.confirmation is not None) or (args.do_import and args.confirmation != CONFIRMATION):
        print("D2_IMPORT_AUTHORIZATION=BLOCKED")
        return 2
    try:
        if (_git("rev-parse", "--show-toplevel") != str(ROOT)
                or _git("branch", "--show-current") != BRANCH
                or subprocess.run(("git", "merge-base", "--is-ancestor", BASE, "HEAD"),
                                  cwd=ROOT, check=False, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL).returncode):
            raise Blocked("repository")
        if args.do_import:
            if (_git("status", "--porcelain=v1", "--untracked-files=all")
                    or _git("rev-parse", "HEAD") != _git("rev-parse", f"origin/{BRANCH}")):
                raise Blocked("repository")
            remote = subprocess.run(("git", "ls-remote", "--heads", "origin", BRANCH),
                                    cwd=ROOT, capture_output=True, text=True, check=False, timeout=30)
            if remote.returncode or remote.stdout.split("\t", 1)[0] != _git("rev-parse", "HEAD"):
                raise Blocked("remote")
        data = ROOT / "data"
        if data.is_symlink() or not data.is_dir() or data.resolve(strict=True) != data:
            raise Blocked("data")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.25)
            if connection.connect_ex(("127.0.0.1", 8011)) == 0:
                raise Blocked("preview")
        handle = os.open(data, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Blocked("concurrent trial or import") from exc
            _no_active_jobs(data)  # Crucial: JobService's constructor may recover live jobs.
            jobs = SegmentationJobService(data_dir=data)
            maps = SegmentationLabelMapService(data_dir=data, job_service=jobs)
            importer = QualifiedMRIResultImporter(data_dir=data, jobs=jobs, label_maps=maps)
            source, job = importer.qualify()
            if args.check:
                print("D2_EXISTING_MRI_JOB_QUALIFICATION=PASS")
                print("D2_MODEL_INFERENCE=NOT_RUN")
                print("D2_IMPORT_NOT_PERFORMED=YES")
                return 0
            if (PYTHON.parent.resolve(strict=True) != PYTHON.resolve(strict=True).parent
                    or not PYTHON.is_file() or not os.access(PYTHON, os.X_OK)
                    or not WORKER.is_file() or WORKER.is_symlink()):
                raise Blocked("worker")
            descriptor = importer.import_current(
                python_executable=str(PYTHON.resolve(strict=True)), worker_script=WORKER,
            )
            if descriptor.get("source_study_id") != source.study_id or descriptor.get("segmentation_job_id") != job["job_id"]:
                raise Blocked("result")
            print("D2_CANONICAL_MRI_LABEL_MAP=PASS")
            print("D2_PATIENT_LPS_AND_LABEL_CONTRACT=PASS")
            print("D2_MODEL_INFERENCE=NOT_RUN")
            print("D2_CLINICAL_VALIDATION=NOT_CLAIMED")
            return 0
        finally:
            os.close(handle)
    except Exception:  # No patient IDs, paths, private logs or model details on stdout.
        print("D2_STATUS=BLOCKED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
