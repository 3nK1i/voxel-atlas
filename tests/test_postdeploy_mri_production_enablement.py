"""Post-deployment MRI enablement regressions. Synthetic only; never runs TotalSegmentator."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from voxelatlas.app import _canonical_mri_worker_python, create_app
from voxelatlas.config import AppSettings
from voxelatlas.mri_provider_qualification import (
    MRIProviderQualification,
    build_mri_execution_descriptor,
)
from voxelatlas.mri_worker_execution import MRIWorkerError
from voxelatlas.segmentation import SegmentationUnavailableError
from voxelatlas.segmentation_workflow import SegmentationWorkflowService
from test_phase6j_c4b_mri_study_bound_jobs import MRIBoundJobs

ROOT = Path(__file__).resolve().parents[1]


class FakeLabelMaps:
    def __init__(self):
        self.descriptors: list[dict[str, object]] = []
        self.ct_import_calls: list[dict[str, object]] = []

    def list(self, **_kwargs):
        return list(self.descriptors)

    def import_succeeded_job(self, **kwargs):
        self.ct_import_calls.append(kwargs)
        raise AssertionError("MRI result bypassed QualifiedMRIResultImporter")


class FakeMRIImporter:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def import_current(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(label_map_id="map-" + "9" * 32)


class PostDeployMRIEnablementTests(unittest.TestCase):
    def setUp(self):
        fixture = MRIBoundJobs("test_synthetic_job_completion_and_immutable_source_binding")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.data = fixture.data
        self.jobs = fixture.jobs
        self.executor = fixture.executor
        fixture.permit = True  # synthetic executor only
        self.start_qualified = True
        self.maps = FakeLabelMaps()
        self.importer = FakeMRIImporter()
        self.workflow = SegmentationWorkflowService(
            data_dir=self.data,
            job_service=self.jobs,
            label_map_service=self.maps,
            python_executable=None,
            import_worker_script=ROOT / "scripts" / "phase5c_label_map_worker.py",
            mri_presentation_only=False,
            mri_python_executable="/synthetic/mri/python",
            mri_result_importer=self.importer,
            mri_start_qualification=lambda: self.start_qualified,
        )

    def test_app_canonicalizes_only_same_runtime_python_alias(self):
        runtime = self.data / "runtime" / "bin"
        runtime.mkdir(parents=True)
        real = runtime / "python3.13"
        real.write_text("synthetic executable", encoding="utf-8")
        real.chmod(0o755)
        alias = runtime / "python"
        alias.symlink_to(real.name)
        self.assertEqual(_canonical_mri_worker_python(str(alias)), real)

        outside = self.data / "outside-python"
        outside.write_text("synthetic executable", encoding="utf-8")
        outside.chmod(0o755)
        alias.unlink()
        alias.symlink_to(outside)
        with self.assertRaises(MRIWorkerError):
            _canonical_mri_worker_python(str(alias))

    def test_normal_app_wires_executable_mri_only_after_startup_qualification(self):
        runtime = self.data / "runtime" / "bin"
        runtime.mkdir(parents=True, exist_ok=True)
        python = runtime / "python"
        python.write_text("synthetic executable", encoding="utf-8")
        python.chmod(0o755)
        settings = AppSettings(
            environment="test", session_secret="x" * 48, secure_cookies=False,
            session_cookie_name="va_hotfix", allowed_hosts=("localhost", "127.0.0.1"),
            data_dir=self.data, max_upload_mib=512, auth_username=None, auth_password_hash=None,
            session_ttl_minutes=60, mri_worker_python=str(python),
        )
        qualified = MRIProviderQualification(
            "study_binding_pending", "qualified", runtime_qualified=True, weights_qualified=True,
        )
        with patch("voxelatlas.app.qualify_mri_provider", return_value=qualified):
            app = create_app(settings=settings)
        descriptor = app.state.segmentation_service.registry.descriptor("totalsegmentator", "total_mr")
        self.assertTrue(descriptor.available)
        self.assertFalse(app.state.segmentation_workflow_service.mri_presentation_only)
        self.assertIsNotNone(app.state.segmentation_workflow_service.mri_result_importer)
        self.assertIsNotNone(app.state.segmentation_workflow_service.mri_start_qualification)
        self.assertEqual(app.state.segmentation_workflow_service.mri_python_executable, str(python))

    def test_execution_descriptor_requires_runtime_and_sealed_weights(self):
        qualified = MRIProviderQualification(
            "study_binding_pending", "qualified", runtime_qualified=True, weights_qualified=True,
        )
        descriptor = build_mri_execution_descriptor(qualification=qualified)
        self.assertTrue(descriptor.available)
        self.assertEqual(descriptor.model_id, "total_mr")
        self.assertEqual(descriptor.supported_modalities, ("MR",))
        for invalid in (
            MRIProviderQualification("runtime", "no"),
            MRIProviderQualification("weights", "no", runtime_qualified=True),
            MRIProviderQualification("authorized", "no", runtime_qualified=True,
                                     weights_qualified=True, execution_authorized=True),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build_mri_execution_descriptor(qualification=invalid)

    def test_start_requalifies_before_job_creation_and_fails_closed(self):
        self.assertTrue(self.workflow.snapshot_latest()["can_start"])
        self.start_qualified = False
        with self.assertRaises(SegmentationUnavailableError):
            self.workflow.request_start()
        self.assertEqual(self.jobs.list_jobs(), [])
        self.assertEqual(self.executor.calls, [])

    def test_normal_start_retains_exact_mri_study_and_series_binding(self):
        started = self.workflow.request_start()
        self.assertIsNotNone(started.background_job_id)
        job = self.jobs.get_job(started.background_job_id)
        provenance = job["provenance"]
        source = self.jobs.sources.latest()
        self.assertEqual(provenance["source_study_id"], source.study_id)
        self.assertEqual(provenance["source_study_instance_uid"], source.study_instance_uid)
        self.assertEqual(provenance["source_series_uid"], source.source_series_uid)
        self.assertEqual(provenance["source_modality"], "MR")
        self.assertEqual(provenance["parameters"], {"mode": "fastest"})
        self.assertEqual(provenance["selected_device"]["selector"], "cuda:0")

    def test_progress_and_cancellation_remain_on_study_bound_job(self):
        started = self.workflow.request_start()
        snap = self.workflow.snapshot_latest()
        self.assertEqual(snap["job_id"], started.background_job_id)
        self.assertEqual(snap["state"], "queued")
        self.assertTrue(snap["can_cancel"])
        cancelled = self.workflow.cancel_latest()
        self.assertEqual(cancelled["state"], "cancelled")
        self.assertEqual(self.jobs.get_job(started.background_job_id)["state"], "cancelled")
        self.assertEqual(self.executor.calls, [])

    def test_success_uses_qualified_mri_importer_not_generic_ct_import(self):
        started = self.workflow.request_start()
        self.workflow.execute_requested(started.background_job_id)
        job = self.jobs.get_job(started.background_job_id)
        self.assertEqual(job["state"], "succeeded")
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(len(self.importer.calls), 1)
        self.assertEqual(self.importer.calls[0]["python_executable"], "/synthetic/mri/python")
        self.assertEqual(self.maps.ct_import_calls, [])

    def test_existing_exact_mri_map_is_reused_without_model_execution(self):
        started = self.workflow.request_start()
        self.jobs.run_job(started.background_job_id)
        source = self.jobs.sources.latest()
        job = self.jobs.get_job(started.background_job_id)
        self.maps.descriptors = [{
            "state": "ready",
            "label_map_id": "map-" + "8" * 32,
            "segmentation_job_id": job["job_id"],
            "source_study_id": source.study_id,
            "source_study_instance_uid": source.study_instance_uid,
            "source_series_uid": source.source_series_uid,
            "source_modality": "MR",
            "source_volume_descriptor_sha256": source.descriptor_sha256,
            "source_volume_artifact_sha256": source.artifact_sha256,
            "segmentation_terminal_provenance_sha256": job["terminal_provenance_sha256"],
            "provider_id": "totalsegmentator",
            "model_id": "total_mr",
            "task": "total_mr",
            "class_count": 50,
            "clinical_validation": "not_claimed",
            "present_labels": [0, 50],
        }]
        calls_before = len(self.executor.calls)
        snap = self.workflow.snapshot_latest()
        self.assertEqual(snap["state"], "available")
        self.assertTrue(snap["can_use"])
        self.assertFalse(snap["can_start"])
        self.assertTrue(snap["mri_label_map_ready"])
        reused = self.workflow.request_start()
        self.assertIsNone(reused.background_job_id)
        self.assertEqual(len(self.executor.calls), calls_before)

    def test_mismatched_persisted_mri_map_is_never_reused(self):
        started = self.workflow.request_start()
        self.jobs.run_job(started.background_job_id)
        source = self.jobs.sources.latest()
        job = self.jobs.get_job(started.background_job_id)
        self.maps.descriptors = [{
            "state": "ready", "label_map_id": "map-" + "7" * 32,
            "segmentation_job_id": job["job_id"], "source_study_id": source.study_id,
            "source_study_instance_uid": source.study_instance_uid,
            "source_series_uid": "wrong.series", "source_modality": "MR",
            "source_volume_descriptor_sha256": source.descriptor_sha256,
            "source_volume_artifact_sha256": source.artifact_sha256,
            "segmentation_terminal_provenance_sha256": job["terminal_provenance_sha256"],
            "provider_id": "totalsegmentator", "model_id": "total_mr", "task": "total_mr",
            "class_count": 50, "clinical_validation": "not_claimed", "present_labels": [0, 50],
        }]
        snap = self.workflow.snapshot_latest()
        self.assertEqual(snap["state"], "output_ready")
        self.assertFalse(snap["can_use"])
        self.assertIsNone(snap["label_map_id"])


if __name__ == "__main__":
    unittest.main()
