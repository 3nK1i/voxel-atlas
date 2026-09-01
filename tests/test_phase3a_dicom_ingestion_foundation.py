from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from voxelatlas import config  # noqa: E402
from voxelatlas.app import create_app  # noqa: E402
from voxelatlas.dicom_ingestion import (  # noqa: E402
    DicomHeader,
    DicomIngestionService,
    DicomSeriesDescriptor,
    DicomStudyDescriptor,
    DicomStudyValidationError,
    DicomUploadLimitExceeded,
)
from voxelatlas.passwords import hash_password  # noqa: E402


class Part:
    def __init__(self, name: str, payload: bytes):
        self.filename = name
        self.file = BytesIO(payload)


def fake_header_reader(path: Path) -> DicomHeader | None:
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("INVALID"):
        return None
    fields = raw.split("|")
    if len(fields) < 6:
        return None
    study, series, sop, modality, instance, description = fields[:6]
    return DicomHeader(
        study_instance_uid=study,
        series_instance_uid=series,
        sop_instance_uid=sop,
        modality=modality,
        study_date="20260901",
        study_description="Head study",
        series_number=1 if series.endswith("A") else 2,
        series_description=description,
        manufacturer="Voxel Scanner",
        manufacturer_model="VS-1",
        rows=512,
        columns=512,
        pixel_spacing=(0.5, 0.5),
        slice_thickness=0.6,
        spacing_between_slices=0.6,
        instance_number=int(instance),
        image_position_patient=(0.0, 0.0, float(instance)),
        image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
    )


def make_settings(data_dir: Path) -> config.AppSettings:
    return config.AppSettings(
        environment="test",
        session_secret="x" * 48,
        secure_cookies=False,
        session_cookie_name="voxelatlas_session",
        allowed_hosts=("testserver", "127.0.0.1", "localhost"),
        data_dir=data_dir,
        max_upload_mib=512,
        auth_username="engineer",
        auth_password_hash=hash_password("correct horse battery staple"),
        session_ttl_minutes=60,
    )


class FakeHTTPDicomService:
    def __init__(self, study: DicomStudyDescriptor):
        self.study = study
        self.received_count = 0

    def latest_public_study(self):
        return self.study.public_dict()

    def ingest(self, parts):
        items = list(parts)
        self.received_count = len(items)
        return self.study


