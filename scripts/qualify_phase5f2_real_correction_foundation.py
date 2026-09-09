#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_corrections import SegmentationCorrectionService  # noqa: E402
from voxelatlas.segmentation_label_maps import SegmentationLabelMapService  # noqa: E402


def file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify Phase 5F2 against a real canonical label map")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--label-map-id", required=True)
    parser.add_argument("--label-id", type=int, default=91)
    args = parser.parse_args()

    maps = SegmentationLabelMapService(data_dir=args.data_dir)
    descriptor = maps.get(args.label_map_id)
    artifact = args.data_dir / "segmentation" / "label-maps" / args.label_map_id / "labels.npy"
    before = file_digest(artifact)
    if before != descriptor["artifact_sha256"]:
        raise SystemExit("Canonical label-map artifact seal does not match")

    shape = np.asarray(descriptor["shape"], dtype=np.float64)
    affine = np.asarray(descriptor["array_index_to_patient_lps"], dtype=np.float64)
    center = affine @ np.asarray([*((shape - 1.0) / 2.0), 1.0])
    service = SegmentationCorrectionService(data_dir=args.data_dir, label_map_service=maps)
    quality = service.quality_report(label_map_id=args.label_map_id, label_id=args.label_id)
    session = service.create(args.label_map_id)
    session = service.add_action(
        session["session_id"],
        kind="review",
        label_id=args.label_id,
        center_lps_mm=center[:3].tolist(),
        radius_mm=3.0,
        plane="axial",
    )
    undone = service.undo(session["session_id"])
    redone = service.redo(session["session_id"])
    discarded = service.discard(session["session_id"])
    after = file_digest(artifact)
    if before != after or before != redone["label_map_sha256"]:
        raise SystemExit("Canonical label map changed during correction qualification")

    print("===== PHASE 5F2 REAL MANUAL CORRECTION FOUNDATION QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    print(f"SESSION_ID={session['session_id']}")
    print(f"LABEL_MAP_ID={args.label_map_id}")
    print(f"LABEL_MAP_SHA256={before}")
    print(f"LABEL_ID={args.label_id}")
    print(f"QUALITY_WARNING_COUNT={quality['warning_count']}")
    print(f"ACTION_COUNT={session['action_count']}")
    print(f"UNDO_APPLIED_COUNT={undone['applied_action_count']}")
    print(f"REDO_APPLIED_COUNT={redone['applied_action_count']}")
    print(f"FINAL_SESSION_STATE={discarded['state']}")
    print("SOURCE_LABEL_MAP=IMMUTABLE")
    print("CORRECTION_MATERIALIZATION=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE5F2_CORRECTION_FOUNDATION_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
