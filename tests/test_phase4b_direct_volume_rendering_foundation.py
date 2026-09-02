from __future__ import annotations

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

from voxelatlas.volume_rendering import (  # noqa: E402
    VolumeRenderingService,
    VolumeRenderingValidationError,
)


def write_volume(
    root: Path,
    *,
    modality: str = "CT",
    values: np.ndarray | None = None,
) -> tuple[Path, np.ndarray]:
    study_dir = root / "studies" / "study"
    derived = study_dir / "derived"
    derived.mkdir(parents=True)
    volume = (
        np.asarray(values, dtype=np.float32)
        if values is not None
        else np.asarray(
            [
                [[-1024.0, -500.0, 0.0, 400.0], [40.0, 120.0, 800.0, 1594.0]],
                [[-900.0, -250.0, 10.0, 350.0], [60.0, 200.0, 1000.0, 1450.0]],
            ],
            dtype=np.float32,
        )
    )
    np.save(derived / "volume.npy", volume, allow_pickle=False)
    descriptor = {
        "schema_version": 1,
        "ready": True,
        "created_at_utc": "2026-09-01T00:00:00+00:00",
        "source_series_uid": "series",
        "source_instance_count": int(volume.shape[0]),
        "modality": modality,
        "dtype": "float32",
        "shape": list(volume.shape),
        "axis_order": ["slice", "row", "column"],
        "spacing_mm": [2.0, 0.5, 0.75],
        "origin_patient_lps_mm": [10.0, 20.0, 30.0],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 0.75, 10.0],
            [0.0, 0.5, 0.0, 20.0],
            [2.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "intensity_units": "HU" if modality == "CT" else "modality",
        "value_range": [float(volume.min()), float(volume.max())],
        "artifact_path": "derived/volume.npy",
        "metadata_path": "derived/volume.json",
    }
    (derived / "volume.json").write_text(
        json.dumps(descriptor, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 3,
        "study_id": "study",
        "study_instance_uid": "1.2.3",
        "created_at_utc": "2026-09-01T00:00:00+00:00",
        "modalities": [modality],
        "reconstruction_ready": True,
        "reconstruction_series_uid": "series",
        "series": [],
        "volume": descriptor,
    }
    (study_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return study_dir, volume


class Phase4BDirectVolumeRenderingCoreTests(unittest.TestCase):
    def test_builds_rg8_volume_without_altering_canonical_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, volume = write_volume(root)
            canonical_path = study_dir / "derived" / "volume.npy"
            metadata_path = study_dir / "derived" / "volume.json"
            canonical_before = sha256(canonical_path.read_bytes()).hexdigest()
            metadata_before = sha256(metadata_path.read_bytes()).hexdigest()

            service = VolumeRenderingService(data_dir=root)
            descriptor = service.prepare_latest()
            artifact_path, stored = service.artifact_latest(descriptor["revision"])
            packed = np.frombuffer(artifact_path.read_bytes(), dtype=np.uint8).reshape(-1, 2)
            quantized = packed[:, 0].astype(np.uint16) + (
                packed[:, 1].astype(np.uint16) << np.uint16(8)
            )
            decoded = (
                descriptor["decode_offset"]
                + descriptor["decode_scale"] * quantized.astype(np.float64)
            ).reshape(volume.shape)
            canonical_after = sha256(canonical_path.read_bytes()).hexdigest()
            metadata_after = sha256(metadata_path.read_bytes()).hexdigest()

        self.assertEqual(canonical_before, canonical_after)
        self.assertEqual(metadata_before, metadata_after)
        self.assertEqual(descriptor["source_shape"], [2, 2, 4])
        self.assertEqual(descriptor["texture_dimensions"], [4, 2, 2])
        self.assertEqual(descriptor["texture_axis_order"], ["column", "row", "slice"])
        self.assertEqual(descriptor["encoding"], "linear_uint16_rg8")
        self.assertEqual(descriptor["source_modality"], "CT")
        self.assertEqual(descriptor["source_intensity_units"], "HU")
        self.assertEqual(descriptor["byte_length"], volume.size * 2)
        self.assertEqual(
            descriptor["texture_coordinate_to_patient_lps"],
            [
                [3.0, 0.0, 0.0, 9.625],
                [0.0, 1.0, 0.0, 19.75],
                [0.0, 0.0, 4.0, 29.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        )
        self.assertEqual(
            descriptor["patient_bounds_lps_mm"],
            [9.625, 19.75, 29.0, 12.625, 20.75, 33.0],
        )
        self.assertEqual(stored.revision, descriptor["revision"])
        self.assertLessEqual(
            float(np.max(np.abs(decoded - volume))),
            float(descriptor["decode_scale"]) / 2.0 + 1e-6,
        )
        self.assertNotIn("artifact_path", descriptor)
        self.assertNotIn(str(study_dir), json.dumps(descriptor))

    def test_preserves_mr_modality_semantics_and_patient_lps_affine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(
                root,
                modality="MR",
                values=np.linspace(12.5, 901.25, 24, dtype=np.float32).reshape(2, 3, 4),
            )
            descriptor = VolumeRenderingService(data_dir=root).prepare_latest()

        self.assertEqual(descriptor["source_modality"], "MR")
        self.assertEqual(descriptor["source_intensity_units"], "modality")
        self.assertNotEqual(descriptor["source_intensity_units"], "HU")
        self.assertEqual(
            descriptor["array_index_to_patient_lps"],
            [
                [0.0, 0.0, 0.75, 10.0],
                [0.0, 0.5, 0.0, 20.0],
                [2.0, 0.0, 0.0, 30.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        )

    def test_constant_volume_has_a_stable_lossless_decode_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, volume = write_volume(
                root,
                values=np.full((2, 3, 4), 42.5, dtype=np.float32),
            )
            service = VolumeRenderingService(data_dir=root)
            descriptor = service.prepare_latest()
            artifact_path, _ = service.artifact_latest(descriptor["revision"])
            encoded = artifact_path.read_bytes()

        self.assertEqual(descriptor["decode_offset"], 42.5)
        self.assertEqual(descriptor["decode_scale"], 1.0)
        self.assertEqual(encoded, bytes(volume.size * 2))
        self.assertNotIn(str(study_dir), json.dumps(descriptor))

    def test_oblique_source_orientation_is_preserved_in_texture_transform(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, _ = write_volume(root)
            manifest_path = study_dir / "manifest.json"
            metadata_path = study_dir / "derived" / "volume.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            affine = [
                [0.0, -0.5, 0.0, 10.0],
                [0.0, 0.0, 0.75, 20.0],
                [2.0, 0.0, 0.0, 30.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
            manifest["volume"]["array_index_to_patient_lps"] = affine
            metadata_path.write_text(
                json.dumps(manifest["volume"], indent=2, sort_keys=True),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            descriptor = VolumeRenderingService(data_dir=root).prepare_latest()

        self.assertEqual(descriptor["array_index_to_patient_lps"], affine)
        self.assertEqual(
            descriptor["texture_coordinate_to_patient_lps"],
            [
                [0.0, -1.0, 0.0, 10.25],
                [3.0, 0.0, 0.0, 19.625],
                [0.0, 0.0, 4.0, 29.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        )
        self.assertEqual(
            descriptor["patient_bounds_lps_mm"],
            [9.25, 19.625, 29.0, 10.25, 22.625, 33.0],
        )

    def test_revision_binding_rejects_stale_binary_after_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, _ = write_volume(root)
            service = VolumeRenderingService(data_dir=root)
            first = service.prepare_latest()

            manifest_path = study_dir / "manifest.json"
            metadata_path = study_dir / "derived" / "volume.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["volume"]["created_at_utc"] = "2026-09-01T01:00:00+00:00"
            metadata_path.write_text(
                json.dumps(manifest["volume"], indent=2, sort_keys=True),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(VolumeRenderingValidationError, "revision"):
                service.artifact_latest(first["revision"])
            second = service.prepare_latest()

        self.assertNotEqual(first["revision"], second["revision"])

    def test_refuses_a_rendering_artifact_above_the_configured_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            with self.assertRaisesRegex(VolumeRenderingValidationError, "too large"):
                VolumeRenderingService(data_dir=root, max_rendering_bytes=8).prepare_latest()

    def test_corrupted_derived_artifact_is_not_served_as_patient_volume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            service = VolumeRenderingService(data_dir=root)
            descriptor = service.prepare_latest()
            artifact_path, _ = service.artifact_latest(descriptor["revision"])
            artifact_path.write_bytes(artifact_path.read_bytes() + b"corrupt")

            status = service.inspect_latest()
            with self.assertRaisesRegex(VolumeRenderingValidationError, "revision"):
                service.artifact_latest(descriptor["revision"])
            repaired = service.prepare_latest()
            repaired_path, _ = service.artifact_latest(repaired["revision"])
            repaired_length = len(repaired_path.read_bytes())

        self.assertFalse(status["ready"])
        self.assertEqual(repaired["revision"], descriptor["revision"])
        self.assertEqual(repaired_length, repaired["byte_length"])

    def test_rejects_source_values_that_do_not_match_canonical_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, _ = write_volume(root)
            manifest_path = study_dir / "manifest.json"
            metadata_path = study_dir / "derived" / "volume.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["volume"]["value_range"] = [-1024.0, 2000.0]
            metadata_path.write_text(
                json.dumps(manifest["volume"], indent=2, sort_keys=True),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(VolumeRenderingValidationError, "value range"):
                VolumeRenderingService(data_dir=root).prepare_latest()

            output_dir = study_dir / "derived" / "volume_rendering"
            leftovers = list(output_dir.glob("*.tmp")) if output_dir.exists() else []
            stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(leftovers, [])
        self.assertNotIn("volume_rendering", stored_manifest)


class Phase4BDirectVolumeRenderingHttpTests(unittest.TestCase):
    def test_http_contract_is_authenticated_revision_bound_and_no_store(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from voxelatlas import config
            from voxelatlas.app import create_app
            from voxelatlas.passwords import hash_password
        except ModuleNotFoundError as exc:  # pragma: no cover - workstation dependency profile
            self.skipTest(f"HTTP test dependencies unavailable: {exc}")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, volume = write_volume(root)
            settings = config.AppSettings(
                environment="test",
                session_secret="x" * 48,
                secure_cookies=False,
                session_cookie_name="voxelatlas_session",
                allowed_hosts=("testserver", "127.0.0.1", "localhost"),
                data_dir=root,
                max_upload_mib=512,
                auth_username="engineer",
                auth_password_hash=hash_password("correct horse battery staple"),
                session_ttl_minutes=60,
            )
            with TestClient(create_app(settings=settings)) as client:
                denied = client.get("/api/studies/latest/volume-rendering")
                self.assertEqual(denied.status_code, 401)
                client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                prepared = client.post("/api/studies/latest/volume-rendering")
                descriptor = client.get("/api/studies/latest/volume-rendering")
                revision = prepared.json()["volume_rendering"]["revision"]
                binary = client.get(
                    "/api/studies/latest/volume-rendering/data",
                    params={"revision": revision},
                )
                stale = client.get(
                    "/api/studies/latest/volume-rendering/data",
                    params={"revision": "0" * 64},
                )

        self.assertEqual(prepared.status_code, 200)
        self.assertEqual(descriptor.status_code, 200)
        self.assertEqual(binary.status_code, 200)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(prepared.headers["cache-control"], "no-store")
        self.assertEqual(descriptor.headers["cache-control"], "no-store")
        self.assertEqual(binary.headers["cache-control"], "no-store")
        self.assertEqual(binary.headers["x-content-type-options"], "nosniff")
        self.assertEqual(binary.headers["x-voxelatlas-volume-revision"], revision)
        self.assertEqual(binary.headers["content-type"], "application/x-voxelatlas-volume-rg8")
        self.assertEqual(len(binary.content), volume.size * 2)
        self.assertNotIn("artifact_path", descriptor.text)
        self.assertNotIn("/tmp/", descriptor.text)


class Phase4BDirectVolumeRenderingFrontendContractTests(unittest.TestCase):
    def test_frontend_qualifies_webgl2_without_enabling_unimplemented_volume_layer(self) -> None:
        capabilities = (ROOT / "web" / "js" / "volume-rendering-capabilities.js").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn("MAX_3D_TEXTURE_SIZE", capabilities)
        self.assertIn("WebGL2RenderingContext", capabilities)
        self.assertIn("qualifyVolumeRenderingCapabilities", app_js)
        self.assertIn('data-layer="volume" disabled', html)
        self.assertNotIn("sampler3D", app_js)

    def test_frontend_finishes_mpr_status_and_uses_supported_three_timer(self) -> None:
        app_js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn("Patient volume and synchronized MPR ready.", app_js)
        self.assertEqual(app_js.count("setPatientVolumeReadyStatus();"), 2)
        self.assertIn("const timer = new THREE.Timer();", app_js)
        self.assertIn("timer.connect(document);", app_js)
        self.assertIn("timer.update(timestamp);", app_js)
        self.assertNotIn("new THREE.Clock()", app_js)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4', html)


if __name__ == "__main__":
    unittest.main()
