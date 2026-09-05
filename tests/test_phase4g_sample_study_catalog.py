from __future__ import annotations

from dataclasses import dataclass
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
from voxelatlas.passwords import hash_password  # noqa: E402
from voxelatlas.sample_catalog import (  # noqa: E402
    SAMPLE_CATALOG_SCHEMA_VERSION,
    SampleStudyCatalogService,
    SampleStudyIntegrityError,
    compute_sample_payload_digest,
)


@dataclass
class _Descriptor:
    study_id: str = "loaded-study-id"

    def public_dict(self) -> dict[str, object]:
        return {
            "study_id": self.study_id,
            "study_description": "Catalog sample",
            "modalities": ["CT"],
            "file_count": 2,
            "series_count": 1,
            "reconstruction_ready": True,
            "volume_ready": False,
            "series": [],
        }


class _FakeDicomService:
    def __init__(self) -> None:
        self.received: list[tuple[str, bytes]] = []
        self.origin: dict[str, object] | None = None

    def ingest(self, parts):
        self.received = [
            (part.filename or "", part.file.read())
            for part in parts
        ]
        return _Descriptor()

    def annotate_study_origin(self, study_id: str, origin: dict[str, object]):
        self.origin = origin
        return _Descriptor(study_id).public_dict() | {"origin": origin}


def _settings(data_dir: Path) -> config.AppSettings:
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


