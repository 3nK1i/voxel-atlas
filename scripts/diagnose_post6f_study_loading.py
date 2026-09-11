#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.dicom_ingestion import DicomStudyRepository  # noqa: E402
from voxelatlas.dicom_mpr import CanonicalMprService  # noqa: E402
from voxelatlas.sample_catalog import SampleStudyCatalogService, compute_sample_payload_contract  # noqa: E402
from voxelatlas.volume_rendering import VolumeRenderingService  # noqa: E402


def timed(label: str, fn):
    started = perf_counter()
    value = fn()
    elapsed = (perf_counter() - started) * 1000.0
    print(f"{label}_MS={elapsed:.3f}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only post-6F study loading diagnostic")
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    data_dir = args.data_dir.expanduser().resolve()
    repository = DicomStudyRepository(data_dir)
    print("===== POST-6F STUDY LOADING DIAGNOSTIC =====")
    latest = timed("LATEST_STUDY_LOOKUP", repository.latest_manifest)
    if not latest:
        raise SystemExit("No stored study is available")
    timed("MPR_DESCRIPTOR", lambda: CanonicalMprService(data_dir=data_dir).descriptor_latest())
    rendering = VolumeRenderingService(data_dir=data_dir)
    descriptor = timed("VOLUME_RENDERING_INSPECT", rendering.inspect_latest)
    # Keep this diagnostic read-only: do not synthesize a missing rendering artifact.
    print("VOLUME_RENDERING_PREPARE_MS=SKIPPED_READ_ONLY")
    if descriptor.get("ready") is True:
        revision = str(descriptor.get("revision") or "")
        timed("VOLUME_RENDERING_ARTIFACT_VALIDATE", lambda: rendering.artifact_latest(revision))
        print(f"VOLUME_RENDERING_BYTES={int(descriptor.get('byte_length') or 0)}")
    else:
        print("VOLUME_RENDERING_ARTIFACT_VALIDATE_MS=SKIPPED_NOT_READY")
        print("VOLUME_RENDERING_BYTES=0")

    origin = latest.get("origin") if isinstance(latest, dict) else None
    sample_id = origin.get("sample_id") if isinstance(origin, dict) and origin.get("kind") == "sample" else None
    if isinstance(sample_id, str) and sample_id:
        sample_service = SampleStudyCatalogService(data_dir=data_dir, dicom_service=object())
        record = sample_service._record(sample_id)  # diagnostic-only use of strict installed record
        timed("SAMPLE_PAYLOAD_VERIFY", lambda: compute_sample_payload_contract(record.dicom_root))
        print(f"SAMPLE_FILE_COUNT={record.file_count}")
        print(f"SAMPLE_BYTES={record.size_bytes}")
    else:
        print("SAMPLE_PAYLOAD_VERIFY_MS=SKIPPED_NON_SAMPLE")
    print("FRONTEND_READY_STUDY_ORCHESTRATION=MPR_AND_GPU_VOLUME_PRESTARTED_IN_PARALLEL")
    print("DIAGNOSTIC_MUTATION=NO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
