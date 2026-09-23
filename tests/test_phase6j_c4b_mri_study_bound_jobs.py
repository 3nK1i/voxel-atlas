"""C4B synthetic MRI job integration; never launches an MRI model or patient dataset."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.mri_job_binding import MRIStudyBoundProvider, _ARTIFACT
from voxelatlas.mri_runtime_qualification import MRI_MAPPING_JSON_SHA256
from voxelatlas.mri_worker_execution import MRIWorkerExecutor, MRIWorkerError
from voxelatlas.segmentation import (
    SegmentationDevice, SegmentationExecutionRequirements, SegmentationJobService,
    SegmentationModelDescriptor, SegmentationModelRegistry,
    SegmentationConflictError, SegmentationValidationError,
)
from test_phase5a_segmentation_architecture import write_canonical_volume

A = "a" * 32
B = "b" * 32


def make_descriptor():
    return SegmentationModelDescriptor(
        provider_id="totalsegmentator", provider_version="2.18.0", model_id="total_mr",
        model_version="2.18.0", display_name="Synthetic isolated MRI model",
        task="multi_structure", capabilities=("anatomical_segmentation",),
        supported_modalities=("MR",), available=True, availability_reason=None,
        execution=SegmentationExecutionRequirements(supported_devices=("cuda",)),
    )


class SyntheticMRIExecutor(MRIWorkerExecutor):
    def __init__(self):
        self.calls = []
        self.fail = None
        self.on_execute = None
        self.overrides = {}

    def execute(self, request, *, cancellation_check, explicit_model_authorization=False):
        self.calls.append((request, explicit_model_authorization))
        if self.on_execute:
            self.on_execute(request)
        if self.fail:
            raise MRIWorkerError(self.fail)
        if cancellation_check():
            raise MRIWorkerError("MRI worker cancelled")
        path = request.data_dir / "segmentation" / "jobs" / request.job_id / _ARTIFACT
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic-nifti-mask-not-a-patient-or-model-output")
        report = {
            "schema": 1, "task": "total_mr", "modality": "MR", "mode": request.mode,
            "model_version": "2.18.0", "model_mapping_sha256": MRI_MAPPING_JSON_SHA256,
            "weights_manifest_sha256": "a" * 64, "input_nifti_sha256": "b" * 64,
            "mask_nifti_sha256": sha256(path.read_bytes()).hexdigest(),
            "mask_artifact": _ARTIFACT, "nonzero_voxels": 1, "present_labels": [0, 50],
            "cuda": {"selected_index": request.device_index}, "clinical_validation": "not_claimed",
        }
        report.update(self.overrides)
        return report


class MRIBoundJobs(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name).resolve()
        study_dir, _ = write_canonical_volume(self.data, modality="MR")
        manifest_path = study_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["series"] = [{"series_instance_uid": "1.2.840.series", "modality": "MR",
                              "instance_count": 2,
                              "geometry": {"reconstruction_ready": True,
                                           "dimensions": [3, 4, 2]}}]
        manifest_path.write_text(json.dumps(manifest))
        self.executor = SyntheticMRIExecutor()
        self.model = make_descriptor()
        registry = SegmentationModelRegistry()
        self.jobs = SegmentationJobService(data_dir=self.data, registry=registry,
            device_discovery=lambda: (SegmentationDevice("cuda", "cuda:0", "Synthetic GPU", 0, 6144, 5120),))
        self.permit = False
        self.provider = MRIStudyBoundProvider(
            data_dir=self.data, job_service=self.jobs, descriptor=self.model,
            executor=self.executor, execution_permission=lambda: self.permit,
        )
        registry.register_provider(self.provider)

    def create(self, *, study_id=A, parameters=None):
        return self.jobs.create_job(provider_id="totalsegmentator", model_id="total_mr",
            device_request="auto", parameters={} if parameters is None else parameters,
            source_study_id=study_id)

    def test_parameter_contract_and_default_closed_execution(self):
        self.assertEqual(self.provider.validate_parameters({}), {"mode": "fastest"})
        for invalid in ({"task": "total"}, {"mode": "full"}, {"mode": True}, {"mode": "fastest", "a": 2}):
            with self.subTest(invalid=invalid), self.assertRaises(SegmentationValidationError):
                self.provider.validate_parameters(invalid)
        job = self.create()
        self.assertEqual(self.jobs.run_job(job["job_id"])["state"], "failed")
        self.assertEqual(self.executor.calls, [])
        self.assertFalse((self.data / "segmentation" / "jobs" / job["job_id"] / "provider").exists())

    def test_synthetic_job_completion_and_immutable_source_binding(self):
        self.permit = True  # isolated fake executor only; NEVER a real app configuration.
        job = self.create()
        # Changing which study is latest cannot retarget an already bound job.
        other = self.data / "studies" / B
        shutil.copytree(self.data / "studies" / A, other)
        new = json.loads((other / "manifest.json").read_text())
        new["study_id"] = B
        (other / "manifest.json").write_text(json.dumps(new))
        result = self.jobs.run_job(job["job_id"])
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["provenance"]["source_study_id"], A)
        self.assertEqual(result["provenance"]["source_series_uid"], "1.2.840.series")
        self.assertEqual(result["outcome"]["provider"]["class_count"], 50)
        self.assertEqual(result["outcome"]["clinical_validation"], "not_claimed")
        self.assertEqual(self.executor.calls[0][0].job_id, job["job_id"])
        self.assertTrue(self.executor.calls[0][1])
        self.assertEqual(self.jobs.get_job(job["job_id"])["terminal_provenance_sha256"],
                         result["terminal_provenance_sha256"])
        self.assertEqual(result["outcome"]["mask_artifact"], _ARTIFACT)
        self.assertNotEqual(result["outcome"]["mask_artifact"], "provider/totalsegmentator/output/labels.nii.gz")

    def test_changed_series_or_source_blocks_before_worker(self):
        self.permit = True
        job = self.create()
        manifest_path = self.data / "studies" / A / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["reconstruction_series_uid"] = "1.2.999"
        manifest_path.write_text(json.dumps(manifest))
        self.assertEqual(self.jobs.run_job(job["job_id"])["state"], "failed")
        self.assertEqual(self.executor.calls, [])
        self.assertFalse((self.data / "segmentation" / "jobs" / job["job_id"] / "provider").exists())

    def test_source_change_after_job_creation_is_rejected(self):
        self.permit = True
        job = self.create()
        (self.data / "studies" / A / "derived" / "volume.npy").write_bytes(b"changed synthetic source")
        with self.assertRaises(SegmentationConflictError):
            self.jobs.run_job(job["job_id"])
        self.assertEqual(self.jobs.get_job(job["job_id"])["state"], "queued")
        self.assertEqual(self.executor.calls, [])

    def test_worker_error_is_private_and_job_fails_closed(self):
        self.permit = True
        self.executor.fail = "/private/patient/secret.dcm"
        job = self.create()
        result = self.jobs.run_job(job["job_id"])
        self.assertEqual(result["state"], "failed")
        self.assertNotIn("patient", str(result))
        self.assertNotIn("secret", str(result))

    def test_cancellation_preempts_fake_worker_result(self):
        self.permit = True
        job = self.create()
        self.executor.on_execute = lambda request: self.jobs.cancel_job(request.job_id)
        result = self.jobs.run_job(job["job_id"])
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(self.jobs.get_job(job["job_id"])["state"], "cancelled")

    def test_corrupted_worker_result_never_marks_success(self):
        self.permit = True
        for override in ({"task": "total"}, {"present_labels": [0, 51]},
                         {"mask_nifti_sha256": "f" * 64}, {"mask_artifact": "../ct-mask.nii.gz"},
                         {"model_mapping_sha256": "0" * 64}):
            with self.subTest(override=override):
                self.executor.overrides = override
                job = self.create()
                result = self.jobs.run_job(job["job_id"])
                self.assertEqual(result["state"], "failed")
                self.assertEqual(result["outcome"]["code"], "provider_failure")

    def test_source_mutation_during_worker_execution_is_rejected(self):
        self.permit = True
        job = self.create()
        self.executor.on_execute = lambda request: request.source_npy.write_bytes(b"changed-after-bind")
        self.assertEqual(self.jobs.run_job(job["job_id"])["state"], "failed")

    def test_low_memory_mode_rejected_before_worker(self):
        self.permit = True
        job = self.create(parameters={"mode": "default"})
        self.assertEqual(self.jobs.run_job(job["job_id"])["state"], "failed")
        self.assertEqual(self.executor.calls, [])

    def test_ct_and_default_app_are_not_registered_with_this_adapter(self):
        self.assertEqual(self.jobs.list_models()[0]["model_id"], "total_mr")
        code = (ROOT / "backend" / "voxelatlas" / "app.py").read_text()
        self.assertNotIn("from .mri_job_binding import", code)
        self.assertNotIn("MRIStudyBoundProvider(", code)
        # Real app remains on C4A unavailable descriptor and unchanged CT provider.
        from voxelatlas.mri_provider_qualification import build_mri_model_descriptor
        planned = build_mri_model_descriptor(data_dir=self.data, python_executable=None)
        self.assertFalse(planned.available)
        self.assertEqual(planned.supported_modalities, ("MR",))


if __name__ == "__main__":
    unittest.main()
