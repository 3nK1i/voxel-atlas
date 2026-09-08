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

from voxelatlas import config  # noqa: E402
from voxelatlas.dicom_mpr import CanonicalMprService  # noqa: E402
from voxelatlas.segmentation import SegmentationValidationError  # noqa: E402
from voxelatlas.segmentation_overlays import (  # noqa: E402
    OVERLAY_MEDIA_TYPE,
    SegmentationOverlayService,
    color_for_label,
)


STUDY_ID = "f" * 32
LABEL_MAP_ID = "map-" + "4" * 32
AFFINE = [
    [0.0, 0.0, 0.5, 10.0],
    [0.0, 1.0, 0.0, 20.0],
    [2.0, 0.0, 0.0, 30.0],
    [0.0, 0.0, 0.0, 1.0],
]


def write_volume(root: Path) -> np.ndarray:
    study_dir = root / "studies" / STUDY_ID
    derived = study_dir / "derived"
    derived.mkdir(parents=True)
    volume = np.arange(3 * 2 * 4, dtype=np.float32).reshape(3, 2, 4)
    np.save(derived / "volume.npy", volume, allow_pickle=False)
    descriptor = {
        "schema_version": 1,
        "ready": True,
        "created_at_utc": "2026-09-08T00:00:00+00:00",
        "source_series_uid": "series",
        "source_instance_count": 3,
        "modality": "CT",
        "dtype": "float32",
        "shape": [3, 2, 4],
        "axis_order": ["slice", "row", "column"],
        "spacing_mm": [2.0, 1.0, 0.5],
        "origin_patient_lps_mm": [10.0, 20.0, 30.0],
        "array_index_to_patient_lps": AFFINE,
        "intensity_units": "HU",
        "value_range": [0.0, 23.0],
        "artifact_path": "derived/volume.npy",
        "metadata_path": "derived/volume.json",
    }
    (derived / "volume.json").write_text(json.dumps(descriptor), encoding="utf-8")
    (study_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "study_id": STUDY_ID,
                "study_instance_uid": "1.2.3",
                "created_at_utc": "2026-09-08T00:00:00+00:00",
                "study_date": "20260908",
                "study_description": "Synthetic CT",
                "modalities": ["CT"],
                "file_count": 3,
                "skipped_file_count": 0,
                "series_count": 1,
                "primary_series_uid": "series",
                "reconstruction_ready": True,
                "reconstruction_series_uid": "series",
                "series": [],
                "volume": descriptor,
            }
        ),
        encoding="utf-8",
    )
    return volume


class StubLabelMapService:
    def __init__(self, descriptor: dict[str, object]):
        self.descriptor = descriptor

    def list(self, *, study_id: str | None = None) -> list[dict[str, object]]:
        if study_id is not None and study_id != self.descriptor["source_study_id"]:
            return []
        return [dict(self.descriptor)]

    def get(self, label_map_id: str) -> dict[str, object]:
        if label_map_id != self.descriptor["label_map_id"]:
            raise SegmentationValidationError("Canonical label map was not found")
        return dict(self.descriptor)


def make_service(root: Path, *, study_id: str = STUDY_ID) -> SegmentationOverlayService:
    labels = np.zeros((3, 2, 4), dtype=np.uint16)
    labels[1, 0, 1] = 1
    labels[1, 1, 2] = 7
    map_dir = root / "segmentation" / "label-maps" / LABEL_MAP_ID
    map_dir.mkdir(parents=True)
    np.save(map_dir / "labels.npy", labels, allow_pickle=False)
    descriptor = {
        "label_map_id": LABEL_MAP_ID,
        "state": "ready",
        "source_study_id": study_id,
        "source_modality": "CT",
        "provider_id": "totalsegmentator",
        "provider_version": "2.18.0",
        "model_id": "total",
        "model_version": "2.18.0",
        "coordinate_system": "patient_lps",
        "representation": "label_map",
        "artifact_format": "npy",
        "artifact_sha256": "a" * 64,
        "artifact_bytes": int(labels.nbytes),
        "shape": [3, 2, 4],
        "dtype": "uint16",
        "axis_order": ["slice", "row", "column"],
        "array_index_to_patient_lps": AFFINE,
        "present_labels": [0, 1, 7],
        "nonzero_voxels": 2,
        "clinical_validation": "not_claimed",
    }
    return SegmentationOverlayService(
        data_dir=root,
        mpr_service=CanonicalMprService(data_dir=root),
        label_map_service=StubLabelMapService(descriptor),
    )


