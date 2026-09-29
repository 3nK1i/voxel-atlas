#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation import (  # noqa: E402
    CanonicalSegmentationSourceRepository,
    SegmentationError,
    SegmentationJobService,
    SegmentationModelRegistry,
    SegmentationValidationError,
)
from voxelatlas.totalsegmentator_execution import (  # noqa: E402
    TotalSegmentatorExecutionError,
    TotalSegmentatorProvider,
    build_controlled_runtime_paths,
    load_weights_manifest,
)
from voxelatlas.totalsegmentator_runtime import TotalSegmentatorRuntimeQualifier  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one bounded non-clinical Phase 5B2 TotalSegmentator qualification"
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--python", required=True, help="Qualified isolated Python executable")
    parser.add_argument(
        "--study-id",
        required=True,
        help="Exact 32-hex VoxelAtlas study identity to qualify",
    )
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--timeout-seconds", type=float, default=21600.0)
    parser.add_argument(
        "--confirm-nonclinical",
        action="store_true",
        help="Confirm this is an engineering/research qualification, not clinical use",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print("===== PHASE 5B2 REAL CT EXECUTION QUALIFICATION =====")
    if not args.confirm_nonclinical:
        print("STATUS=REFUSED")
        print("MESSAGE=Pass --confirm-nonclinical to run the engineering qualification")
        return 2
    runtime = TotalSegmentatorRuntimeQualifier().qualify(args.python)
    if not runtime.qualified:
        print("STATUS=RUNTIME_NOT_QUALIFIED")
        return 1
    try:
        source = CanonicalSegmentationSourceRepository(args.data_dir).load(args.study_id)
        if source.modality != "CT":
            raise SegmentationValidationError("Phase 5B2 requires a canonical CT volume")
        weights = load_weights_manifest(build_controlled_runtime_paths(args.data_dir))
        provider = TotalSegmentatorProvider(
            data_dir=args.data_dir,
            python_executable=args.python,
            bridge_script=ROOT / "scripts" / "phase5b2_nifti_worker.py",
            inference_timeout_seconds=args.timeout_seconds,
        )
        registry = SegmentationModelRegistry()
        registry.register_provider(provider)
        service = SegmentationJobService(data_dir=args.data_dir, registry=registry)
        job = service.create_job(
            provider_id="totalsegmentator",
            model_id="total",
            device_request=args.device,
            parameters={},
            source_study_id=source.study_id,
        )
        result = service.run_job(str(job["job_id"]))
    except (TotalSegmentatorExecutionError, SegmentationError):
        print("STATUS=FAILED")
        print("MESSAGE=Phase 5B2 qualification could not start")
        return 1
    outcome = result.get("outcome")
    if result.get("state") != "succeeded" or not isinstance(outcome, dict):
        print("STATUS=FAILED")
        print(f"JOB_ID={result.get('job_id', 'UNAVAILABLE')}")
        print("MESSAGE=Provider execution failed; inspect the private job logs")
        return 1
    print("STATUS=QUALIFIED")
    print(f"JOB_ID={result['job_id']}")
    print(f"WEIGHTS_MANIFEST_SHA256={weights.sha256}")
    print(f"MEMORY_STRATEGY={outcome['memory_strategy']}")
    print(f"MASK_NIFTI_SHA256={outcome['mask_nifti_sha256']}")
    print(f"PRESENT_LABEL_COUNT={len(outcome['present_labels'])}")
    print("FULL_RESOLUTION=YES")
    print("CUDA_ONLY=YES")
    print("REAL_SEGMENTATION_INFERENCE=RUN")
    print("PHASE5B2_EXECUTION_CONTRACT_OK=YES")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
