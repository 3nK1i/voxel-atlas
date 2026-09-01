#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.anatomy_reconstruction import (  # noqa: E402
    AnatomyReconstructionError,
    AnatomyReconstructionService,
)


def yes_no(value: object) -> str:
    return "YES" if value is True else "NO"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect the latest canonical patient volume for Phase 4 reconstruction input readiness."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
        help="VoxelAtlas data directory. Defaults to the repository data directory.",
    )
    args = parser.parse_args()

    try:
        status = AnatomyReconstructionService(data_dir=args.data_dir).inspect_latest()
    except AnatomyReconstructionError as exc:
        print("LATEST_RECONSTRUCTION_INPUT=FAIL")
        print(f"REASON={exc}")
        print("LATEST_RECONSTRUCTION_INPUT_RC=1")
        return 1

    source = status["source_volume"]
    layers = status["layers"]
    skull = layers["skull"]
    brain = layers["brain"]

    print("LATEST_RECONSTRUCTION_INPUT=PRESENT")
    print(f"SOURCE_MODALITY={source['modality']}")
    print(f"SOURCE_UNITS={source['intensity_units']}")
    print(f"SOURCE_SHAPE={source['shape']}")
    print(f"COORDINATE_SYSTEM={status['coordinate_system']}")
    print(f"LENGTH_UNITS={status['length_units']}")
    print(f"SKULL_INPUT_ELIGIBLE={yes_no(skull['input_eligible'])}")
    print(f"SKULL_ARTIFACT_READY={yes_no(skull['artifact_ready'])}")
    print(f"BRAIN_INPUT_ELIGIBLE={yes_no(brain['input_eligible'])}")
    print(f"BRAIN_ARTIFACT_READY={yes_no(brain['artifact_ready'])}")
    print(f"COMBINED_READY={yes_no(status['combined_ready'])}")
    print("LATEST_RECONSTRUCTION_INPUT_RC=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
