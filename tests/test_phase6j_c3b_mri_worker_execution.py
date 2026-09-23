"""Synthetic-only MRI supervisor contract; never calls the real model."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from voxelatlas.mri_task_contract import TOTAL_SEGMENTATOR_MRI_STRUCTURES
from voxelatlas.mri_worker_execution import (MRIWorkerExecutor, MRIWorkerError, MRIWorkerRequest,
                                             _valid_inspection, _valid_provider, mri_command)
from voxelatlas.totalsegmentator_execution import (ProcessExecutionError, ProcessExecutionResult,
                                                   SupervisedProcessRunner)

SHA = "a" * 64
AFFINE = [[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


class FakeRunner:
    def __init__(self, root: Path, *, fail: str = "", total_mib: int = 5744):
        self.commands = []
        self.root = root
        self.fail = fail
        self.total_mib = total_mib

    def run(self, command, *, environment, working_directory, timeout_seconds,
            cancellation_check, log_prefix, max_log_bytes):
        self.commands.append((tuple(command), dict(environment), log_prefix))
        if log_prefix == self.fail:
            raise ProcessExecutionError("nonzero_exit", "private-model-path")
        if cancellation_check():
            raise ProcessExecutionError("cancelled", "private-study")
        parent = working_directory.parent
        stdout = working_directory / (log_prefix + ".stdout.log")
        stderr = working_directory / (log_prefix + ".stderr.log")
        if log_prefix == "cuda":
            payload = {"schema": 1, "index": 0, "total_mib": self.total_mib,
                       "free_mib": 5000, "test_sum": 65536.}
        elif log_prefix == "export":
            input_path = parent / "input" / "canonical-mri.nii.gz"
            input_path.write_bytes(b"fake-input-only")
            request = self.request
            payload = {"schema_version": 1, "operation": "export", "task": "total_mr",
                       "modality": "MR", "shape": [2, 3, 4], "dtype": "float32",
                       "axis_order": ["slice", "row", "column"],
                       "source_artifact_sha256": request.source_sha256,
                       "source_descriptor_sha256": request.descriptor_sha256,
                       "output_nifti_sha256": sha256(input_path.read_bytes()).hexdigest()}
        elif log_prefix == "model":
            mask_path = parent / "output" / "labels.nii.gz"
            mask_path.write_bytes(b"fake-mask-only")
            input_path = parent / "input" / "canonical-mri.nii.gz"
            mode = self.request.mode
            payload = {"totalsegmentator_version": "2.18.0", "task": "total_mr", "modality": "MR",
                       "device": "gpu", "multilabel": True, "output_type": "nifti", "roi_subset": None,
                       "input": str(input_path), "output": str(mask_path), "num_classes": 50,
                       "classes": {str(k): v for k, v in TOTAL_SEGMENTATOR_MRI_STRUCTURES.items()},
                       "fast": mode == "fast", "fastest": mode == "fastest", "runtime_seconds": 1.}
            (parent / "output" / "provider-report.json").write_text(json.dumps(payload))
        else:
            input_path = parent / "input" / "canonical-mri.nii.gz"
            mask_path = parent / "output" / "labels.nii.gz"
            payload = {"schema_version": 1, "operation": "inspect", "task": "total_mr",
                       "modality": "MR", "shape": [2, 3, 4], "affine_matches_input": True,
                       "integer_labels": True,
                       "input_nifti_sha256": sha256(input_path.read_bytes()).hexdigest(),
                       "mask_nifti_sha256": sha256(mask_path.read_bytes()).hexdigest(),
                       "nonzero_voxels": 1, "present_labels": [0, 50],
                       "minimum_label": 0, "maximum_label": 50}
        stdout.write_text(json.dumps(payload) + "\n")
        stderr.write_text("")
        return ProcessExecutionResult(0, 0.1, stdout, stderr)


class MRIWorkerContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        source_dir = self.data / "samples"
        source_dir.mkdir()
        self.source = source_dir / "canonical.npy"
        self.source.write_bytes(b"synthetic-only-source")
        self.descriptor = source_dir / "descriptor.json"
        self.descriptor.write_text(json.dumps({"ready": True, "modality": "MR", "dtype": "float32",
                     "axis_order": ["slice", "row", "column"], "shape": [2, 3, 4],
                     "array_index_to_patient_lps": AFFINE}))
        self.py = self.root / "mri-python"
        self.py.write_text("#! /bin/sh\nexit 0\n")
        self.py.chmod(0o755)
        self.bridge = self.root / "mri-bridge.py"
        self.bridge.write_text("#synthetic\n")
        self.request = MRIWorkerRequest(self.data, "syntheticjob123", self.source, self.descriptor,
                                        sha256(self.source.read_bytes()).hexdigest(),
                                        sha256(canonical(json.loads(self.descriptor.read_text()))).hexdigest(),
                                        0, "fastest")
        self.fake = FakeRunner(self.root)
        self.fake.request = self.request
        self.executor = MRIWorkerExecutor(python_executable=self.py, bridge_script=self.bridge,
                     process_runner=self.fake, runtime_check=lambda _: True,
                     installed_mapping_check=lambda _: True,
                     weights_check=lambda _: {"task": "total_mr", "manifest_sha256": SHA,
                              "mode_ids": {"default": [850, 851], "fast": [852], "fastest": [853]}})

    def test_no_inference_by_default_and_no_artifact(self):
        with self.assertRaisesRegex(MRIWorkerError, "not authorized"):
            self.executor.execute(self.request, cancellation_check=lambda: False)
        self.assertFalse((self.data / "segmentation").exists())
        self.assertEqual(self.fake.commands, [])

    def test_supervised_four_stage_fake_execution_and_private_binding(self):
        report = self.executor.execute(self.request, cancellation_check=lambda: False,
                                       explicit_model_authorization=True)
        self.assertEqual([cmd[2] for cmd in self.fake.commands], ["cuda", "export", "model", "inspect"])
        self.assertEqual(report["task"], "total_mr")
        self.assertEqual(report["present_labels"], [0, 50])
        self.assertEqual(report["clinical_validation"], "not_claimed")
        self.assertIn("--fastest", self.fake.commands[2][0])
        self.assertNotIn("--task\x00total", self.fake.commands[2][0])
        self.assertEqual(self.fake.commands[2][1]["CUDA_VISIBLE_DEVICES"], "0")
        self.assertIn("totalsegmentator-mri", report["mask_artifact"])
        with self.assertRaisesRegex(MRIWorkerError, "workspace already exists"):
            self.executor.execute(self.request, cancellation_check=lambda: False,
                                  explicit_model_authorization=True)

    def test_worker_errors_do_not_leak_private_details(self):
        self.fake.fail = "model"
        with self.assertRaisesRegex(MRIWorkerError, "process failed") as caught:
            self.executor.execute(self.request, cancellation_check=lambda: False,
                                  explicit_model_authorization=True)
        self.assertNotIn("private-model-path", str(caught.exception))

    def test_reject_ct_changed_source_wrong_mode_and_symlink(self):
        payload = json.loads(self.descriptor.read_text())
        payload["modality"] = "CT"
        self.descriptor.write_text(json.dumps(payload))
        changed = MRIWorkerRequest(self.data, self.request.job_id, self.source, self.descriptor,
                                   self.request.source_sha256,
                                   sha256(canonical(payload)).hexdigest(), 0, "fastest")
        with self.assertRaisesRegex(MRIWorkerError, "qualification"):
            self.executor.execute(changed, cancellation_check=lambda: False,
                                  explicit_model_authorization=True)
        self.assertEqual(self.fake.commands, [])
        alias = self.root / "symlink"
        alias.symlink_to(self.py)
        with self.assertRaises(MRIWorkerError):
            mri_command(python_executable=alias,
                        input_nifti=self.root / "input.nii.gz",
                        mask_nifti=self.root / "output.nii.gz",
                        report_json=self.root / "report.json", device_index=0, mode="fastest")

    def test_low_memory_is_fastest_only_and_fails_before_export(self):
        from dataclasses import replace
        request = replace(self.request, mode="default")
        self.fake.request = request
        with self.assertRaisesRegex(MRIWorkerError, "6 mm trial"):
            self.executor.execute(request, cancellation_check=lambda: False,
                                  explicit_model_authorization=True)
        self.assertEqual([cmd[2] for cmd in self.fake.commands], ["cuda"])

    def test_mask_and_provider_report_validation_reject_bad_values(self):
        inp = self.root / "input.nii.gz"
        out = self.root / "mask.nii.gz"
        inp.write_bytes(b"input")
        out.write_bytes(b"mask")
        invalid = {"schema_version": 1, "operation": "inspect", "task": "total_mr",
                   "modality": "MR", "shape": [2, 3, 4], "affine_matches_input": True,
                   "integer_labels": True, "input_nifti_sha256": sha256(b"input").hexdigest(),
                   "mask_nifti_sha256": sha256(b"mask").hexdigest(),
                   "nonzero_voxels": 1, "present_labels": [0, 51], "minimum_label": 0,
                   "maximum_label": 51}
        with self.assertRaises(MRIWorkerError):
            _valid_inspection(invalid, (2, 3, 4), inp, out)
        with self.assertRaises(MRIWorkerError):
            _valid_provider({"task": "total", "classes": {}}, inp, out, "fastest")

    def test_generic_supervisor_timeout_and_cancel_kill_process_group(self):
        runner = SupervisedProcessRunner()
        env = dict(os.environ)
        log1 = self.root / "timeout"
        with self.assertRaises(ProcessExecutionError) as err:
            runner.run((sys.executable, "-c", "import time;time.sleep(10)"),
                       environment=env, working_directory=log1, timeout_seconds=.15,
                       cancellation_check=lambda: False, log_prefix="probe")
        self.assertEqual(err.exception.code, "timeout")
        log2 = self.root / "cancel"
        with self.assertRaises(ProcessExecutionError) as err:
            runner.run((sys.executable, "-c", "import time;time.sleep(10)"),
                       environment=env, working_directory=log2, timeout_seconds=3,
                       cancellation_check=lambda: True, log_prefix="probe")
        self.assertEqual(err.exception.code, "cancelled")


if __name__ == "__main__":
    unittest.main()
