from __future__ import annotations

from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.segmentation import SegmentationValidationError  # noqa: E402
from voxelatlas.segmentation_surfaces import (  # noqa: E402
    SURFACE_HEADER,
    SURFACE_MAGIC,
    SURFACE_MEDIA_TYPE,
    SegmentationSurface,
    SegmentationSurfaceService,
)
from voxelatlas import config  # noqa: E402


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


def make_service(root: Path) -> SegmentationSurfaceService:
    labels = np.zeros((4, 5, 6), dtype=np.uint16)
    labels[1:3, 1:4, 2:5] = 7
    artifact_root = root / "segmentation" / "label-maps" / LABEL_MAP_ID
    artifact_root.mkdir(parents=True)
    np.save(artifact_root / "labels.npy", labels, allow_pickle=False)
    descriptor = {
        "label_map_id": LABEL_MAP_ID,
        "state": "ready",
        "source_study_id": STUDY_ID,
        "source_modality": "CT",
        "provider_id": "totalsegmentator",
        "provider_version": "2.18.0",
        "model_id": "total",
        "model_version": "2.18.0",
        "coordinate_system": "patient_lps",
        "representation": "label_map",
        "artifact_format": "npy",
        "artifact_sha256": "a" * 64,
        "shape": [4, 5, 6],
        "dtype": "uint16",
        "axis_order": ["slice", "row", "column"],
        "present_labels": [0, 7],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 2.0, 10.0],
            [0.0, 3.0, 0.0, 20.0],
            [4.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "clinical_validation": "not_claimed",
    }
    return SegmentationSurfaceService(
        data_dir=root,
        study_repository=FakeStudyRepository(),
        label_map_service=FakeLabelMapService(descriptor),
    )


class Phase5F1SurfaceServiceTests(unittest.TestCase):
    def test_single_label_surface_is_deterministic_and_patient_lps_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = make_service(Path(tmp))
            first = service.surface_latest(
                label_id=7,
                label_map_id=LABEL_MAP_ID,
                quality="preview",
            )
            second = service.surface_latest(
                label_id=7,
                label_map_id=LABEL_MAP_ID,
                quality="preview",
            )

        self.assertEqual(first.payload, second.payload)
        self.assertEqual(first.payload_sha256, second.payload_sha256)
        self.assertEqual(first.coordinate_system, "patient_lps")
        self.assertEqual(first.extraction, "voxel_boundary_faces")
        self.assertEqual(first.stride, 1)
        self.assertEqual(first.triangle_count, 84)
        self.assertEqual(first.vertex_count, 168)
        self.assertEqual(first.bounds_lps_mm, (13.0, 21.5, 32.0, 19.0, 30.5, 40.0))

        header = SURFACE_HEADER.unpack_from(first.payload)
        self.assertEqual(header[0], SURFACE_MAGIC)
        self.assertEqual(header[1], 1)
        self.assertEqual(header[2], 7)
        self.assertEqual(header[3], first.vertex_count)
        self.assertEqual(header[4], first.triangle_count * 3)
        self.assertEqual(len(first.payload), SURFACE_HEADER.size + 168 * 12 + 84 * 12)

    def test_descriptor_is_study_bound_and_exposes_no_internal_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            descriptor = make_service(Path(tmp)).descriptor_latest(
                label_map_id=LABEL_MAP_ID,
            )

        self.assertTrue(descriptor["ready"])
        self.assertEqual(descriptor["label_map_id"], LABEL_MAP_ID)
        self.assertEqual(descriptor["source_study_id"], STUDY_ID)
        self.assertEqual(descriptor["present_labels"], [7])
        self.assertEqual(descriptor["coordinate_system"], "patient_lps")
        self.assertEqual(descriptor["surface_endpoint"], "/api/studies/latest/segmentation-surfaces/{label_id}")
        self.assertEqual(descriptor["clinical_validation"], "not_claimed")
        self.assertNotIn(str(Path(tmp)), str(descriptor))

    def test_background_missing_labels_and_cross_study_maps_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = make_service(Path(tmp))
            for label_id in (0, 8, 118):
                with self.subTest(label_id=label_id):
                    with self.assertRaises(SegmentationValidationError):
                        service.surface_latest(
                            label_id=label_id,
                            label_map_id=LABEL_MAP_ID,
                            quality="preview",
                        )

            service.repository = FakeStudyRepository("f" * 32)
            with self.assertRaises(SegmentationValidationError):
                service.descriptor_latest(label_map_id=LABEL_MAP_ID)

    def test_invalid_quality_and_changed_artifact_contract_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = make_service(root)
            with self.assertRaises(SegmentationValidationError):
                service.surface_latest(
                    label_id=7,
                    label_map_id=LABEL_MAP_ID,
                    quality="maximum",
                )
            path = root / "segmentation" / "label-maps" / LABEL_MAP_ID / "labels.npy"
            np.save(path, np.zeros((2, 2, 2), dtype=np.uint16), allow_pickle=False)
            with self.assertRaises(SegmentationValidationError):
                service.surface_latest(
                    label_id=7,
                    label_map_id=LABEL_MAP_ID,
                    quality="preview",
                )


