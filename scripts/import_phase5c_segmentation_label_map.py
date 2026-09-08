#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation import SegmentationError  # noqa: E402
from voxelatlas.segmentation_label_maps import SegmentationLabelMapService  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import one succeeded segmentation job as a canonical Patient LPS label map"
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--python", required=True, help="Qualified isolated worker Python")
    parser.add_argument(
        "--job-id",
        required=True,
        help="Exact succeeded VoxelAtlas segmentation job identity",
    )
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument(
        "--confirm-nonclinical",
        action="store_true",
        help="Confirm this is an engineering/research import, not clinical use",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print("===== PHASE 5C CANONICAL PATIENT LPS LABEL-MAP IMPORT =====")
    if not args.confirm_nonclinical:
        print("STATUS=REFUSED")
        print("MESSAGE=Pass --confirm-nonclinical to import the engineering artifact")
        return 2
    service = SegmentationLabelMapService(data_dir=args.data_dir)
    try:
        descriptor = service.import_succeeded_job(
            job_id=args.job_id,
            python_executable=args.python,
            worker_script=ROOT / "scripts" / "phase5c_label_map_worker.py",
            timeout_seconds=args.timeout_seconds,
        )
    except SegmentationError:
        print("STATUS=FAILED")
        print("MESSAGE=Canonical label-map import failed; inspect private source artifacts")
        return 1
    print("STATUS=QUALIFIED")
    print(f"LABEL_MAP_ID={descriptor['label_map_id']}")
    print(f"SEGMENTATION_JOB_ID={descriptor['segmentation_job_id']}")
    print(f"SOURCE_STUDY_ID={descriptor['source_study_id']}")
    print(f"SOURCE_VOLUME_SHA256={descriptor['source_volume_artifact_sha256']}")
    print(f"PROVIDER_MASK_SHA256={descriptor['provider_mask_sha256']}")
    print(f"CANONICAL_LABEL_MAP_SHA256={descriptor['artifact_sha256']}")
    print(f"CANONICAL_LABEL_MAP_BYTES={descriptor['artifact_bytes']}")
    print(f"SHAPE={'x'.join(str(item) for item in descriptor['shape'])}")
    print(f"DTYPE={descriptor['dtype']}")
    print(f"PRESENT_LABEL_COUNT={len(descriptor['present_labels'])}")
    print(f"NONZERO_VOXELS={descriptor['nonzero_voxels']}")
    print(f"COORDINATE_SYSTEM={descriptor['coordinate_system']}")
    print("SOURCE_TO_MODEL_TRANSFORM=PRESERVED")
    print("MODEL_TO_SOURCE_TRANSFORM=PRESERVED")
    print(f"RESAMPLED={'YES' if descriptor['resampled'] else 'NO'}")
    print("PHASE5C_CANONICAL_LABEL_MAP_OK=YES")
    print("MPR_OVERLAY=NOT_ENABLED_UNTIL_PHASE5D")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
