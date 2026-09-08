#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.totalsegmentator_runtime import (  # noqa: E402
    PINNED_TOTALSEGMENTATOR_VERSION,
    TotalSegmentatorRuntimeQualifier,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Non-mutating Phase 5B1 qualification of an isolated "
            "TotalSegmentator runtime. No model weights are downloaded and no inference runs."
        )
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable belonging to the isolated TotalSegmentator environment",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the bounded machine-readable qualification report",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = TotalSegmentatorRuntimeQualifier().qualify(args.python)
    payload = report.public_dict()

    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print("===== PHASE 5B1 TOTALSEGMENTATOR RUNTIME QUALIFICATION =====")
        print(f"PINNED_TOTALSEGMENTATOR_VERSION={PINNED_TOTALSEGMENTATOR_VERSION}")
        print(f"STATUS_CODE={report.status_code}")
        print(f"STATUS_MESSAGE={report.message}")
        print(f"PYTHON_VERSION={report.python_version or 'UNAVAILABLE'}")
        print(
            "TOTALSEGMENTATOR_VERSION="
            f"{report.totalsegmentator_version or 'UNAVAILABLE'}"
        )
        print(f"TORCH_VERSION={report.torch_version or 'UNAVAILABLE'}")
        print(f"NNUNETV2_VERSION={report.nnunetv2_version or 'UNAVAILABLE'}")
        print(f"TASK={report.task or 'UNAVAILABLE'}")
        print(f"TASK_MODALITY={report.task_modality or 'UNAVAILABLE'}")
        print(
            "TASK_CLASS_COUNT="
            f"{report.task_class_count if report.task_class_count is not None else 'UNAVAILABLE'}"
        )
        print(f"TASK_DEFINITION_SHA256={report.task_definition_sha256 or 'UNAVAILABLE'}")
        print(
            "CUDA_DEVICE_COUNT="
            f"{report.cuda_device_count if report.cuda_device_count is not None else 'UNAVAILABLE'}"
        )
        for device in report.cuda_devices:
            print(
                f"CUDA_DEVICE_{device.index}="
                f"{device.name}|{device.total_memory_mib}MiB"
            )
        print(f"PHASE5B1_RUNTIME_CONTRACT_OK={'YES' if report.qualified else 'NO'}")
        print("MODEL_WEIGHTS=NOT_DOWNLOADED")
        print("REAL_SEGMENTATION_INFERENCE=NOT_RUN")
        print("CLINICAL_VALIDATION=NOT_CLAIMED")
    return 0 if report.qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
