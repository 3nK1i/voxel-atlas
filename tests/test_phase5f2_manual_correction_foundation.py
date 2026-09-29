from __future__ import annotations

from datetime import datetime, timezone
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

from voxelatlas.segmentation import (  # noqa: E402
    SegmentationConflictError,
    SegmentationValidationError,
)
from voxelatlas.segmentation_corrections import (  # noqa: E402
    SegmentationCorrectionService,
)
from voxelatlas import config  # noqa: E402


LABEL_MAP_ID = "map-0123456789abcdef0123456789abcdef"
STUDY_ID = "0123456789abcdef0123456789abcdef"
SESSION_ID = "corr-11111111111111111111111111111111"


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


def make_service(root: Path) -> tuple[SegmentationCorrectionService, Path]:
    labels = np.zeros((4, 5, 6), dtype=np.uint16)
    labels[0:3, 1:4, 2:5] = 7
    artifact_root = root / "segmentation" / "label-maps" / LABEL_MAP_ID
    artifact_root.mkdir(parents=True)
    artifact_path = artifact_root / "labels.npy"
    np.save(artifact_path, labels, allow_pickle=False)
    artifact_sha256 = sha256(artifact_path.read_bytes()).hexdigest()
    descriptor = {
        "label_map_id": LABEL_MAP_ID,
        "state": "ready",
        "source_study_id": STUDY_ID,
        "coordinate_system": "patient_lps",
        "artifact_format": "npy",
        "artifact_sha256": artifact_sha256,
        "shape": [4, 5, 6],
        "dtype": "uint16",
        "present_labels": [0, 7],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 2.0, 10.0],
            [0.0, 3.0, 0.0, 20.0],
            [4.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }
    service = SegmentationCorrectionService(
        data_dir=root,
        study_repository=FakeStudyRepository(),
        label_map_service=FakeLabelMapService(descriptor),
        clock=lambda: datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc),
        token_factory=lambda: "1" * 32,
    )
    return service, artifact_path


class Phase5F2CorrectionServiceTests(unittest.TestCase):
    def test_draft_actions_are_sealed_reversible_and_source_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, artifact = make_service(Path(tmp))
            source_before = sha256(artifact.read_bytes()).hexdigest()
            session = service.create(LABEL_MAP_ID)
            session = service.add_action(
                SESSION_ID,
                kind="exclude",
                label_id=7,
                center_lps_mm=[14.0, 23.0, 34.0],
                radius_mm=3.0,
                plane="axial",
            )
            revision = session["revision_sha256"]
            undone = service.undo(SESSION_ID)
            redone = service.redo(SESSION_ID)

            self.assertEqual(session["action_count"], 1)
            self.assertEqual(undone["applied_action_count"], 0)
            self.assertTrue(undone["can_redo"])
            self.assertEqual(redone["applied_action_count"], 1)
            self.assertEqual(redone["revision_sha256"], revision)
            self.assertEqual(source_before, sha256(artifact.read_bytes()).hexdigest())
            self.assertEqual(redone["source_label_map"], "immutable")
            self.assertEqual(redone["materialization"], "not_applied")
            self.assertNotIn(str(Path(tmp)), str(redone))
            self.assertEqual(service.list(label_map_id=LABEL_MAP_ID)[0]["session_id"], SESSION_ID)

    def test_new_action_after_undo_truncates_redo_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_service(Path(tmp))
            service.create(LABEL_MAP_ID)
            for kind in ("review", "exclude"):
                service.add_action(
                    SESSION_ID,
                    kind=kind,
                    label_id=7,
                    center_lps_mm=[14.0, 23.0, 34.0],
                    radius_mm=2.0,
                    plane="coronal",
                )
            service.undo(SESSION_ID)
            replaced = service.add_action(
                SESSION_ID,
                kind="include",
                label_id=7,
                center_lps_mm=[16.0, 26.0, 38.0],
                radius_mm=1.5,
                plane="sagittal",
            )

            self.assertEqual(replaced["action_count"], 2)
            self.assertEqual(replaced["actions"][-1]["kind"], "include")
            self.assertFalse(replaced["can_redo"])

    def test_invalid_geometry_binding_and_discarded_edits_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_service(Path(tmp))
            service.create(LABEL_MAP_ID)
            invalid = (
                {"kind": "paint", "label_id": 7, "center_lps_mm": [14, 23, 34], "radius_mm": 3, "plane": "axial"},
                {"kind": "review", "label_id": 8, "center_lps_mm": [14, 23, 34], "radius_mm": 3, "plane": "axial"},
                {"kind": "review", "label_id": 7, "center_lps_mm": [999, 999, 999], "radius_mm": 3, "plane": "axial"},
                {"kind": "review", "label_id": 7, "center_lps_mm": [14, 23, 34], "radius_mm": 30, "plane": "axial"},
            )
            for action in invalid:
                with self.subTest(action=action):
                    with self.assertRaises(SegmentationValidationError):
                        service.add_action(SESSION_ID, **action)
            service.discard(SESSION_ID)
            with self.assertRaises(SegmentationConflictError):
                service.add_action(
                    SESSION_ID,
                    kind="review",
                    label_id=7,
                    center_lps_mm=[14, 23, 34],
                    radius_mm=3,
                    plane="axial",
                )

    def test_manifest_tampering_and_cross_study_use_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_service(Path(tmp))
            service.create(LABEL_MAP_ID)
            path = Path(tmp) / "segmentation" / "correction-sessions" / SESSION_ID / "manifest.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["applied_action_count"] = 1
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(SegmentationValidationError):
                service.get(SESSION_ID)

            other, _ = make_service(Path(tmp) / "other")
            other.repository.study_id = "f" * 32
            with self.assertRaises(SegmentationValidationError):
                other.create(LABEL_MAP_ID)

    def test_quality_report_flags_boundary_and_nonclinical_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_service(Path(tmp))
            report = service.quality_report(label_map_id=LABEL_MAP_ID, label_id=7)

        codes = {warning["code"] for warning in report["warnings"]}
        self.assertEqual(report["voxel_count"], 27)
        self.assertTrue(report["touches_volume_boundary"])
        self.assertIn("touches_volume_boundary", codes)
        self.assertIn("clinical_validation_not_claimed", codes)
        self.assertIn("draft_not_materialized", codes)
        self.assertEqual(report["source_label_map"], "immutable")


