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

from fastapi.testclient import TestClient  # noqa: E402

from voxelatlas import config  # noqa: E402
from voxelatlas.anatomy_reconstruction import (  # noqa: E402
    AnatomyReconstructionService,
    AnatomyReconstructionValidationError,
)
from voxelatlas.app import create_app  # noqa: E402
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


def write_volume(root: Path, *, modality: str = "CT") -> Path:
    study_dir = root / "studies" / "study"
    derived = study_dir / "derived"
    derived.mkdir(parents=True)
    volume = np.arange(24, dtype=np.float32).reshape(2, 3, 4)
    np.save(derived / "volume.npy", volume, allow_pickle=False)
    descriptor = {
        "schema_version": 1,
        "ready": True,
        "created_at_utc": "2026-09-01T00:00:00+00:00",
        "source_series_uid": "series",
        "source_instance_count": 2,
        "modality": modality,
        "dtype": "float32",
        "shape": [2, 3, 4],
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
    return study_dir


def tetrahedron() -> tuple[np.ndarray, np.ndarray]:
    vertices = np.array(
        [
            [10.0, 20.0, 30.0],
            [11.0, 20.0, 30.0],
            [10.0, 21.0, 30.0],
            [10.0, 20.0, 31.0],
        ],
        dtype=np.float32,
    )
    faces = np.array(
        [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]],
        dtype=np.int32,
    )
    return vertices, faces


