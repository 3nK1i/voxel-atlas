from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.segmentation import SegmentationValidationError  # noqa: E402
from voxelatlas.segmentation_surface_runtime import (  # noqa: E402
    SegmentationSurfaceRuntimeQualifier,
)
from voxelatlas.segmentation_surfaces import (  # noqa: E402
    ACCURATE_SURFACE_EXTRACTION,
    ACCURATE_SURFACE_HEADER,
    ACCURATE_SURFACE_MEDIA_TYPE,
    SegmentationSurface,
    SegmentationSurfaceService,
)


LABEL_MAP_ID = "map-0123456789abcdef0123456789abcdef"
STUDY_ID = "0123456789abcdef0123456789abcdef"


class FakeStudyRepository:
    def __init__(self, study_id: str = STUDY_ID):
        self.study_id = study_id

    def latest_manifest(self) -> dict[str, object]:
        return {"study_id": self.study_id}


class FakeLabelMapService:
    def __init__(self, descriptor: dict[str, object]):
        self.descriptor = descriptor

    def get(self, label_map_id: str) -> dict[str, object]:
        if label_map_id != LABEL_MAP_ID:
            raise AssertionError("unexpected label-map identity")
        return dict(self.descriptor)

    def list(self, *, study_id: str | None = None) -> list[dict[str, object]]:
        if study_id != self.descriptor["source_study_id"]:
            return []
        return [dict(self.descriptor)]


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_service(
    root: Path,
    *,
    labels: np.ndarray | None = None,
    affine: list[list[float]] | None = None,
    worker_python: str | None = None,
) -> tuple[SegmentationSurfaceService, Path, dict[str, object]]:
    if labels is None:
        labels = np.zeros((4, 5, 6), dtype=np.uint16)
        labels[1:3, 1:4, 2:5] = 7
    artifact_root = root / "segmentation" / "label-maps" / LABEL_MAP_ID
    artifact_root.mkdir(parents=True)
    artifact_path = artifact_root / "labels.npy"
    np.save(artifact_path, labels, allow_pickle=False)
    descriptor = {
        "label_map_id": LABEL_MAP_ID,
        "state": "ready",
        "source_study_id": STUDY_ID,
        "source_study_instance_uid": "1.2.840.113619.2.55.3.1",
        "source_series_uid": "1.2.840.113619.2.55.3.2",
        "source_modality": "CT",
        "source_volume_descriptor_sha256": "1" * 64,
        "source_volume_artifact_sha256": "2" * 64,
        "segmentation_job_id": "seg-" + "3" * 32,
        "segmentation_terminal_provenance_sha256": "4" * 64,
        "provider_id": "totalsegmentator",
        "provider_version": "2.18.0",
        "model_id": "total",
        "model_version": "2.18.0",
        "model_descriptor_sha256": "5" * 64,
        "task": "total",
        "task_definition_sha256": "6" * 64,
        "provider_mask_sha256": "7" * 64,
        "coordinate_system": "patient_lps",
        "length_units": "mm",
        "representation": "label_map",
        "artifact_format": "npy",
        "artifact_sha256": sha256_file(artifact_path),
        "shape": list(labels.shape),
        "dtype": "uint16",
        "axis_order": ["slice", "row", "column"],
        "present_labels": [0, 7],
        "array_index_to_patient_lps": affine or [
            [0.0, 0.0, 2.0, 10.0],
            [0.0, 3.0, 0.0, 20.0],
            [4.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "model_index_to_patient_lps": [
            [0.0, 0.0, 2.0, 10.0],
            [0.0, 3.0, 0.0, 20.0],
            [4.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "source_to_model_index": np.eye(4).tolist(),
        "model_to_source_index": np.eye(4).tolist(),
        "resampled": False,
        "interpolation": "none",
        "clinical_validation": "not_claimed",
    }
    service = SegmentationSurfaceService(
        data_dir=root,
        study_repository=FakeStudyRepository(),
        label_map_service=FakeLabelMapService(descriptor),
        worker_python=(
            worker_python
            if worker_python is not None
            else os.environ.get("VOXELATLAS_SURFACE_PYTHON")
        ),
    )
    return service, artifact_path, descriptor


def decode_accurate(surface):
    header = ACCURATE_SURFACE_HEADER.unpack_from(surface.payload)
    self_magic, version, label_id, vertex_count, index_count, pos_bytes, normal_bytes, index_bytes, flags = header
    offset = ACCURATE_SURFACE_HEADER.size
    positions = np.frombuffer(surface.payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape(-1, 3)
    offset += pos_bytes
    normals = np.frombuffer(surface.payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape(-1, 3)
    offset += normal_bytes
    indices = np.frombuffer(surface.payload, dtype="<u4", count=index_count, offset=offset).reshape(-1, 3)
    return {
        "magic": self_magic,
        "version": version,
        "label_id": label_id,
        "vertex_count": vertex_count,
        "index_count": index_count,
        "pos_bytes": pos_bytes,
        "normal_bytes": normal_bytes,
        "index_bytes": index_bytes,
        "flags": flags,
        "positions": positions,
        "normals": normals,
        "indices": indices,
    }


class Phase6AAccurateSurfaceTests(unittest.TestCase):
    def test_accurate_surface_requires_explicit_qualified_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp), worker_python="")
            with self.assertRaisesRegex(
                SegmentationValidationError, "surface runtime is not configured"
            ):
                service.surface_latest(
                    label_id=7, label_map_id=LABEL_MAP_ID, quality="accurate"
                )

    def test_runtime_qualifier_records_scientific_runtime_fingerprint(self) -> None:
        payload = {
            "schema_version": 1,
            "python_version": "3.12.3",
            "numpy_version": "2.5.2",
            "scikit_image_version": "0.26.0",
            "numpy_available": True,
            "skimage_available": True,
            "marching_cubes_available": True,
            "runtime_fingerprint_sha256": "147606f76b5c72b93646451dda079716aa6a7d51914d9bcc78bed6ce1c6773e4",
        }

        class Completed:
            returncode = 0
            stdout = json.dumps(payload) + "\n"

        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return Completed()

        report = SegmentationSurfaceRuntimeQualifier(runner=runner).qualify(
            "/opt/voxelatlas-surface/bin/python"
        )
        self.assertTrue(report.qualified)
        self.assertEqual(report.numpy_version, "2.5.2")
        self.assertEqual(report.scikit_image_version, "0.26.0")
        self.assertEqual(
            report.runtime_fingerprint_sha256,
            "147606f76b5c72b93646451dda079716aa6a7d51914d9bcc78bed6ce1c6773e4",
        )
        self.assertEqual(calls[0][0][:2], ["/opt/voxelatlas-surface/bin/python", "-I"])
        self.assertFalse(calls[0][1]["shell"])

    def test_descriptor_makes_accurate_surface_default_without_removing_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp))
            descriptor = service.descriptor_latest(label_map_id=LABEL_MAP_ID)

        self.assertEqual(descriptor["default_quality"], "accurate")
        self.assertEqual(descriptor["accurate_surface"]["extraction"], ACCURATE_SURFACE_EXTRACTION)
        self.assertEqual(descriptor["accurate_surface"]["media_type"], ACCURATE_SURFACE_MEDIA_TYPE)
        self.assertTrue(descriptor["preview_surface"]["available"])
        self.assertEqual(descriptor["source_label_map_immutable"], True)
        self.assertEqual(descriptor["clinical_validation"], "not_claimed")

    def test_native_resolution_surface_is_deterministic_patient_lps_and_carries_normals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_service, _, _ = make_service(root)
            first = first_service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality="accurate"
            )
            second_service = SegmentationSurfaceService(
                data_dir=root,
                study_repository=first_service.repository,
                label_map_service=first_service.label_map_service,
                worker_python=os.environ.get("VOXELATLAS_SURFACE_PYTHON"),
            )
            second = second_service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality="accurate"
            )

        self.assertEqual(first.schema_version, 2)
        self.assertEqual(first.media_type, ACCURATE_SURFACE_MEDIA_TYPE)
        self.assertEqual(first.extraction, ACCURATE_SURFACE_EXTRACTION)
        self.assertEqual(first.coordinate_system, "patient_lps")
        self.assertEqual(first.stride, 1)
        self.assertEqual(first.bounds_lps_mm, (13.0, 21.5, 32.0, 19.0, 30.5, 40.0))
        self.assertEqual(first.surface_id, second.surface_id)
        self.assertEqual(first.provenance_sha256, second.provenance_sha256)
        self.assertEqual(first.payload_sha256, second.payload_sha256)
        self.assertEqual(first.payload, second.payload)

        decoded = decode_accurate(first)
        self.assertEqual(decoded["magic"], b"VXSF")
        self.assertEqual(decoded["version"], 2)
        self.assertEqual(decoded["label_id"], 7)
        self.assertEqual(decoded["vertex_count"], first.vertex_count)
        self.assertEqual(decoded["index_count"], first.triangle_count * 3)
        self.assertEqual(decoded["pos_bytes"], first.vertex_count * 12)
        self.assertEqual(decoded["normal_bytes"], first.vertex_count * 12)
        self.assertEqual(decoded["index_bytes"], first.triangle_count * 12)
        self.assertEqual(decoded["flags"], 1)
        self.assertTrue(np.all(np.isfinite(decoded["positions"])))
        self.assertTrue(np.all(np.isfinite(decoded["normals"])))
        np.testing.assert_allclose(np.linalg.norm(decoded["normals"], axis=1), 1.0, atol=1e-5)
        self.assertGreaterEqual(int(decoded["indices"].min()), 0)
        self.assertLess(int(decoded["indices"].max()), first.vertex_count)

        triangles = decoded["positions"][decoded["indices"]]
        face_normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        face_lengths = np.linalg.norm(face_normals, axis=1)
        self.assertTrue(np.all(face_lengths > 1e-8))
        averaged = decoded["normals"][decoded["indices"]].mean(axis=1)
        self.assertTrue(np.all(np.einsum("ij,ij->i", face_normals, averaged) > 0.0))

    def test_local_gradient_normal_disagreement_does_not_reject_global_winding(self) -> None:
        labels = np.zeros((5, 5, 5), dtype=np.uint16)
        coordinates = [
            (0, 1, 1), (0, 2, 2), (0, 3, 3), (0, 3, 4), (0, 4, 0),
            (1, 0, 0), (1, 0, 1), (1, 0, 2), (1, 4, 2),
            (2, 0, 0), (2, 0, 2), (2, 1, 0), (2, 1, 1), (2, 2, 4),
            (2, 3, 3), (2, 4, 0), (2, 4, 3),
            (3, 0, 1), (3, 1, 0), (3, 1, 3), (3, 2, 3), (3, 2, 4),
            (3, 3, 0), (3, 4, 2), (3, 4, 4),
            (4, 0, 2), (4, 1, 4), (4, 2, 3), (4, 3, 0), (4, 3, 3),
            (4, 4, 3),
        ]
        for coordinate in coordinates:
            labels[coordinate] = 7

        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp), labels=labels)
            surface = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality="accurate"
            )

        decoded = decode_accurate(surface)
        triangles = decoded["positions"][decoded["indices"]]
        face_cross = np.cross(
            triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
        )
        self.assertTrue(np.all(np.linalg.norm(face_cross, axis=1) > 1e-8))
        self.assertTrue(np.all(np.isfinite(decoded["normals"])))
        np.testing.assert_allclose(
            np.linalg.norm(decoded["normals"], axis=1), 1.0, atol=1e-5
        )

    def test_boundary_touching_labels_reach_full_half_voxel_cell_envelope(self) -> None:
        labels = np.zeros((4, 5, 6), dtype=np.uint16)
        labels[0, 0, 0] = 7
        labels[3, 4, 5] = 7
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp), labels=labels)
            surface = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality="accurate"
            )

        self.assertEqual(surface.bounds_lps_mm, (9.0, 18.5, 28.0, 21.0, 33.5, 44.0))

    def test_reflected_affine_keeps_winding_and_normals_consistent(self) -> None:
        affine = [
            [-2.0, 0.0, 0.0, 10.0],
            [0.0, 3.0, 0.0, 20.0],
            [0.0, 0.0, 4.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        labels = np.zeros((3, 3, 3), dtype=np.uint16)
        labels[1, 1, 1] = 7
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp), labels=labels, affine=affine)
            surface = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality="accurate"
            )
        decoded = decode_accurate(surface)
        triangles = decoded["positions"][decoded["indices"]]
        face_normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        averaged = decoded["normals"][decoded["indices"]].mean(axis=1)
        self.assertTrue(np.all(np.einsum("ij,ij->i", face_normals, averaged) > 0.0))
        self.assertEqual(surface.bounds_lps_mm, (7.0, 21.5, 32.0, 9.0, 24.5, 36.0))


    def test_oblique_affine_preserves_index_space_half_voxel_interface(self) -> None:
        affine = [
            [0.0, -2.0, 0.25, 10.0],
            [1.5, 0.0, 0.0, 20.0],
            [0.2, 0.0, 3.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        labels = np.zeros((3, 3, 3), dtype=np.uint16)
        labels[1, 1, 1] = 7
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp), labels=labels, affine=affine)
            surface = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality="accurate"
            )
        decoded = decode_accurate(surface)
        linear = np.asarray(affine, dtype=np.float64)[:3, :3]
        translation = np.asarray(affine, dtype=np.float64)[:3, 3]
        recovered = (decoded["positions"].astype(np.float64) - translation) @ np.linalg.inv(linear).T
        self.assertTrue(np.all(recovered >= 0.5 - 1e-5))
        self.assertTrue(np.all(recovered <= 1.5 + 1e-5))
        for axis in range(3):
            self.assertAlmostEqual(float(recovered[:, axis].min()), 0.5, places=5)
            self.assertAlmostEqual(float(recovered[:, axis].max()), 1.5, places=5)

    def test_accurate_surface_rejects_changed_artifact_and_absent_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, artifact_path, _ = make_service(root)
            with self.assertRaises(SegmentationValidationError):
                service.surface_latest(
                    label_id=8, label_map_id=LABEL_MAP_ID, quality="accurate"
                )
            changed = np.zeros((4, 5, 6), dtype=np.uint16)
            changed[1, 1, 1] = 7
            np.save(artifact_path, changed, allow_pickle=False)
            with self.assertRaisesRegex(SegmentationValidationError, "artifact changed"):
                service.surface_latest(
                    label_id=7, label_map_id=LABEL_MAP_ID, quality="accurate"
                )

    def test_accurate_surface_keeps_heavy_mesh_dependency_out_of_backend_imports(self) -> None:
        backend = (ROOT / "backend" / "voxelatlas" / "segmentation_surfaces.py").read_text(
            encoding="utf-8"
        )
        runtime = (ROOT / "backend" / "voxelatlas" / "segmentation_surface_runtime.py").read_text(
            encoding="utf-8"
        )
        worker = (ROOT / "scripts" / "phase6a_surface_worker.py").read_text(encoding="utf-8")
        backend_requirements = (ROOT / "requirements" / "backend.txt").read_text(encoding="utf-8")
        surface_requirements = (ROOT / "requirements" / "segmentation-surfaces.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from skimage", backend)
        self.assertNotIn("import skimage", backend)
        self.assertNotIn("from skimage", runtime)
        self.assertNotIn("import skimage", runtime)
        self.assertNotIn("scikit-image", backend_requirements)
        self.assertIn("scikit-image", surface_requirements)
        self.assertIn("from skimage.measure import marching_cubes", worker)
        self.assertNotIn("decimat", worker.lower())
        self.assertNotIn("smooth", worker.lower())
        self.assertNotIn("trimesh", worker.lower())