class Phase5F1FrontendContractTests(unittest.TestCase):
    def test_authenticated_surface_endpoints_are_bound_and_no_store(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from voxelatlas.app import create_app
            from voxelatlas.passwords import hash_password
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(f"HTTP dependencies unavailable: {exc}")

        payload = SURFACE_HEADER.pack(
            SURFACE_MAGIC, 1, 7, 4, 6, 1, 48, 24
        ) + (b"\0" * 72)

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
                    extraction="voxel_boundary_faces",
                    coordinate_system="patient_lps",
                    stride=1,
                    vertex_count=4,
                    triangle_count=2,
                    bounds_lps_mm=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
                    payload_sha256="b" * 64,
                    payload=payload,
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
            with TestClient(
                create_app(
                    settings=settings,
                    segmentation_surface_service=StubSurfaceService(),
                )
            ) as client:
                denied = client.get("/api/studies/latest/segmentation-surfaces")
                client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                descriptor = client.get(
                    "/api/studies/latest/segmentation-surfaces",
                    params={"label_map_id": LABEL_MAP_ID},
                )
                surface = client.get(
                    "/api/studies/latest/segmentation-surfaces/7",
                    params={"label_map_id": LABEL_MAP_ID, "quality": "preview"},
                )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(descriptor.status_code, 200)
        self.assertEqual(descriptor.headers["cache-control"], "no-store")
        self.assertEqual(surface.status_code, 200)
        self.assertEqual(surface.headers["content-type"], SURFACE_MEDIA_TYPE)
        self.assertEqual(surface.headers["cache-control"], "no-store")
        self.assertEqual(surface.headers["x-content-type-options"], "nosniff")
        self.assertEqual(surface.headers["x-voxelatlas-label-id"], "7")
        self.assertEqual(surface.headers["x-voxelatlas-surface-triangles"], "2")
        self.assertEqual(surface.content, payload)

    def test_workspace_exposes_selected_structure_surface_controls(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        module = (ROOT / "web" / "js" / "segmentation-surface-viewer.js").read_text(
            encoding="utf-8"
        )

        for control_id in (
            "segmentationSurfacePanel",
            "segmentationSurfaceToggle",
            "segmentationSurfaceStatus",
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("PatientSegmentationSurfaceLayer", module)
        self.assertIn("computeVertexNormals", module)
        self.assertIn("patient_lps", module)
        self.assertIn("syncSegmentationSurface", app)
        self.assertNotIn("clinical-grade", (html + app + module).lower())

    def test_phase5f1_browser_and_architecture_probes_exist(self) -> None:
        self.assertTrue((ROOT / "scripts" / "check_phase5f1_surface_viewer.mjs").is_file())
        self.assertTrue(
            (ROOT / "scripts" / "check_phase5f1_segmentation_surface_architecture.py").is_file()
        )


if __name__ == "__main__":
    unittest.main()
