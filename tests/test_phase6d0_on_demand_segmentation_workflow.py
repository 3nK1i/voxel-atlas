from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FakeSources:
    def __init__(self, study_id: str = "a" * 32, modality: str = "CT") -> None:
        self.source = SimpleNamespace(study_id=study_id, modality=modality)

    def latest(self):
        return self.source


class FakeJobService:
    def __init__(self, *, modality: str = "CT", available: bool = True) -> None:
        self.sources = FakeSources(modality=modality)
        self.jobs: list[dict[str, object]] = []
        self.create_calls = 0
        self.available = available

    def list_models(self):
        return [{
            "provider_id": "totalsegmentator",
            "model_id": "total",
            "display_name": "TotalSegmentator total task",
            "supported_modalities": ["CT"],
            "available": self.available,
            "availability_reason": None if self.available else "Runtime not configured",
        }]

    def list_jobs(self):
        return list(self.jobs)

    def create_job(self, *, provider_id, model_id, device_request, parameters, source_study_id):
        self.create_calls += 1
        job = {
            "job_id": f"seg-{self.create_calls:032x}",
            "state": "queued",
            "progress": {"stage": "queued", "percent": 0.0, "message": "Queued"},
            "provenance": {
                "source_study_id": source_study_id,
                "source_modality": self.sources.source.modality,
                "provider_id": provider_id,
                "model_id": model_id,
                "selected_device": {"selector": "cuda:0", "name": "GPU"},
            },
        }
        self.jobs.insert(0, job)
        return dict(job)

    def get_job(self, job_id):
        return next(dict(item) for item in self.jobs if item["job_id"] == job_id)

    def run_job(self, job_id):
        job = next(item for item in self.jobs if item["job_id"] == job_id)
        job["state"] = "succeeded"
        job["progress"] = {"stage": "complete", "percent": 100.0, "message": "Provider execution completed"}
        job["outcome"] = {"mask_nifti_sha256": "b" * 64}
        return dict(job)

    def cancel_job(self, job_id):
        job = next(item for item in self.jobs if item["job_id"] == job_id)
        job["state"] = "cancelled"
        return dict(job)


class FakeLabelMaps:
    def __init__(self) -> None:
        self.maps: list[dict[str, object]] = []
        self.import_calls = 0

    def list(self, *, study_id=None):
        return [item for item in self.maps if study_id is None or item["source_study_id"] == study_id]

    def import_succeeded_job(self, *, job_id, python_executable, worker_script, timeout_seconds=1800.0):
        del python_executable, worker_script, timeout_seconds
        self.import_calls += 1
        descriptor = {
            "label_map_id": "map-" + "c" * 32,
            "source_study_id": "a" * 32,
            "segmentation_job_id": job_id,
            "provider_id": "totalsegmentator",
            "model_id": "total",
            "present_labels": [0, 1, 2],
        }
        self.maps.insert(0, descriptor)
        return descriptor


