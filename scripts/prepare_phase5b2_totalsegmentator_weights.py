#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.totalsegmentator_execution import (  # noqa: E402
    EXPECTED_TOTAL_WEIGHT_IDS,
    SupervisedProcessRunner,
    TotalSegmentatorExecutionError,
    build_controlled_runtime_paths,
    build_weights_download_invocation,
    create_weights_manifest,
    prepare_controlled_runtime,
)
from voxelatlas.totalsegmentator_runtime import TotalSegmentatorRuntimeQualifier  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire and seal the Phase 5B2 TotalSegmentator total-task weights"
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--python", required=True, help="Qualified isolated Python executable")
    parser.add_argument(
        "--accept-download",
        action="store_true",
        help="Explicitly authorize the upstream model-weight download",
    )
    parser.add_argument("--timeout-seconds", type=float, default=21600.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print("===== PHASE 5B2 CONTROLLED WEIGHT ACQUISITION =====")
    if not args.accept_download:
        print("STATUS=REFUSED")
        print("MESSAGE=Pass --accept-download to authorize model-weight acquisition")
        return 2
    runtime = TotalSegmentatorRuntimeQualifier().qualify(args.python)
    if not runtime.qualified:
        print("STATUS=RUNTIME_NOT_QUALIFIED")
        return 1
    try:
        paths = build_controlled_runtime_paths(args.data_dir)
        prepare_controlled_runtime(paths)
        plan = build_weights_download_invocation(
            python_executable=args.python,
            paths=paths,
        )
        logs = paths.root / "acquisition-logs"
        SupervisedProcessRunner().run(
            plan.command,
            environment=plan.environment,
            working_directory=logs,
            timeout_seconds=args.timeout_seconds,
            cancellation_check=lambda: False,
            log_prefix="weights-download",
        )
        manifest = create_weights_manifest(paths)
    except TotalSegmentatorExecutionError:
        print("STATUS=FAILED")
        print("MESSAGE=Controlled model-weight acquisition failed; inspect private logs")
        return 1
    print("STATUS=QUALIFIED")
    print("TASK=total")
    print("TASK_IDS=" + ",".join(str(item) for item in EXPECTED_TOTAL_WEIGHT_IDS))
    print(f"WEIGHT_FILE_COUNT={len(manifest.files)}")
    print(f"WEIGHT_BYTES={manifest.total_bytes}")
    print(f"WEIGHTS_MANIFEST_SHA256={manifest.sha256}")
    print("MODEL_WEIGHTS=DOWNLOADED_AND_SEALED")
    print("REAL_SEGMENTATION_INFERENCE=NOT_RUN")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
