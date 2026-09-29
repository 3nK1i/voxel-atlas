#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_surface_runtime import (  # noqa: E402
    SegmentationSurfaceRuntimeQualifier,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify the isolated Phase 6A accurate-surface Python runtime"
    )
    parser.add_argument(
        "--python",
        default=os.environ.get("VOXELATLAS_SURFACE_PYTHON"),
        help="Python executable for the isolated Phase 6A surface environment",
    )
    args = parser.parse_args()

    report = SegmentationSurfaceRuntimeQualifier().qualify(args.python)
    print("===== PHASE 6A SURFACE RUNTIME =====")
    print(f"STATUS_CODE={report.status_code}")
    print(f"QUALIFIED={'YES' if report.qualified else 'NO'}")
    if report.python_version is not None:
        print(f"PYTHON_VERSION={report.python_version}")
    if report.numpy_version is not None:
        print(f"NUMPY_VERSION={report.numpy_version}")
    if report.scikit_image_version is not None:
        print(f"SCIKIT_IMAGE_VERSION={report.scikit_image_version}")
    if report.runtime_fingerprint_sha256 is not None:
        print(f"RUNTIME_FINGERPRINT_SHA256={report.runtime_fingerprint_sha256}")
    print(f"MESSAGE={report.message}")
    print(f"PHASE6A_SURFACE_RUNTIME_OK={'YES' if report.qualified else 'NO'}")
    return 0 if report.qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
