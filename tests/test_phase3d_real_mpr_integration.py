from __future__ import annotations

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
from voxelatlas.dicom_mpr import CanonicalMprService, DicomMprValidationError  # noqa: E402
from voxelatlas.passwords import hash_password  # noqa: E402


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


def write_volume(root: Path, *, modality: str = "CT") -> tuple[Path, np.ndarray]:
    study_dir = root / "studies" / "study"
    derived = study_dir / "derived"
    derived.mkdir(parents=True)
    volume = np.zeros((3, 2, 4), dtype=np.float32)
    for s in range(3):
        for r in range(2):
            for c in range(4):
                volume[s, r, c] = 100 * s + 10 * r + c
    np.save(derived / "volume.npy", volume, allow_pickle=False)
    descriptor = {
        "schema_version": 1,
        "ready": True,
        "created_at_utc": "2026-09-01T00:00:00+00:00",
        "source_series_uid": "series",
        "source_instance_count": 3,
        "modality": modality,
        "dtype": "float32",
        "shape": [3, 2, 4],
        "axis_order": ["slice", "row", "column"],
        "spacing_mm": [2.0, 1.0, 0.5],
        "origin_patient_lps_mm": [10.0, 20.0, 30.0],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 0.5, 10.0],
            [0.0, 1.0, 0.0, 20.0],
            [2.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "intensity_units": "HU" if modality == "CT" else "modality",
        "value_range": [0.0, 213.0],
        "artifact_path": "derived/volume.npy",
        "metadata_path": "derived/volume.json",
    }
    (derived / "volume.json").write_text(json.dumps(descriptor), encoding="utf-8")
    manifest = {
        "schema_version": 3,
        "study_id": "study",
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
        "series": [],
        "volume": descriptor,
    }
    (study_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return study_dir, volume


class Phase3DRealMprIntegrationTests(unittest.TestCase):
    def test_descriptor_exposes_patient_space_planes_and_conventional_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            descriptor = CanonicalMprService(data_dir=root).descriptor_latest()

            self.assertTrue(descriptor["ready"])
            self.assertEqual(descriptor["intensity_units"], "HU")
            self.assertEqual(descriptor["default_window"], {"width": 400.0, "level": 40.0})
            self.assertEqual(descriptor["crosshair_lps_mm"], [10.75, 20.5, 32.0])
            self.assertEqual(descriptor["planes"]["axial"]["slice_count"], 3)
            self.assertEqual(descriptor["planes"]["coronal"]["slice_count"], 2)
            self.assertEqual(descriptor["planes"]["sagittal"]["slice_count"], 4)
            self.assertEqual(
                descriptor["planes"]["axial"]["labels"],
                {"left": "R", "right": "L", "top": "A", "bottom": "P"},
            )
            self.assertEqual(
                descriptor["planes"]["coronal"]["labels"],
                {"left": "R", "right": "L", "top": "S", "bottom": "I"},
            )
            self.assertEqual(
                descriptor["planes"]["sagittal"]["labels"],
                {"left": "A", "right": "P", "top": "S", "bottom": "I"},
            )

    def test_axial_and_coronal_rendering_follow_patient_axes_not_instance_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            service = CanonicalMprService(data_dir=root)

            axial = service.render_latest("axial", index=1, window=256.0, level=128.0)
            self.assertEqual((axial.width, axial.height), (4, 2))
            axial_pixels = np.frombuffer(axial.pixels, dtype=np.uint8).reshape(2, 4)
            self.assertTrue(np.all(np.diff(axial_pixels[0].astype(int)) >= 0))
            self.assertGreater(int(axial_pixels[1, 0]), int(axial_pixels[0, 0]))

            coronal = service.render_latest("coronal", index=0, window=256.0, level=128.0)
            self.assertEqual((coronal.width, coronal.height), (4, 3))
            coronal_pixels = np.frombuffer(coronal.pixels, dtype=np.uint8).reshape(3, 4)
            # Coronal top is Superior, therefore slice 2 appears above slice 0.
            self.assertGreater(int(coronal_pixels[0, 0]), int(coronal_pixels[-1, 0]))


    def test_coronal_native_sampling_reformats_to_anatomical_plane_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = root / "studies" / "study"
            derived = study_dir / "derived"
            derived.mkdir(parents=True)
            volume = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
            np.save(derived / "volume.npy", volume, allow_pickle=False)
            descriptor = {
                "schema_version": 1,
                "ready": True,
                "source_series_uid": "series",
                "source_instance_count": 2,
                "modality": "CT",
                "dtype": "float32",
                "shape": [2, 3, 4],
                "axis_order": ["slice", "row", "column"],
                "spacing_mm": [2.0, 1.0, 0.5],
                "origin_patient_lps_mm": [0.0, 0.0, 0.0],
                "array_index_to_patient_lps": [
                    [0.0, 0.0, 0.5, 0.0],
                    [2.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                "intensity_units": "HU",
                "value_range": [0.0, float(volume.max())],
                "artifact_path": "derived/volume.npy",
                "metadata_path": "derived/volume.json",
            }
            (study_dir / "manifest.json").write_text(
                json.dumps({"schema_version": 3, "study_id": "study", "volume": descriptor}),
                encoding="utf-8",
            )
            mpr = CanonicalMprService(data_dir=root).descriptor_latest()
            self.assertEqual(mpr["planes"]["axial"]["slice_count"], 3)
            self.assertEqual(mpr["planes"]["coronal"]["slice_count"], 2)
            self.assertEqual(mpr["planes"]["sagittal"]["slice_count"], 4)

    def test_oblique_patient_affine_can_be_resampled_without_nonfinite_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, _ = write_volume(root)
            manifest_path = study_dir / "manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            angle = np.deg2rad(30.0)
            c, s = float(np.cos(angle)), float(np.sin(angle))
            payload["volume"]["array_index_to_patient_lps"] = [
                [0.0, -s, 0.5 * c, 10.0],
                [0.0, c, 0.5 * s, 20.0],
                [2.0, 0.0, 0.0, 30.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            service = CanonicalMprService(data_dir=root)
            descriptor = service.descriptor_latest()
            image = service.render_latest(
                "axial",
                index=int(descriptor["planes"]["axial"]["slice_count"]) // 2,
                window=400.0,
                level=40.0,
            )
            pixels = np.frombuffer(image.pixels, dtype=np.uint8)
            self.assertEqual(pixels.size, image.width * image.height)
            self.assertGreater(pixels.size, 0)

    def test_zero_or_invalid_window_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            with self.assertRaises(DicomMprValidationError):
                CanonicalMprService(data_dir=root).render_latest(
                    "axial", index=0, window=0.0, level=40.0
                )

    def test_http_mpr_endpoints_require_auth_and_return_no_store_raw_gray8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            client = TestClient(create_app(settings=make_settings(root)))

            self.assertEqual(client.get("/api/studies/latest/mpr").status_code, 401)
            login = client.post(
                "/api/auth/login",
                json={"username": "engineer", "password": "correct horse battery staple"},
            )
            self.assertEqual(login.status_code, 200)

            descriptor = client.get("/api/studies/latest/mpr")
            self.assertEqual(descriptor.status_code, 200)
            self.assertEqual(descriptor.headers["cache-control"], "no-store")
            self.assertTrue(descriptor.json()["mpr"]["ready"])

            image = client.get(
                "/api/studies/latest/mpr/axial",
                params={"index": 1, "window": 400, "level": 40},
            )
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.headers["cache-control"], "no-store")
            self.assertEqual(image.headers["content-type"], "application/x-voxelatlas-gray8")
            self.assertEqual(image.headers["x-voxelatlas-width"], "4")
            self.assertEqual(image.headers["x-voxelatlas-height"], "2")
            self.assertEqual(len(image.content), 8)

    def test_frontend_has_real_canvas_mpr_and_synchronized_navigation_contract(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")

        for canvas_id in ("mprAxialCanvas", "mprCoronalCanvas", "mprSagittalCanvas"):
            self.assertIn(canvas_id, html)
        self.assertIn("orientation-top", html)
        self.assertIn("orientation-bottom", html)
        self.assertIn('/api/studies/latest/mpr', js)
        self.assertIn("renderAllMprPlanes", js)
        self.assertIn("setMprCrosshairFromPointer", js)
        self.assertIn("adjustMprWindowLevel", js)
        self.assertIn("wheel", js)
        self.assertIn("--mpr-crosshair-x", css)
        self.assertIn("--mpr-crosshair-y", css)
        self.assertNotIn("Volume ready - MPR rendering pending", html)


if __name__ == "__main__":
    unittest.main()