class Phase3ADicomIngestionFoundationTests(unittest.TestCase):
    def test_ingestion_groups_one_study_into_multiple_series_and_persists_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DicomIngestionService(
                data_dir=Path(tmp),
                max_upload_mib=8,
                header_reader=fake_header_reader,
            )
            descriptor = service.ingest(
                [
                    Part("patient-name-001.dcm", b"study1|seriesA|sop1|CT|1|Head thin"),
                    Part("patient-name-002.dcm", b"study1|seriesA|sop2|CT|2|Head thin"),
                    Part("scout.dcm", b"study1|seriesB|sop3|CT|1|Scout"),
                    Part("notes.txt", b"INVALID not dicom"),
                ]
            )

            self.assertEqual(descriptor.study_instance_uid, "study1")
            self.assertEqual(descriptor.file_count, 3)
            self.assertEqual(descriptor.skipped_file_count, 1)
            self.assertEqual(descriptor.series_count, 2)
            self.assertEqual(descriptor.primary_series_uid, "seriesA")
            self.assertEqual(descriptor.modalities, ("CT",))

            study_dir = Path(tmp) / "studies" / descriptor.study_id
            manifest = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(len(list(study_dir.glob("instance-*.dcm"))), 3)
            self.assertNotIn("patient-name", json.dumps(manifest))
            self.assertNotIn("PatientName", json.dumps(manifest))
            self.assertNotIn("PatientID", json.dumps(manifest))

    def test_ingestion_rejects_mixed_studies_and_removes_staging_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = DicomIngestionService(
                data_dir=root,
                max_upload_mib=8,
                header_reader=fake_header_reader,
            )
            with self.assertRaisesRegex(DicomStudyValidationError, "more than one DICOM study"):
                service.ingest(
                    [
                        Part("a.dcm", b"study1|seriesA|sop1|CT|1|Head"),
                        Part("b.dcm", b"study2|seriesA|sop2|CT|2|Head"),
                    ]
                )
            staging = root / ".staging"
            self.assertEqual(list(staging.iterdir()), [])
            self.assertEqual(list((root / "studies").iterdir()), [])

    def test_ingestion_rejects_duplicate_sop_instance_uid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DicomIngestionService(
                data_dir=Path(tmp),
                max_upload_mib=8,
                header_reader=fake_header_reader,
            )
            with self.assertRaisesRegex(DicomStudyValidationError, "Duplicate SOP Instance UID"):
                service.ingest(
                    [
                        Part("a.dcm", b"study1|seriesA|same-sop|CT|1|Head"),
                        Part("b.dcm", b"study1|seriesA|same-sop|CT|2|Head"),
                    ]
                )

    def test_ingestion_enforces_configured_total_upload_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DicomIngestionService(
                data_dir=Path(tmp),
                max_upload_mib=1,
                header_reader=fake_header_reader,
            )
            with self.assertRaises(DicomUploadLimitExceeded):
                service.ingest([Part("large.dcm", b"x" * (1024 * 1024 + 1))])

    def test_latest_study_restores_public_metadata_without_instance_paths_or_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DicomIngestionService(
                data_dir=Path(tmp),
                max_upload_mib=8,
                header_reader=fake_header_reader,
            )
            descriptor = service.ingest(
                [Part("a.dcm", b"study1|seriesA|sop1|MR|1|T1")]
            )
            latest = service.latest_public_study()
            self.assertIsNotNone(latest)
            self.assertEqual(latest["study_id"], descriptor.study_id)
            serialized = json.dumps(latest)
            self.assertNotIn("stored_filename", serialized)
            self.assertNotIn("sha256", serialized)

    def test_authenticated_http_upload_and_latest_routes_use_injected_ingestion_service(self) -> None:
        study = DicomStudyDescriptor(
            schema_version=1,
            study_id="study-public-id",
            study_instance_uid="1.2.3",
            created_at_utc="2026-09-01T09:00:00+00:00",
            study_date="20260901",
            study_description="Head CT",
            modalities=("CT",),
            file_count=2,
            skipped_file_count=0,
            series_count=1,
            primary_series_uid="4.5.6",
            series=(
                DicomSeriesDescriptor(
                    series_instance_uid="4.5.6",
                    modality="CT",
                    series_number=1,
                    series_description="Head thin",
                    manufacturer="Scanner",
                    manufacturer_model="Model",
                    rows=512,
                    columns=512,
                    pixel_spacing=(0.5, 0.5),
                    slice_thickness=0.6,
                    spacing_between_slices=0.6,
                    instance_count=2,
                    instances=(),
                ),
            ),
        )
        fake = FakeHTTPDicomService(study)
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp))
            with TestClient(create_app(settings=settings, dicom_service=fake)) as client:
                unauthenticated = client.post(
                    "/api/studies/dicom",
                    files=[("files", ("a.dcm", b"abc", "application/dicom"))],
                )
                self.assertEqual(unauthenticated.status_code, 401)

                login = client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                self.assertEqual(login.status_code, 200)

                uploaded = client.post(
                    "/api/studies/dicom",
                    files=[
                        ("files", ("a.dcm", b"abc", "application/dicom")),
                        ("files", ("b.dcm", b"def", "application/dicom")),
                    ],
                )
                latest = client.get("/api/studies/latest")

            self.assertEqual(uploaded.status_code, 201)
            self.assertEqual(uploaded.json()["study"]["study_id"], "study-public-id")
            self.assertEqual(fake.received_count, 2)
            self.assertEqual(latest.status_code, 200)
            self.assertEqual(latest.json()["study"]["series_count"], 1)

    def test_backend_manifest_declares_metadata_only_dicom_parser(self) -> None:
        requirements = (ROOT / "requirements/backend.txt").read_text(encoding="utf-8")
        ingestion = (ROOT / "backend/voxelatlas/dicom_ingestion.py").read_text(encoding="utf-8")
        self.assertIn("pydicom", requirements)
        self.assertIn("stop_before_pixels=True", ingestion)
        self.assertIn("force=False", ingestion)
        self.assertNotIn("PixelData", ingestion)

    def test_workspace_enables_real_folder_upload_and_updates_study_metadata(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn('id="uploadDicomButton"', html)
        self.assertIn('id="dicomFileInput"', html)
        self.assertIn("webkitdirectory", html)
        self.assertNotIn('id="uploadDicomButton"\n              class="upload-button"\n              type="button"\n              disabled', html)
        self.assertIn('fetch("/api/studies/dicom"', js)
        self.assertIn('fetch("/api/studies/latest"', js)
        self.assertIn('formData.append("files"', js)
        self.assertIn("applyStudy(payload.study)", js)
        self.assertIn("DICOM series discovered", js)

    def test_phase3a_does_not_fake_reconstruction_or_mpr_output(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn("DICOM volume not loaded", html)
        self.assertIn("DICOM ready - reconstruction pending", js)
        self.assertIn("Demo skull - patient reconstruction pending", js)
        self.assertNotIn("registerLayer(\"brain\"", js)
        self.assertNotIn("registerLayer(\"volume\"", js)


if __name__ == "__main__":
    unittest.main()