class StubCorrectionService:
    def quality_report(self, **kwargs):
        return {"label_id": kwargs["label_id"], "warnings": [], "clinical_validation": "not_claimed"}

    def create(self, label_map_id):
        return {"session_id": SESSION_ID, "label_map_id": label_map_id, "state": "draft"}

    def get(self, session_id):
        return {"session_id": session_id, "state": "draft"}

    def list(self, *, label_map_id):
        return [{"session_id": SESSION_ID, "label_map_id": label_map_id, "state": "draft"}]

    def add_action(self, session_id, **kwargs):
        return {"session_id": session_id, "state": "draft", "action": kwargs}

    def undo(self, session_id):
        return {"session_id": session_id, "applied_action_count": 0}

    def redo(self, session_id):
        return {"session_id": session_id, "applied_action_count": 1}

    def discard(self, session_id):
        return {"session_id": session_id, "state": "discarded"}


class Phase5F2HttpAndUiTests(unittest.TestCase):
    def test_authenticated_http_contracts_are_no_store(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from voxelatlas.app import create_app
            from voxelatlas.passwords import hash_password
        except (ImportError, RuntimeError) as exc:
            self.skipTest(f"FastAPI test client unavailable: {exc}")
        with tempfile.TemporaryDirectory() as tmp:
            settings = config.AppSettings(
                environment="test",
                session_secret="x" * 48,
                secure_cookies=False,
                allowed_hosts=("testserver", "127.0.0.1", "localhost"),
                session_cookie_name="voxelatlas_session",
                data_dir=Path(tmp),
                max_upload_mib=512,
                auth_username="engineer",
                auth_password_hash=hash_password("correct horse battery staple"),
                session_ttl_minutes=60,
            )
            with TestClient(create_app(settings=settings, segmentation_correction_service=StubCorrectionService())) as client:
                denied = client.post("/api/segmentation/correction-sessions", json={"label_map_id": LABEL_MAP_ID})
                client.post("/api/auth/login", json={"username": "engineer", "password": "correct horse battery staple"})
                created = client.post("/api/segmentation/correction-sessions", json={"label_map_id": LABEL_MAP_ID})
                listed = client.get(f"/api/segmentation/correction-sessions?label_map_id={LABEL_MAP_ID}")
                quality = client.get(f"/api/studies/latest/segmentation-quality/7?label_map_id={LABEL_MAP_ID}")
                action = client.post(
                    f"/api/segmentation/correction-sessions/{SESSION_ID}/actions",
                    json={"kind": "review", "label_id": 7, "center_lps_mm": [1, 2, 3], "radius_mm": 3, "plane": "axial"},
                )
                undo = client.post(f"/api/segmentation/correction-sessions/{SESSION_ID}/undo")
                redo = client.post(f"/api/segmentation/correction-sessions/{SESSION_ID}/redo")
                discard = client.post(f"/api/segmentation/correction-sessions/{SESSION_ID}/discard")

        self.assertEqual(denied.status_code, 401)
        for response in (created, listed, quality, action, undo, redo, discard):
            self.assertEqual(response.status_code, 201 if response is created else 200)
            self.assertEqual(response.headers["cache-control"], "no-store")

    def test_workspace_exposes_correction_and_warning_controls(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        module = (ROOT / "web" / "js" / "segmentation-correction-panel.js").read_text(encoding="utf-8")
        for control_id in (
            "segmentationCorrectionPanel",
            "segmentationCorrectionStart",
            "segmentationCorrectionKind",
            "segmentationCorrectionRadius",
            "segmentationCorrectionApply",
            "segmentationCorrectionUndo",
            "segmentationCorrectionRedo",
            "segmentationCorrectionDiscard",
            "segmentationQualityWarnings",
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("SegmentationCorrectionPanel", module)
        self.assertIn("getCrosshair", app)
        self.assertIn("activePlane", app)
        self.assertIn("phase5f2-r1", html)
        self.assertNotIn("clinical-grade", (html + app + module).lower())


if __name__ == "__main__":
    unittest.main()