class Phase6D0OnDemandSegmentationWorkflowTests(unittest.TestCase):
    def workflow(self, jobs=None, maps=None):
        from voxelatlas.segmentation_workflow import SegmentationWorkflowService

        return SegmentationWorkflowService(
            data_dir=ROOT / "data",
            job_service=jobs or FakeJobService(),
            label_map_service=maps or FakeLabelMaps(),
            python_executable="/opt/voxelatlas-segmentation/bin/python",
            import_worker_script=ROOT / "scripts" / "phase5c_label_map_worker.py",
        )

    def test_existing_valid_label_map_is_reused_only_after_explicit_request(self) -> None:
        jobs = FakeJobService()
        maps = FakeLabelMaps()
        maps.maps.append({
            "label_map_id": "map-" + "d" * 32,
            "source_study_id": "a" * 32,
            "segmentation_job_id": "seg-" + "e" * 32,
            "provider_id": "totalsegmentator",
            "model_id": "total",
            "present_labels": [0, 1, 2, 3],
        })
        workflow = self.workflow(jobs, maps)

        before = workflow.snapshot_latest()
        requested = workflow.request_start()

        self.assertEqual(before["state"], "available")
        self.assertTrue(before["can_use"])
        self.assertEqual(requested.workflow["state"], "available")
        self.assertIsNone(requested.background_job_id)
        self.assertEqual(jobs.create_calls, 0)

    def test_start_is_explicit_and_duplicate_active_jobs_are_not_created(self) -> None:
        jobs = FakeJobService()
        workflow = self.workflow(jobs, FakeLabelMaps())

        before = workflow.snapshot_latest()
        first = workflow.request_start()
        second = workflow.request_start()

        self.assertEqual(before["state"], "idle")
        self.assertEqual(jobs.create_calls, 1)
        self.assertEqual(first.workflow["state"], "queued")
        self.assertIsNotNone(first.background_job_id)
        self.assertIsNone(second.background_job_id)
        self.assertEqual(second.workflow["job_id"], first.workflow["job_id"])

    def test_background_execution_imports_canonical_label_map_then_becomes_available(self) -> None:
        jobs = FakeJobService()
        maps = FakeLabelMaps()
        workflow = self.workflow(jobs, maps)
        request = workflow.request_start()

        workflow.execute_requested(str(request.background_job_id))
        snapshot = workflow.snapshot_latest()

        self.assertEqual(maps.import_calls, 1)
        self.assertEqual(snapshot["state"], "available")
        self.assertEqual(snapshot["label_map_id"], "map-" + "c" * 32)
        self.assertEqual(snapshot["present_label_count"], 2)

    def test_ct_provider_is_modality_gated_and_mri_is_not_silently_started(self) -> None:
        from voxelatlas.segmentation import SegmentationUnavailableError

        jobs = FakeJobService(modality="MR")
        workflow = self.workflow(jobs, FakeLabelMaps())
        snapshot = workflow.snapshot_latest()

        # Since 6J-B1, absent MRI provider is "unavailable", not CT "unsupported".
        self.assertEqual(snapshot["state"], "unavailable")
        self.assertFalse(snapshot["can_start"])
        with self.assertRaises(SegmentationUnavailableError):
            workflow.request_start()
        self.assertEqual(jobs.create_calls, 0)

    def test_frontend_loads_patient_visualization_before_segmentation_and_exposes_user_action(self) -> None:
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        panel = (ROOT / "web/js/segmentation-workflow-panel.js").read_text(encoding="utf-8")

        ensure_mpr = app[app.index("async function ensureMprReady"):app.index("function setMprCrosshairFromPointer")]
        self.assertNotIn("refreshSegmentationOverlayDescriptor", ensure_mpr)
        self.assertIn("await ensureVolumeRenderingFoundation();", app)
        self.assertIn("refreshSegmentationWorkflowStatus", app)
        self.assertIn("Start Segmentation", index)
        self.assertIn("Use Segmentation", panel)
        self.assertIn("Cancel", index)
        self.assertIn("Retry", panel)
        self.assertIn("segmentationWorkflowProgress", index)
        self.assertNotIn("setInterval", panel)

    def test_runtime_is_explicitly_configured_and_heavy_provider_is_not_imported_in_frontend(self) -> None:
        config = (ROOT / "backend/voxelatlas/config.py").read_text(encoding="utf-8")
        app = (ROOT / "backend/voxelatlas/app.py").read_text(encoding="utf-8")
        frontend = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        self.assertIn("VOXELATLAS_SEGMENTATION_PYTHON", config)
        self.assertIn("TotalSegmentatorProvider", app)
        self.assertIn("SegmentationWorkflowService", app)
        self.assertNotIn("totalsegmentator_execution", frontend.lower())
        self.assertNotIn("import torch", frontend.lower())

    def test_http_workflow_contract_is_authenticated_no_store_and_background_safe(self) -> None:
        import tempfile
        from fastapi.testclient import TestClient
        from voxelatlas import config
        from voxelatlas.app import create_app
        from voxelatlas.passwords import hash_password
        from voxelatlas.segmentation_workflow import SegmentationWorkflowStart

        class FakeWorkflow:
            def __init__(self):
                self.snapshot_calls = 0
                self.start_calls = 0
                self.cancel_calls = 0

            def snapshot_latest(self):
                self.snapshot_calls += 1
                return {
                    "schema_version": 1, "study_id": "a" * 32, "modality": "CT",
                    "provider_id": "totalsegmentator", "model_id": "total",
                    "state": "idle", "message": "Segmentation has not been started",
                    "can_start": True, "can_cancel": False, "can_use": False,
                    "label_map_id": None, "present_label_count": 0, "job_id": None,
                    "progress": None, "provider_available": True, "provider_reason": None,
                    "clinical_validation": "not_claimed",
                }

            def request_start(self):
                self.start_calls += 1
                workflow = self.snapshot_latest() | {
                    "state": "available", "can_start": False, "can_use": True,
                    "label_map_id": "map-" + "f" * 32, "present_label_count": 49,
                    "message": "Existing segmentation is ready to use",
                }
                return SegmentationWorkflowStart(workflow)

            def cancel_latest(self):
                self.cancel_calls += 1
                return self.snapshot_latest() | {"state": "cancelled", "message": "Segmentation cancelled"}

        with tempfile.TemporaryDirectory() as tmp:
            workflow = FakeWorkflow()
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
            with TestClient(create_app(settings=settings, segmentation_workflow_service=workflow)) as client:
                denied = client.get("/api/studies/latest/segmentation-workflow")
                client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                status_response = client.get("/api/studies/latest/segmentation-workflow")
                start_response = client.post("/api/studies/latest/segmentation-workflow/start")
                cancel_response = client.post("/api/studies/latest/segmentation-workflow/cancel")

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(cancel_response.status_code, 200)
        for response in (status_response, start_response, cancel_response):
            self.assertEqual(response.headers.get("cache-control"), "no-store")
        self.assertEqual(start_response.json()["workflow"]["label_map_id"], "map-" + "f" * 32)
        self.assertEqual(workflow.start_calls, 1)
        self.assertEqual(workflow.cancel_calls, 1)

    def test_config_parses_isolated_segmentation_runtime_without_changing_surface_runtime(self) -> None:
        from voxelatlas import config

        settings = config.load_settings({
            "VOXELATLAS_ENV": "development",
            "VOXELATLAS_SEGMENTATION_PYTHON": "/opt/seg/bin/python",
            "VOXELATLAS_SURFACE_PYTHON": "/opt/surface/bin/python",
        })
        self.assertEqual(settings.segmentation_worker_python, "/opt/seg/bin/python")
        self.assertEqual(settings.surface_worker_python, "/opt/surface/bin/python")


if __name__ == "__main__":
    unittest.main()
