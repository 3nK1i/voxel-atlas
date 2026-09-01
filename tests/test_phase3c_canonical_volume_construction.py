from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from voxelatlas import config  # noqa: E402
from voxelatlas.app import create_app  # noqa: E402
from voxelatlas.passwords import hash_password  # noqa: E402
from voxelatlas.dicom_volume import (  # noqa: E402
    CanonicalVolumeService,
    DecodedDicomSlice,
    DicomVolumeValidationError,
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


def ready_manifest(study_id: str = "study", modality: str = "CT") -> dict[str, object]:
    return {
        "schema_version": 2,
        "study_id": study_id,
        "study_instance_uid": "1.2.3",
        "created_at_utc": "2026-09-01T00:00:00+00:00",
        "study_date": "20260901",
        "study_description": "Head CT",
        "modalities": [modality],
        "file_count": 3,
        "skipped_file_count": 0,
        "series_count": 1,
        "primary_series_uid": "series",
        "reconstruction_ready": True,
        "reconstruction_series_uid": "series",
        "series": [
            {
                "series_instance_uid": "series",
                "modality": modality,
                "series_number": 1,
                "series_description": "Head",
                "manufacturer": "Scanner",
                "manufacturer_model": "Model",
                "rows": 2,
                "columns": 3,
                "pixel_spacing": [0.5, 0.75],
                "slice_thickness": 2.0,
                "spacing_between_slices": 2.0,
                "instance_count": 3,
                "instances": [
                    {"stored_filename": name, "sop_instance_uid": name, "sha256": sha256(name.encode("ascii")).hexdigest()}
                    for name in ("instance-c.dcm", "instance-a.dcm", "instance-b.dcm")
                ],
                "geometry": {
                    "reconstruction_ready": True,
                    "orientation_label": "axial",
                    "dimensions": [2, 3, 3],
                    "spacing_mm": [0.5, 0.75, 2.0],
                    "slice_spacing_mm": 2.0,
                    "origin_patient_mm": [10.0, 20.0, 30.0],
                    "row_direction": [1.0, 0.0, 0.0],
                    "column_direction": [0.0, 1.0, 0.0],
                    "slice_normal": [0.0, 0.0, 1.0],
                    "slice_position_range_mm": [30.0, 34.0],
                    "ordered_instance_filenames": [
                        "instance-a.dcm",
                        "instance-b.dcm",
                        "instance-c.dcm",
                    ],
                    "issues": [],
                },
            }
        ],
    }


def write_study(root: Path, payload: dict[str, object]) -> Path:
    study_id = str(payload["study_id"])
    study_dir = root / "studies" / study_id
    study_dir.mkdir(parents=True)
    for name in ("instance-a.dcm", "instance-b.dcm", "instance-c.dcm"):
        (study_dir / name).write_bytes(name.encode("ascii"))
    (study_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    return study_dir


def pixel_reader(path: Path) -> DecodedDicomSlice:
    values = {
        "instance-a.dcm": 100,
        "instance-b.dcm": 200,
        "instance-c.dcm": 300,
    }
    return DecodedDicomSlice(
        pixels=np.full((2, 3), values[path.name], dtype=np.int16),
        rescale_slope=2.0,
        rescale_intercept=-1024.0,
    )


class Phase3CCanonicalVolumeConstructionTests(unittest.TestCase):
    def test_builds_float32_volume_in_geometric_order_and_persists_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = write_study(root, ready_manifest())
            service = CanonicalVolumeService(data_dir=root, pixel_reader=pixel_reader)

            public = service.build_latest()

            volume = np.load(study_dir / "derived" / "volume.npy", allow_pickle=False)
            self.assertEqual(volume.dtype, np.float32)
            self.assertEqual(volume.shape, (3, 2, 3))
            self.assertTrue(np.all(volume[0] == -824.0))
            self.assertTrue(np.all(volume[1] == -624.0))
            self.assertTrue(np.all(volume[2] == -424.0))
            self.assertTrue(public["volume_ready"])
            self.assertEqual(public["volume"]["shape"], [3, 2, 3])
            self.assertEqual(public["volume"]["axis_order"], ["slice", "row", "column"])
            self.assertFalse((study_dir / "derived" / "volume.npy.tmp").exists())

    def test_volume_metadata_uses_unambiguous_array_spacing_and_patient_lps_affine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_study(root, ready_manifest())
            volume = CanonicalVolumeService(data_dir=root, pixel_reader=pixel_reader).build_latest()["volume"]

            self.assertEqual(volume["spacing_mm"], [2.0, 0.5, 0.75])
            self.assertEqual(volume["origin_patient_lps_mm"], [10.0, 20.0, 30.0])
            self.assertEqual(
                volume["array_index_to_patient_lps"],
                [
                    [0.0, 0.0, 0.75, 10.0],
                    [0.0, 0.5, 0.0, 20.0],
                    [2.0, 0.0, 0.0, 30.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
            )

    def test_ct_rescale_is_recorded_as_hounsfield_units_and_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_study(root, ready_manifest(modality="CT"))
            volume = CanonicalVolumeService(data_dir=root, pixel_reader=pixel_reader).build_latest()["volume"]
            self.assertEqual(volume["intensity_units"], "HU")
            self.assertEqual(volume["value_range"], [-824.0, -424.0])

    def test_mr_volume_uses_modality_intensity_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_study(root, ready_manifest(modality="MR"))
            volume = CanonicalVolumeService(data_dir=root, pixel_reader=pixel_reader).build_latest()["volume"]
            self.assertEqual(volume["intensity_units"], "modality")

    def test_phase3a_legacy_manifest_builds_without_reupload_by_qualifying_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = ready_manifest()
            payload["schema_version"] = 1
            payload.pop("reconstruction_ready", None)
            payload.pop("reconstruction_series_uid", None)
            series = payload["series"][0]
            series.pop("geometry", None)
            positions = {
                "instance-a.dcm": 0.0,
                "instance-b.dcm": 2.0,
                "instance-c.dcm": 4.0,
            }
            for item in series["instances"]:
                item["instance_number"] = 99 - int(positions[item["stored_filename"]])
                item["image_position_patient"] = [10.0, 20.0, 30.0 + positions[item["stored_filename"]]]
                item["image_orientation_patient"] = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            study_dir = write_study(root, payload)

            public = CanonicalVolumeService(data_dir=root, pixel_reader=pixel_reader).build_latest()

            self.assertTrue(public["volume_ready"])
            manifest = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 3)
            self.assertTrue(manifest["reconstruction_ready"])
            self.assertEqual(
                manifest["series"][0]["geometry"]["ordered_instance_filenames"],
                ["instance-a.dcm", "instance-b.dcm", "instance-c.dcm"],
            )

    def test_build_rejects_unqualified_geometry_without_writing_derived_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = ready_manifest()
            payload["reconstruction_ready"] = False
            payload["reconstruction_series_uid"] = None
            payload["series"][0]["geometry"]["reconstruction_ready"] = False
            payload["series"][0]["geometry"]["issues"] = [
                {"code": "slice_gap_detected", "message": "gap"}
            ]
            study_dir = write_study(root, payload)
            with self.assertRaises(DicomVolumeValidationError):
                CanonicalVolumeService(data_dir=root, pixel_reader=pixel_reader).build_latest()
            self.assertFalse((study_dir / "derived").exists())

    def test_decode_shape_mismatch_does_not_publish_partial_volume(self) -> None:
        def bad_reader(path: Path) -> DecodedDicomSlice:
            del path
            return DecodedDicomSlice(np.zeros((4, 4), dtype=np.int16), 1.0, 0.0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = write_study(root, ready_manifest())
            with self.assertRaisesRegex(DicomVolumeValidationError, "pixel matrix"):
                CanonicalVolumeService(data_dir=root, pixel_reader=bad_reader).build_latest()
            manifest = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("volume", manifest)

    def test_public_manifest_exposes_volume_provenance_without_internal_artifact_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_study(root, ready_manifest())
            public = CanonicalVolumeService(data_dir=root, pixel_reader=pixel_reader).build_latest()
            encoded = json.dumps(public)
            self.assertTrue(public["volume_ready"])
            self.assertIn("source_series_uid", public["volume"])
            self.assertNotIn("volume.npy", encoded)
            self.assertNotIn("artifact_path", encoded)
            self.assertNotIn("stored_filename", encoded)

    def test_source_hash_mismatch_blocks_volume_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = write_study(root, ready_manifest())
            (study_dir / "instance-b.dcm").write_bytes(b"tampered")
            with self.assertRaisesRegex(DicomVolumeValidationError, "integrity"):
                CanonicalVolumeService(data_dir=root, pixel_reader=pixel_reader).build_latest()
            manifest = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("volume", manifest)

    def test_missing_published_artifact_is_rebuilt_instead_of_trusted(self) -> None:
        calls = {"count": 0}

        def counting_reader(path: Path) -> DecodedDicomSlice:
            calls["count"] += 1
            return pixel_reader(path)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = write_study(root, ready_manifest())
            service = CanonicalVolumeService(data_dir=root, pixel_reader=counting_reader)
            service.build_latest()
            first_calls = calls["count"]
            (study_dir / "derived" / "volume.npy").unlink()
            service.build_latest()
            self.assertGreater(calls["count"], first_calls)
            self.assertTrue((study_dir / "derived" / "volume.npy").is_file())

    def test_authenticated_volume_build_route_uses_injected_service(self) -> None:
        class FakeDicomService:
            def latest_public_study(self):
                return {"study_id": "study", "reconstruction_ready": True, "volume_ready": False}

            def ingest(self, parts):
                raise AssertionError(list(parts))

        @dataclass
        class FakeVolumeService:
            calls: int = 0

            def build_latest(self):
                self.calls += 1
                return {
                    "study_id": "study",
                    "reconstruction_ready": True,
                    "volume_ready": True,
                    "volume": {"shape": [3, 2, 3]},
                }

        fake_volume = FakeVolumeService()
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp))
            app = create_app(
                settings=settings,
                dicom_service=FakeDicomService(),
                volume_service=fake_volume,
            )
            with TestClient(app) as client:
                blocked = client.post("/api/studies/latest/volume")
                self.assertEqual(blocked.status_code, 401)
                client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                built = client.post("/api/studies/latest/volume")

            self.assertEqual(built.status_code, 200)
            self.assertTrue(built.json()["study"]["volume_ready"])
            self.assertEqual(fake_volume.calls, 1)

    def test_workspace_auto_builds_qualified_volume_and_defers_3d_patient_anatomy(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn('fetch("/api/studies/latest/volume"', js)
        self.assertIn("Patient volume ready", js)
        self.assertIn('/api/studies/latest/mpr', js)
        self.assertIn("DICOM volume not loaded", html)
        self.assertNotIn('registerLayer("volume"', js)

    def test_backend_runtime_manifest_declares_numpy_for_volume_construction(self) -> None:
        requirements = (ROOT / "requirements/backend.txt").read_text(encoding="utf-8")
        self.assertIn("numpy", requirements)


if __name__ == "__main__":
    unittest.main()
