#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_label_maps import SegmentationLabelMapService  # noqa: E402
from voxelatlas.segmentation_surfaces import (  # noqa: E402
    REFINED_SURFACE_QUALITY,
    SegmentationSurfaceService,
)
from voxelatlas.volume_rendering import VolumeRenderingService  # noqa: E402
from voxelatlas.volume_surfaces import (  # noqa: E402
    DEFAULT_CT_BONE_ISOVALUE_HU,
    VolumeSurfaceService,
)


def _runtime_executable_path(path: Path) -> Path:
    """Return an absolute runtime path without dereferencing its venv symlink."""
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify one real CT study as the immutable engineering source for the "
            "final Phase 6E Fidelity/Presentation manual closure matrix."
        )
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--surface-python", required=True, type=Path)
    parser.add_argument("--label-map-id", required=True)
    parser.add_argument(
        "--label-id",
        required=True,
        action="append",
        type=int,
        help="Segmentation label to qualify; repeat for additional structures.",
    )
    parser.add_argument("--expected-study-id")
    args = parser.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    surface_python = _runtime_executable_path(args.surface_python)
    label_ids = tuple(dict.fromkeys(args.label_id))
    if not label_ids or any(label_id <= 0 for label_id in label_ids):
        raise SystemExit("At least one positive --label-id is required")
    if not surface_python.is_file():
        raise SystemExit("Qualified surface Python is unavailable")

    volume_service = VolumeRenderingService(data_dir=data_dir)
    source = volume_service.source_latest()
    study_id = source.study_dir.name
    if args.expected_study_id and study_id != args.expected_study_id:
        raise SystemExit("Latest study does not match --expected-study-id")
    if source.modality != "CT" or source.intensity_units != "HU":
        raise SystemExit("Phase 6E-F final presentation qualification requires CT HU input")

    source_volume_before = file_sha256(source.volume_path)

    label_service = SegmentationLabelMapService(data_dir=data_dir)
    label_map = label_service.get(args.label_map_id)
    if label_map.get("state") != "ready":
        raise SystemExit("Canonical segmentation label map is not ready")
    if label_map.get("source_study_id") != study_id:
        raise SystemExit("Segmentation label map does not belong to the active CT study")
    if label_map.get("source_modality") != "CT":
        raise SystemExit("Segmentation label map is not bound to CT")
    if label_map.get("coordinate_system") != "patient_lps":
        raise SystemExit("Segmentation label map is not in Patient LPS")
    if label_map.get("clinical_validation") != "not_claimed":
        raise SystemExit("Clinical-validation boundary changed")
    if label_map.get("source_volume_artifact_sha256") != source_volume_before:
        raise SystemExit("Segmentation label map is not bound to the current canonical volume")

    label_path = data_dir / "segmentation" / "label-maps" / args.label_map_id / "labels.npy"
    if label_path.is_symlink() or not label_path.is_file():
        raise SystemExit("Canonical segmentation label-map artifact is unavailable")
    label_before = file_sha256(label_path)
    if label_before != label_map.get("artifact_sha256"):
        raise SystemExit("Canonical segmentation label-map seal does not match its artifact")

    volume_surface_service = VolumeSurfaceService(
        data_dir=data_dir,
        volume_rendering_service=volume_service,
        worker_python=str(surface_python),
        worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
    )
    direct_ct = volume_surface_service.surface_latest(
        isovalue=DEFAULT_CT_BONE_ISOVALUE_HU
    )
    if direct_ct.study_id != study_id:
        raise SystemExit("Direct CT surface study identity changed")
    if direct_ct.coordinate_system != "patient_lps":
        raise SystemExit("Direct CT surface is not in Patient LPS")
    if direct_ct.source_type != "canonical_volume":
        raise SystemExit("Direct CT surface source is not the canonical volume")
    if direct_ct.source_modality != "CT" or direct_ct.intensity_units != "HU":
        raise SystemExit("Direct CT surface modality/intensity contract changed")
    if direct_ct.isovalue != DEFAULT_CT_BONE_ISOVALUE_HU:
        raise SystemExit("Direct CT surface is not using the locked 300 HU baseline")
    if direct_ct.vertex_count <= 0 or direct_ct.triangle_count <= 0:
        raise SystemExit("Direct CT surface is empty")

    segmentation_service = SegmentationSurfaceService(
        data_dir=data_dir,
        label_map_service=label_service,
        worker_python=str(surface_python),
        worker_script=ROOT / "scripts" / "phase6a_surface_worker.py",
        refinement_worker_script=ROOT / "scripts" / "phase6b_surface_worker.py",
    )
    segmentation_descriptor = segmentation_service.descriptor_latest(
        label_map_id=args.label_map_id
    )
    if segmentation_descriptor.get("ready") is not True:
        raise SystemExit("Segmentation surface descriptor is not ready")
    if segmentation_descriptor.get("source_study_id") != study_id:
        raise SystemExit("Segmentation surface descriptor study identity changed")
    if segmentation_descriptor.get("coordinate_system") != "patient_lps":
        raise SystemExit("Segmentation surface descriptor is not in Patient LPS")
    if segmentation_descriptor.get("presentation_quality") != REFINED_SURFACE_QUALITY:
        raise SystemExit("Presentation no longer uses the qualified refined surface")

    present_labels = {int(value) for value in label_map.get("present_labels", [])}
    missing_labels = [label_id for label_id in label_ids if label_id not in present_labels]
    if missing_labels:
        raise SystemExit(
            "Requested qualification label is absent: "
            + ",".join(str(value) for value in missing_labels)
        )

    segmentation_surfaces = []
    for label_id in label_ids:
        surface = segmentation_service.surface_latest(
            label_id=label_id,
            label_map_id=args.label_map_id,
            quality=REFINED_SURFACE_QUALITY,
        )
        if surface.label_map_id != args.label_map_id or surface.label_id != label_id:
            raise SystemExit("Segmentation surface identity changed")
        if surface.quality != REFINED_SURFACE_QUALITY:
            raise SystemExit("Segmentation presentation surface is not refined")
        if surface.coordinate_system != "patient_lps":
            raise SystemExit("Segmentation surface is not in Patient LPS")
        if surface.vertex_count <= 0 or surface.triangle_count <= 0:
            raise SystemExit("Segmentation surface is empty")
        segmentation_surfaces.append(surface)

    source_volume_after = file_sha256(source.volume_path)
    label_after = file_sha256(label_path)
    if source_volume_before != source_volume_after:
        raise SystemExit("Canonical patient volume changed during qualification")
    if label_before != label_after:
        raise SystemExit("Canonical segmentation label map changed during qualification")

    print("===== PHASE 6E-F REAL-STUDY PRESENTATION SOURCE QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    print(f"SOURCE_STUDY_ID={study_id}")
    print(f"SOURCE_MODALITY={source.modality}")
    print(f"SOURCE_UNITS={source.intensity_units}")
    print("SOURCE_SHAPE=" + "x".join(str(value) for value in source.shape))
    print(f"SOURCE_VOLUME_SHA256={source_volume_before}")
    print(f"DIRECT_CT_ISOVALUE_HU={DEFAULT_CT_BONE_ISOVALUE_HU:g}")
    print(f"DIRECT_CT_SURFACE_ID={direct_ct.surface_id}")
    print(f"DIRECT_CT_PAYLOAD_SHA256={direct_ct.payload_sha256}")
    print(f"DIRECT_CT_VERTEX_COUNT={direct_ct.vertex_count}")
    print(f"DIRECT_CT_TRIANGLE_COUNT={direct_ct.triangle_count}")
    print(f"SEGMENTATION_LABEL_MAP_ID={args.label_map_id}")
    print(f"SEGMENTATION_LABEL_MAP_SHA256={label_before}")
    print("SEGMENTATION_LABEL_IDS=" + ",".join(str(value) for value in label_ids))
    print(f"SEGMENTATION_SURFACE_COUNT={len(segmentation_surfaces)}")
    for surface in segmentation_surfaces:
        prefix = f"SEGMENTATION_LABEL_{surface.label_id}"
        print(f"{prefix}_SURFACE_ID={surface.surface_id}")
        print(f"{prefix}_PAYLOAD_SHA256={surface.payload_sha256}")
        print(f"{prefix}_VERTEX_COUNT={surface.vertex_count}")
        print(f"{prefix}_TRIANGLE_COUNT={surface.triangle_count}")
    print("GEOMETRY_CHAIN=PATIENT_LPS")
    print("DIRECT_CT_BASELINE=300_HU")
    print("SEGMENTATION_PRESENTATION_QUALITY=REFINED")
    print("SOURCE_VOLUME=IMMUTABLE")
    print("SOURCE_LABEL_MAP=IMMUTABLE")
    print("FIDELITY_VISUAL_REVIEW=MANUAL_REQUIRED")
    print("PRESENTATION_VISUAL_REVIEW=MANUAL_REQUIRED")
    print("COMBINED_THREE_LAYER_VISUAL_REVIEW=MANUAL_REQUIRED")
    print("PHASE6F_ADVANCED_INTERACTION=NOT_ENABLED")
    print("PHASE6G_QUANTITATIVE_SURFACE_TO_MASK_FIDELITY=NOT_RUN")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6E_F_REAL_STUDY_QUALIFICATION_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