class Phase5DOverlayServiceTests(unittest.TestCase):
    def test_descriptor_selects_latest_map_for_exact_current_study(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            descriptor = make_service(root).descriptor_latest()

        self.assertTrue(descriptor["ready"])
        self.assertEqual(descriptor["source_study_id"], STUDY_ID)
        self.assertEqual(descriptor["label_map_id"], LABEL_MAP_ID)
        self.assertEqual(descriptor["coordinate_system"], "patient_lps")
        self.assertEqual(descriptor["sampling"], "nearest_neighbor")
        self.assertEqual(descriptor["present_label_count"], 2)
        self.assertEqual(descriptor["clinical_validation"], "not_claimed")
        self.assertEqual(
            descriptor["palette"],
            [
                {"label_id": 1, "color_hex": color_for_label(1)},
                {"label_id": 7, "color_hex": color_for_label(7)},
            ],
        )

    def test_descriptor_is_unavailable_when_current_study_has_no_bound_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            descriptor = make_service(root, study_id="e" * 32).descriptor_latest()

        self.assertFalse(descriptor["ready"])
        self.assertEqual(descriptor["source_study_id"], STUDY_ID)
        self.assertEqual(descriptor["reason"], "no_label_map")

    def test_rgba_overlay_uses_the_mpr_grid_and_transparent_background(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            service = make_service(root)
            image = service.render_latest("axial", index=1)

        self.assertEqual((image.width, image.height), (4, 2))
        rgba = np.frombuffer(image.pixels, dtype=np.uint8).reshape(2, 4, 4)
        self.assertEqual(tuple(rgba[0, 0]), (0, 0, 0, 0))
        self.assertEqual(rgba[0, 1, 3], 255)
        self.assertEqual(rgba[1, 2, 3], 255)
        self.assertNotEqual(tuple(rgba[0, 1, :3]), tuple(rgba[1, 2, :3]))

    def test_requested_map_cannot_cross_the_current_study_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            service = make_service(root, study_id="e" * 32)
            with self.assertRaisesRegex(SegmentationValidationError, "current study"):
                service.render_latest("axial", index=1, label_map_id=LABEL_MAP_ID)


class StubOverlayService:
    descriptor = {
        "ready": True,
        "label_map_id": LABEL_MAP_ID,
        "source_study_id": STUDY_ID,
        "coordinate_system": "patient_lps",
        "sampling": "nearest_neighbor",
        "present_label_count": 2,
        "clinical_validation": "not_claimed",
    }

    def descriptor_latest(self, *, label_map_id: str | None = None) -> dict[str, object]:
        del label_map_id
        return dict(self.descriptor)

    def render_latest(self, plane: str, *, index: int, label_map_id: str | None = None):
        del label_map_id
        from voxelatlas.segmentation_overlays import SegmentationOverlayImage

        return SegmentationOverlayImage(
            plane=plane,
            index=index,
            position_mm=30.0,
            width=2,
            height=1,
            label_map_id=LABEL_MAP_ID,
            pixels=bytes([0, 0, 0, 0, 255, 0, 0, 255]),
        )


class Phase5DHttpAndFrontendTests(unittest.TestCase):
    def test_authenticated_descriptor_and_rgba_endpoints_are_no_store(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from voxelatlas.app import create_app
            from voxelatlas.passwords import hash_password
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(f"HTTP dependencies unavailable: {exc}")

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
                create_app(settings=settings, segmentation_overlay_service=StubOverlayService())
            ) as client:
                denied = client.get("/api/studies/latest/segmentation-overlay")
                client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                descriptor = client.get("/api/studies/latest/segmentation-overlay")
                image = client.get(
                    "/api/studies/latest/segmentation-overlay/axial",
                    params={"index": 1, "label_map_id": LABEL_MAP_ID},
                )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(descriptor.status_code, 200)
        self.assertEqual(descriptor.headers["cache-control"], "no-store")
        self.assertTrue(descriptor.json()["overlay"]["ready"])
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["cache-control"], "no-store")
        self.assertEqual(image.headers["content-type"], OVERLAY_MEDIA_TYPE)
        self.assertEqual(image.headers["x-voxelatlas-width"], "2")
        self.assertEqual(image.headers["x-voxelatlas-height"], "1")
        self.assertEqual(image.headers["x-voxelatlas-label-map-id"], LABEL_MAP_ID)
        self.assertEqual(len(image.content), 8)

    def test_frontend_composites_a_distinct_overlay_canvas_in_all_mpr_views(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
        module = (ROOT / "web" / "js" / "segmentation-overlay.js").read_text(
            encoding="utf-8"
        )

        for canvas_id in (
            "mprAxialSegmentationCanvas",
            "mprCoronalSegmentationCanvas",
            "mprSagittalSegmentationCanvas",
        ):
            self.assertIn(canvas_id, html)
        self.assertIn("segmentationOverlayToggle", html)
        self.assertIn("segmentationOverlayOpacity", html)
        self.assertIn("/api/studies/latest/segmentation-overlay", js)
        self.assertIn("renderSegmentationOverlayPlane", js)
        self.assertIn("drawSegmentationRgba", js)
        self.assertIn("pointer-events: none", css)
        self.assertIn("validateOverlayPayload", module)
        self.assertNotIn("clinical-grade", (html + js + module).lower())


if __name__ == "__main__":
    unittest.main()