class Phase6AFrontendContractTests(unittest.TestCase):

    def test_settings_expose_explicit_surface_worker_without_backend_dependency_leak(self) -> None:
        from voxelatlas import config

        settings = config.load_settings(
            {
                "VOXELATLAS_ENV": "test",
                "VOXELATLAS_SURFACE_PYTHON": "/opt/voxelatlas-surface/bin/python",
            }
        )
        self.assertEqual(
            settings.surface_worker_python, "/opt/voxelatlas-surface/bin/python"
        )
        backend_requirements = (ROOT / "requirements" / "backend.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("scikit-image", backend_requirements)

    def test_authenticated_api_transports_v2_identity_and_provenance(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from voxelatlas.app import create_app
            from voxelatlas.passwords import hash_password
            from voxelatlas import config
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(f"HTTP dependencies unavailable: {exc}")

        positions = np.asarray([[1.0, 2.0, 3.0], [2.0, 2.0, 3.0], [1.0, 3.0, 3.0]], dtype="<f4")
        normals = np.asarray([[0.0, 0.0, 1.0]] * 3, dtype="<f4")
        indices = np.asarray([0, 1, 2], dtype="<u4")
        payload = ACCURATE_SURFACE_HEADER.pack(
            b"VXSF", 2, 7, 3, 3, positions.nbytes, normals.nbytes, indices.nbytes, 1
        ) + positions.tobytes() + normals.tobytes() + indices.tobytes()

        class StubSurfaceService:
            def descriptor_latest(self, *, label_map_id=None):
                return {
                    "ready": True,
                    "label_map_id": label_map_id or LABEL_MAP_ID,
                    "source_study_id": STUDY_ID,
                    "coordinate_system": "patient_lps",
                }

            def surface_latest(self, *, label_id, label_map_id, quality):
                return SegmentationSurface(
                    label_map_id=label_map_id,
                    label_id=label_id,
                    quality=quality,
                    extraction=ACCURATE_SURFACE_EXTRACTION,
                    coordinate_system="patient_lps",
                    stride=1,
                    vertex_count=3,
                    triangle_count=1,
                    bounds_lps_mm=(1.0, 2.0, 3.0, 2.0, 3.0, 3.0),
                    payload_sha256=sha256(payload).hexdigest(),
                    payload=payload,
                    schema_version=2,
                    media_type=ACCURATE_SURFACE_MEDIA_TYPE,
                    surface_id="surf-" + "8" * 32,
                    provenance_sha256="9" * 64,
                    normal_count=3,
                )

        with tempfile.TemporaryDirectory() as tmp:
            settings = config.AppSettings(
                environment="test",
                session_secret="x" * 48,
                secure_cookies=False,
                session_cookie_name="voxelatlas_session",
                allowed_hosts=("testserver", "127.0.0.1", "localhost"),
                data_dir=Path(tmp),
                max_upload_mib=512,
                auth_username="engineer",
                auth_password_hash=hash_password("correct horse battery staple"),
                session_ttl_minutes=60,
            )
            with TestClient(create_app(settings=settings, segmentation_surface_service=StubSurfaceService())) as client:
                client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                response = client.get(
                    "/api/studies/latest/segmentation-surfaces/7",
                    params={"label_map_id": LABEL_MAP_ID, "quality": "accurate"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], ACCURATE_SURFACE_MEDIA_TYPE)
        self.assertEqual(response.headers["x-voxelatlas-surface-schema"], "2")
        self.assertEqual(response.headers["x-voxelatlas-surface-id"], "surf-" + "8" * 32)
        self.assertEqual(response.headers["x-voxelatlas-surface-provenance-sha256"], "9" * 64)
        self.assertEqual(response.content, payload)

    def test_browser_accepts_v2_normals_and_defaults_to_accurate_surface(self) -> None:
        module = (ROOT / "web" / "js" / "segmentation-surface-viewer.js").read_text(
            encoding="utf-8"
        )
        app = (ROOT / "backend" / "voxelatlas" / "app.py").read_text(encoding="utf-8")
        self.assertIn("application/x-voxelatlas-surface-v2", module)
        self.assertIn('setAttribute("normal"', module)
        self.assertIn('default_quality || "accurate"', module)
        self.assertIn("accurate", app)
        self.assertIn("X-VoxelAtlas-Surface-Id", app)
        self.assertIn("X-VoxelAtlas-Surface-Provenance-SHA256", app)

    def test_static_surface_copy_and_cache_identity_are_phase6a_accurate(self) -> None:
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Patient LPS accurate surface", index)
        self.assertNotIn("Patient LPS preview mesh", index)
        self.assertRegex(
            index,
            r'/js/app\.js\?v=[^"]*phase6a-r1[^"]*"',
        )
        self.assertIn("segmentation-surface-viewer.js?v=phase6a-r1", app)
        self.assertNotIn("segmentation-surface-viewer.js?v=phase5f1-r1", app)


if __name__ == "__main__":
    unittest.main()