def _install_sample(
    data_dir: Path,
    *,
    sample_id: str = "ct-head",
    title: str = "Head CT",
    order: int = 10,
    preview: bool = True,
) -> Path:
    root = data_dir / "sample_studies" / sample_id
    dicom = root / "dicom"
    dicom.mkdir(parents=True)
    (dicom / "slice-002.dcm").write_bytes(b"DICOM-B")
    (dicom / "slice-001.dcm").write_bytes(b"DICOM-A")
    digest, count, size_bytes = compute_sample_payload_digest(dicom)
    manifest = {
        "schema_version": SAMPLE_CATALOG_SCHEMA_VERSION,
        "sample_id": sample_id,
        "title": title,
        "summary": "Deidentified demonstration study for direct volume rendering.",
        "modality": "CT",
        "body_region": "Head",
        "source_label": "Public imaging archive",
        "source_url": "https://example.org/dataset",
        "license_label": "Source terms",
        "license_url": "https://example.org/license",
        "payload_sha256": digest,
        "file_count": count,
        "size_bytes": size_bytes,
        "order": order,
        "featured": True,
        "installed_at_utc": "2026-09-03T10:00:00+00:00",
    }
    (root / "sample.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if preview:
        (root / "preview.png").write_bytes(b"\x89PNG\r\n\x1a\npreview")
    return root


class Phase4GSampleStudyCatalogTests(unittest.TestCase):
    def test_catalog_lists_only_strict_installed_samples_without_private_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            _install_sample(data_dir, sample_id="ct-head", title="Head CT", order=20)
            _install_sample(data_dir, sample_id="ct-chest", title="Chest CT", order=10)
            invalid = data_dir / "sample_studies" / "invalid"
            invalid.mkdir(parents=True)
            (invalid / "sample.json").write_text("{}", encoding="utf-8")

            service = SampleStudyCatalogService(
                data_dir=data_dir,
                dicom_service=_FakeDicomService(),
            )
            samples = service.list_public()

            self.assertEqual([item["sample_id"] for item in samples], ["ct-chest", "ct-head"])
            self.assertTrue(samples[0]["preview_available"])
            self.assertEqual(
                samples[0]["preview_url"],
                "/api/sample-studies/ct-chest/preview",
            )
            serialized = json.dumps(samples)
            for private_marker in ("payload_sha256", "dicom", str(data_dir), "StudyInstanceUID"):
                self.assertNotIn(private_marker, serialized)

    def test_loading_reverifies_integrity_and_uses_normal_dicom_ingestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            _install_sample(data_dir)
            dicom = _FakeDicomService()
            service = SampleStudyCatalogService(data_dir=data_dir, dicom_service=dicom)

            result = service.load_sample("ct-head")

            self.assertEqual([name for name, _ in dicom.received], [
                "slice-001.dcm",
                "slice-002.dcm",
            ])
            self.assertEqual(result["study"]["study_id"], "loaded-study-id")
            self.assertEqual(result["study"]["origin"]["kind"], "sample")
            self.assertEqual(result["study"]["origin"]["sample_id"], "ct-head")
            self.assertEqual(dicom.origin["source_label"], "Public imaging archive")

    def test_tampered_sample_is_rejected_before_dicom_ingestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            root = _install_sample(data_dir)
            (root / "dicom" / "slice-001.dcm").write_bytes(b"TAMPERED")
            dicom = _FakeDicomService()
            service = SampleStudyCatalogService(data_dir=data_dir, dicom_service=dicom)

            with self.assertRaisesRegex(SampleStudyIntegrityError, "integrity"):
                service.load_sample("ct-head")
            self.assertEqual(dicom.received, [])

    def test_catalog_http_routes_are_authenticated_no_store_and_load_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            root = _install_sample(data_dir)
            sample_service = SampleStudyCatalogService(
                data_dir=data_dir,
                dicom_service=_FakeDicomService(),
            )
            with TestClient(create_app(
                settings=_settings(data_dir),
                sample_catalog_service=sample_service,
            )) as client:
                self.assertEqual(client.get("/api/sample-studies").status_code, 401)
                self.assertEqual(client.post("/api/sample-studies/ct-head/load").status_code, 401)
                client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                catalog = client.get("/api/sample-studies")
                loaded = client.post("/api/sample-studies/ct-head/load")
                preview = client.get("/api/sample-studies/ct-head/preview")

            self.assertEqual(catalog.status_code, 200)
            self.assertEqual(catalog.headers["cache-control"], "no-store")
            self.assertEqual(catalog.json()["samples"][0]["sample_id"], "ct-head")
            self.assertEqual(loaded.status_code, 201)
            self.assertEqual(loaded.headers["cache-control"], "no-store")
            self.assertEqual(loaded.json()["study"]["origin"]["kind"], "sample")
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.headers["cache-control"], "no-store")
            self.assertEqual(preview.headers["x-content-type-options"], "nosniff")
            self.assertEqual(preview.content, (root / "preview.png").read_bytes())

    def test_installer_requires_explicit_public_deidentified_confirmation(self) -> None:
        installer = (ROOT / "scripts/install_phase4g_sample_study.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "--confirm-public-deidentified",
            "--source-url",
            "--license-url",
            "compute_sample_payload_digest",
            "sample.json",
            "preview.png",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, installer)

    def test_workspace_has_a_single_polished_access_point_and_truthful_states(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
        client = (ROOT / "web/js/sample-study-catalog.js").read_text(encoding="utf-8")

        for marker in (
            'id="sampleCatalogButton"',
            'id="sampleCatalogDialog"',
            'id="sampleCatalogGrid"',
            'id="sampleCatalogEmpty"',
            'id="sampleCatalogProgress"',
            "Explore Sample Studies",
            "Demonstration data",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

        for marker in (
            "SampleStudyCatalogClient",
            "renderSampleCatalog",
            "openSampleCatalog",
            "requestSampleLoad",
            "confirmSampleReplacement",
            "ensureCanonicalVolume",
            "sample-study-card",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, app + css + client)

        self.assertNotIn("sample DICOM", html.lower())
        self.assertNotIn("diagnostic", client.lower())

    def test_phase4g_cache_and_validation_entrypoints_are_present(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn('/css/styles.css?v=phase3d-r21-phase4h6', html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h6', html)
        self.assertIn(
            'from "./sample-study-catalog.js?v=phase4g-r1"',
            app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4g_checks.sh").is_file())
        self.assertTrue((ROOT / "scripts/check_phase4g_sample_catalog.mjs").is_file())


if __name__ == "__main__":
    unittest.main()
