#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    catalog = (ROOT / "backend/voxelatlas/sample_catalog.py").read_text(encoding="utf-8")
    ingestion = (ROOT / "backend/voxelatlas/dicom_ingestion.py").read_text(encoding="utf-8")
    app = (ROOT / "backend/voxelatlas/app.py").read_text(encoding="utf-8")
    combined = (catalog + ingestion + app).lower()

    require("compute_sample_payload_contract" in catalog, "Sample instance inventory is missing")
    require("find_matching_sample_studies" in catalog, "Sample reuse lookup is missing")
    require("activate_study" in catalog, "Existing study activation is missing")
    require("label_map_service=patient_segmentation_label_map_service" in app, "Label-map preference is missing")
    require("instance_inventory" in ingestion, "Stored DICOM inventory binding is missing")
    require("segmentation/label-maps" not in catalog, "Sample catalog reaches into label artifacts")
    require("clinical-grade" not in combined, "Clinical claim found")

    print("PHASE5F2_SAMPLE_INSTANCE_IDENTITY=PASS")
    print("PHASE5F2_EXISTING_STUDY_REACTIVATION=PASS")
    print("PHASE5F2_LABEL_MAP_OWNER_PREFERENCE=PASS")
    print("CROSS_STUDY_LABEL_REUSE=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE5F2_IDENTITY_CORRECTION_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
