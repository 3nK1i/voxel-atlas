#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.dicom_ingestion import DicomIngestionService  # noqa: E402
from voxelatlas.sample_catalog import SampleStudyCatalogService  # noqa: E402
from voxelatlas.segmentation import SegmentationJobService  # noqa: E402
from voxelatlas.segmentation_label_maps import SegmentationLabelMapService  # noqa: E402


def build_service(data_dir: Path) -> tuple[SampleStudyCatalogService, SegmentationLabelMapService]:
    dicom = DicomIngestionService(data_dir=data_dir, max_upload_mib=4096)
    jobs = SegmentationJobService(data_dir=data_dir)
    maps = SegmentationLabelMapService(data_dir=data_dir, job_service=jobs)
    return SampleStudyCatalogService(
        data_dir=data_dir,
        dicom_service=dicom,
        label_map_service=maps,
    ), maps


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify idempotent sample-study activation")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--list", action="store_true", help="List installed sample IDs and exit")
    parser.add_argument("--sample-id")
    parser.add_argument("--label-map-id")
    args = parser.parse_args()
    service, maps = build_service(args.data_dir)
    if args.list:
        print("===== INSTALLED SAMPLE STUDIES =====")
        for sample in service.list_public():
            print(f"SAMPLE_ID={sample['sample_id']}|TITLE={sample['title']}")
        return 0
    if not args.sample_id or not args.label_map_id:
        parser.error("--sample-id and --label-map-id are required unless --list is used")
    label_map = maps.get(args.label_map_id)
    result = service.load_sample(args.sample_id)
    study = result["study"]
    if study.get("study_id") != label_map.get("source_study_id"):
        raise SystemExit("Activated study does not own the canonical label map")
    if result.get("reused") is not True:
        raise SystemExit("Installed sample was re-ingested instead of reused")
    print("===== PHASE 5F2 SAMPLE STUDY IDENTITY QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    print(f"SAMPLE_ID={args.sample_id}")
    print(f"ACTIVATED_STUDY_ID={study['study_id']}")
    print(f"LABEL_MAP_SOURCE_STUDY_ID={label_map['source_study_id']}")
    print(f"LABEL_MAP_ID={args.label_map_id}")
    print("SAMPLE_REUSED=YES")
    print("STUDY_BINDING=PASS")
    print("CROSS_STUDY_LABEL_REUSE=NOT_ENABLED")
    print("PHASE5F2_SAMPLE_IDENTITY_CORRECTION_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
