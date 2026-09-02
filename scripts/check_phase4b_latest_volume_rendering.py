#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.volume_rendering import (  # noqa: E402
    VolumeRenderingError,
    VolumeRenderingService,
)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and inspect the latest real patient volume for Phase 4B."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
        help="VoxelAtlas data directory. Defaults to the repository data directory.",
    )
    args = parser.parse_args()

    try:
        service = VolumeRenderingService(data_dir=args.data_dir)
        source = service.load_latest_source()
        metadata_path = source.study_dir / "derived" / "volume.json"
        volume_before = file_sha256(source.volume_path)
        metadata_before = file_sha256(metadata_path)
        descriptor = service.prepare_latest()
        artifact_path, _ = service.artifact_latest(str(descriptor["revision"]))
        volume_unchanged = volume_before == file_sha256(source.volume_path)
        metadata_unchanged = metadata_before == file_sha256(metadata_path)
        artifact_sha256 = file_sha256(artifact_path)
    except VolumeRenderingError as exc:
        print("LATEST_VOLUME_RENDERING=FAIL")
        print(f"REASON={exc}")
        print("LATEST_VOLUME_RENDERING_RC=1")
        return 1
    except OSError as exc:
        print("LATEST_VOLUME_RENDERING=FAIL")
        print(f"REASON=Volume rendering integrity check failed: {exc}")
        print("LATEST_VOLUME_RENDERING_RC=1")
        return 1

    valid = (
        descriptor.get("ready") is True
        and volume_unchanged
        and metadata_unchanged
        and artifact_sha256 == descriptor.get("artifact_sha256")
    )
    print(f"LATEST_VOLUME_RENDERING={'READY' if valid else 'FAIL'}")
    print(f"SOURCE_MODALITY={descriptor['source_modality']}")
    print(f"SOURCE_UNITS={descriptor['source_intensity_units']}")
    print(f"SOURCE_SHAPE={descriptor['source_shape']}")
    print(f"TEXTURE_DIMENSIONS={descriptor['texture_dimensions']}")
    print(f"ENCODING={descriptor['encoding']}")
    print(f"BYTE_LENGTH={descriptor['byte_length']}")
    print(f"DECODE_OFFSET={descriptor['decode_offset']}")
    print(f"DECODE_SCALE={descriptor['decode_scale']}")
    print(f"CANONICAL_VOLUME_UNCHANGED={'YES' if volume_unchanged else 'NO'}")
    print(f"CANONICAL_METADATA_UNCHANGED={'YES' if metadata_unchanged else 'NO'}")
    print(f"ARTIFACT_SHA256={artifact_sha256}")
    print(f"REVISION={descriptor['revision']}")
    print(f"LATEST_VOLUME_RENDERING_RC={0 if valid else 1}")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
