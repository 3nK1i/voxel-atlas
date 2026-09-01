#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"PASS {message}")


def main() -> int:
    print("===== PHASE 3A DICOM INGESTION FOUNDATION =====")

    try:
        import pydicom  # noqa: F401
    except Exception as exc:
        print(f"FAIL backend_dependency=pydicom import_error={exc}")
        print("PHASE3A_DICOM_INGESTION_OK=NO")
        return 1

    version = importlib.metadata.version("pydicom")
    print(f"PASS backend_dependency=pydicom version={version}")

    ingestion = (ROOT / "backend/voxelatlas/dicom_ingestion.py").read_text(encoding="utf-8")
    app = (ROOT / "backend/voxelatlas/app.py").read_text(encoding="utf-8")
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    require("stop_before_pixels=True" in ingestion, "dicom_parse=metadata_only")
    require('SUPPORTED_MODALITIES = {"CT", "MR"}' in ingestion, "modality_scope=ct_mr")
    require('stage.replace(final_dir)' in ingestion, "storage=staged_then_promoted")
    require('"/api/studies/dicom"' in app, "http=authenticated_upload_endpoint")
    require('"/api/studies/latest"' in app, "http=latest_study_endpoint")
    require('id="dicomFileInput"' in html and "webkitdirectory" in html, "ui=folder_selection")
    require('fetch("/api/studies/dicom"' in js, "ui=real_upload_request")
    require('fetch("/api/studies/latest"' in js, "ui=study_restore")
    require("data/" in gitignore and "*.dcm" in gitignore, "raw_data=git_ignored")
    require("PatientName" not in ingestion and "PatientID" not in ingestion, "canonical_metadata=no_patient_identity_duplication")

    print("PHASE3A_DICOM_INGESTION_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