class Phase4AAnatomicalReconstructionFoundationTests(unittest.TestCase):
    def test_ct_volume_is_skull_eligible_without_faking_ready_anatomy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root, modality="CT")
            status = AnatomyReconstructionService(data_dir=root).inspect_latest()

        self.assertEqual(status["coordinate_system"], "patient_lps")
        self.assertEqual(status["length_units"], "mm")
        self.assertTrue(status["layers"]["skull"]["input_eligible"])
        self.assertEqual(status["layers"]["skull"]["state"], "eligible")
        self.assertFalse(status["layers"]["skull"]["artifact_ready"])
        self.assertFalse(status["layers"]["brain"]["input_eligible"])
        self.assertFalse(status["combined_ready"])

    def test_mr_volume_is_brain_eligible_and_does_not_claim_skull(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root, modality="MR")
            status = AnatomyReconstructionService(data_dir=root).inspect_latest()

        self.assertTrue(status["layers"]["brain"]["input_eligible"])
        self.assertEqual(status["layers"]["brain"]["state"], "eligible")
        self.assertFalse(status["layers"]["skull"]["input_eligible"])
        self.assertFalse(status["layers"]["brain"]["artifact_ready"])

    def test_publish_preserves_patient_lps_mm_and_records_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = write_volume(root, modality="CT")
            service = AnatomyReconstructionService(data_dir=root)
            vertices, faces = tetrahedron()
            descriptor = service.publish_layer_latest(
                layer="skull",
                vertices_lps_mm=vertices,
                faces=faces,
                algorithm="phase4a-test",
                algorithm_version="1",
                parameters={"threshold_hu": 300},
            )
            artifact = study_dir / descriptor.artifact_path
            stored = np.load(artifact, allow_pickle=False)
            stored_vertices = stored["vertices_lps_mm"].copy()
            stored_faces = stored["faces"].copy()
            artifact_digest = sha256(artifact.read_bytes()).hexdigest()
            manifest = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
            status = service.inspect_latest()

        self.assertTrue(np.array_equal(stored_vertices, vertices))
        self.assertTrue(np.array_equal(stored_faces, faces))
        self.assertEqual(descriptor.coordinate_system, "patient_lps")
        self.assertEqual(descriptor.length_units, "mm")
        self.assertEqual(descriptor.vertex_count, 4)
        self.assertEqual(descriptor.triangle_count, 4)
        self.assertEqual(descriptor.bounds_patient_lps_mm, (10.0, 20.0, 30.0, 11.0, 21.0, 31.0))
        self.assertEqual(artifact_digest, descriptor.artifact_sha256)
        self.assertEqual(manifest["schema_version"], 4)
        self.assertTrue(status["layers"]["skull"]["artifact_ready"])
        self.assertEqual(status["layers"]["skull"]["state"], "ready")
        self.assertNotIn("artifact_path", status["layers"]["skull"]["artifact"])
        self.assertNotIn("metadata_path", status["layers"]["skull"]["artifact"])
        self.assertNotIn("parameters", status["layers"]["skull"]["artifact"])

    def test_publish_rejects_layer_when_source_modality_is_not_qualified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = write_volume(root, modality="MR")
            vertices, faces = tetrahedron()
            with self.assertRaisesRegex(AnatomyReconstructionValidationError, "CT HU"):
                AnatomyReconstructionService(data_dir=root).publish_layer_latest(
                    layer="skull",
                    vertices_lps_mm=vertices,
                    faces=faces,
                    algorithm="test",
                    algorithm_version="1",
                )
            manifest = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("anatomy", manifest)

    def test_publish_rejects_nonfinite_vertices_and_invalid_faces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root, modality="CT")
            service = AnatomyReconstructionService(data_dir=root)
            vertices, faces = tetrahedron()
            bad_vertices = vertices.copy()
            bad_vertices[0, 0] = np.nan
            with self.assertRaisesRegex(AnatomyReconstructionValidationError, "finite"):
                service.publish_layer_latest(
                    layer="skull",
                    vertices_lps_mm=bad_vertices,
                    faces=faces,
                    algorithm="test",
                    algorithm_version="1",
                )
            bad_faces = faces.copy()
            bad_faces[0, 0] = 99
            with self.assertRaisesRegex(AnatomyReconstructionValidationError, "out of bounds"):
                service.publish_layer_latest(
                    layer="skull",
                    vertices_lps_mm=vertices,
                    faces=bad_faces,
                    algorithm="test",
                    algorithm_version="1",
                )

    def test_corrupted_published_artifact_is_never_reported_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = write_volume(root, modality="CT")
            service = AnatomyReconstructionService(data_dir=root)
            vertices, faces = tetrahedron()
            descriptor = service.publish_layer_latest(
                layer="skull",
                vertices_lps_mm=vertices,
                faces=faces,
                algorithm="test",
                algorithm_version="1",
            )
            artifact = study_dir / descriptor.artifact_path
            artifact.write_bytes(artifact.read_bytes() + b"corrupt")
            status = service.inspect_latest()

        self.assertFalse(status["layers"]["skull"]["artifact_ready"])
        self.assertEqual(status["layers"]["skull"]["state"], "eligible")

    def test_artifact_is_not_ready_after_source_volume_identity_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = write_volume(root, modality="CT")
            service = AnatomyReconstructionService(data_dir=root)
            vertices, faces = tetrahedron()
            service.publish_layer_latest(
                layer="skull",
                vertices_lps_mm=vertices,
                faces=faces,
                algorithm="test",
                algorithm_version="1",
            )
            manifest_path = study_dir / "manifest.json"
            metadata_path = study_dir / "derived" / "volume.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["volume"]["created_at_utc"] = "2026-09-01T01:00:00+00:00"
            metadata = dict(manifest["volume"])
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
            status = service.inspect_latest()

        self.assertFalse(status["layers"]["skull"]["artifact_ready"])
        self.assertEqual(status["layers"]["skull"]["state"], "eligible")

    def test_reconstruction_status_api_is_authenticated_and_no_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root, modality="CT")
            with TestClient(create_app(settings=make_settings(root))) as client:
                denied = client.get("/api/studies/latest/reconstruction")
                login = client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                response = client.get("/api/studies/latest/reconstruction")

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertTrue(response.json()["reconstruction"]["layers"]["skull"]["input_eligible"])
        self.assertNotIn("artifact_path", response.text)
        self.assertNotIn("/tmp/", response.text)

    def test_phase4a_does_not_promote_heavy_reconstruction_packages_to_backend_runtime(self) -> None:
        backend_requirements = (ROOT / "requirements" / "backend.txt").read_text(encoding="utf-8").lower()
        for package in ("scipy", "scikit-image", "simpleitk", "trimesh", "pyvista"):
            with self.subTest(package=package):
                self.assertNotIn(package, backend_requirements)


if __name__ == "__main__":
    unittest.main()
