#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from voxelatlas.segmentation import SegmentationJobService  # noqa: E402
from voxelatlas.segmentation_label_maps import SegmentationLabelMapService  # noqa: E402
from voxelatlas.segmentation_workflow import SegmentationWorkflowService  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Qualify Phase 6D0 explicit reuse of an existing canonical segmentation."
    )
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--label-map-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir).expanduser().resolve()
    label_map_id = str(args.label_map_id).strip().lower()

    jobs = SegmentationJobService(data_dir=data_dir)
    maps = SegmentationLabelMapService(data_dir=data_dir, job_service=jobs)
    descriptor = maps.get(label_map_id)
    latest = jobs.sources.latest()
    if descriptor.get("source_study_id") != latest.study_id:
        raise SystemExit("Requested label map is not bound to the latest study")

    artifact = data_dir / "segmentation" / "label-maps" / label_map_id / "labels.npy"
    before_sha = sha256_file(artifact)
    before_jobs = jobs.list_jobs()
    before_job_ids = tuple(str(item.get("job_id")) for item in before_jobs)

    workflow = SegmentationWorkflowService(
        data_dir=data_dir,
        job_service=jobs,
        label_map_service=maps,
        python_executable=None,
        import_worker_script=ROOT / "scripts" / "phase5c_label_map_worker.py",
    )
    before = workflow.snapshot_latest()
    requested = workflow.request_start()

    after_sha = sha256_file(artifact)
    after_jobs = jobs.list_jobs()
    after_job_ids = tuple(str(item.get("job_id")) for item in after_jobs)

    if before.get("state") != "available":
        raise SystemExit("Existing segmentation was not detected as reusable")
    if requested.workflow.get("state") != "available":
        raise SystemExit("Explicit use did not return the existing segmentation")
    if requested.workflow.get("label_map_id") != label_map_id:
        raise SystemExit("Explicit use returned a different label map")
    if requested.background_job_id is not None:
        raise SystemExit("Existing segmentation reuse attempted to schedule provider execution")
    if before_job_ids != after_job_ids:
        raise SystemExit("Existing segmentation reuse changed the segmentation job inventory")
    if before_sha != after_sha:
        raise SystemExit("Existing segmentation reuse changed the canonical label map")

    labels = descriptor.get("present_labels")
    present_count = (
        len(labels) - (1 if isinstance(labels, list) and 0 in labels else 0)
        if isinstance(labels, list)
        else 0
    )

    print("===== PHASE 6D0 REAL EXISTING-SEGMENTATION REUSE QUALIFICATION =====")
    print(f"STUDY_ID={latest.study_id}")
    print(f"LABEL_MAP_ID={label_map_id}")
    print(f"PRESENT_STRUCTURE_COUNT={present_count}")
    print(f"SEGMENTATION_JOB_COUNT_BEFORE={len(before_jobs)}")
    print(f"SEGMENTATION_JOB_COUNT_AFTER={len(after_jobs)}")
    print("PROVIDER_EXECUTION_SCHEDULED=NO")
    print("EXISTING_LABEL_MAP_REUSED=YES")
    print("SOURCE_LABEL_MAP=IMMUTABLE")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("STATUS=QUALIFIED")
    print("PHASE6D0_EXISTING_REUSE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
