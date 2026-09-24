"""C5D synthetic-only tests: no stored studies, weights, or GPU execution."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("voxelatlas_c5d_trial", ROOT / "scripts/phase6j_c5d_single_trial.py")
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)


class TrialPreparation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name).resolve()
        self.py = self.data / "isolated-python"
        self.py.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.py.chmod(0o700)
        self.bridge = self.data / "bridge.py"
        self.bridge.write_text("# synthetic only\n", encoding="utf-8")
        self.source = SimpleNamespace(modality="MR", study_id="a" * 32)
        self.gpu = trial.SegmentationDevice("cuda", "cuda:0", "NVIDIA GeForce RTX 2060", 0, 6144, 5120)
        self.status = SimpleNamespace(prerequisites_qualified=True, execution_authorized=False,
                                      source_qualified=True)

    def prepare(self, *, source=None, gpu=None, status=None, python=None, provider_qualification=None):
        source = self.source if source is None else source
        gpu = self.gpu if gpu is None else gpu
        status = self.status if status is None else status
        class Repo:
            def __init__(self, root):
                self.root = root
            def latest(self):
                return source
            def load(self, study_id):
                return source
        with patch.object(trial, "_preview_running", return_value=False), \
             patch.object(trial, "CanonicalSegmentationSourceRepository", Repo), \
             patch.object(trial, "qualify_mri_stored_source", return_value=(True, "synthetic")):
            return trial.preflight(data_dir=self.data, python=self.py if python is None else python, bridge=self.bridge,
                                    gpu_discovery=lambda: (gpu,),
                                    provider_qualification=provider_qualification or (lambda **kwargs: status))

    def test_synthetic_preflight_passes_without_creating_jobs_or_artifacts(self):
        source, device = self.prepare()
        self.assertIs(source, self.source)
        self.assertIs(device, self.gpu)
        self.assertFalse((self.data / "segmentation").exists())

    def test_conda_style_local_python_symlink_qualifies_resolved_executable(self):
        alias = self.data / "python"
        alias.symlink_to(self.py.name)
        seen = []
        def qualify(**kwargs):
            seen.append(kwargs["python_executable"])
            return self.status
        source, device = self.prepare(python=alias, provider_qualification=qualify)
        self.assertIs(source, self.source)
        self.assertIs(device, self.gpu)
        self.assertEqual(seen, [str(self.py)])
        self.assertFalse((self.data / "segmentation").exists())

    def test_dangling_and_external_python_symlinks_fail_closed(self):
        alias = self.data / "python"
        alias.symlink_to("missing-python")
        with self.assertRaisesRegex(trial.TrialBlocked, "RUNTIME_OR_PREVIEW"):
            self.prepare(python=alias)
        alias.unlink()
        with tempfile.TemporaryDirectory() as external:
            external_python = Path(external) / "python3"
            external_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            external_python.chmod(0o700)
            alias.symlink_to(external_python)
            with self.assertRaisesRegex(trial.TrialBlocked, "RUNTIME_OR_PREVIEW"):
                self.prepare(python=alias)
        self.assertFalse((self.data / "segmentation").exists())

    def test_ct_source_is_rejected_without_job_creation(self):
        with self.assertRaisesRegex(trial.TrialBlocked, "STORED_MRI_SOURCE"):
            self.prepare(source=SimpleNamespace(modality="CT", study_id="a" * 32))
        self.assertFalse((self.data / "segmentation").exists())

    def test_low_gpu_memory_and_other_gpu_are_rejected(self):
        for name, free in (("NVIDIA GeForce RTX 2060", 3500), ("NVIDIA RTX 5090", 5120)):
            with self.subTest(name=name, free=free):
                device = trial.SegmentationDevice("cuda", "cuda:0", name, 0, 6144, free)
                with self.assertRaisesRegex(trial.TrialBlocked, "GPU_MEMORY_OR_IDENTITY"):
                    self.prepare(gpu=device)
        self.assertFalse((self.data / "segmentation").exists())

    def test_provider_must_remain_not_execution_authorized(self):
        with self.assertRaisesRegex(trial.TrialBlocked, "MODEL_PREREQUISITES"):
            self.prepare(status=SimpleNamespace(prerequisites_qualified=True,
                   execution_authorized=True, source_qualified=True))

    def test_active_existing_job_blocks_before_service_recovery(self):
        path = self.data / "segmentation" / "jobs" / ("seg-" + "f" * 32)
        path.mkdir(parents=True)
        (path / "manifest.json").write_text('{"state":"running"}', encoding="utf-8")
        with self.assertRaisesRegex(trial.TrialBlocked, "OTHER_JOBS"):
            self.prepare()

    def test_local_preview_blocks_preflight(self):
        with patch.object(trial, "_preview_running", return_value=True):
            with self.assertRaisesRegex(trial.TrialBlocked, "RUNTIME_OR_PREVIEW"):
                trial.preflight(data_dir=self.data, python=self.py, bridge=self.bridge)

    def test_check_mode_rejects_authorization_and_never_executes(self):
        with patch.object(trial, "check_repository"), patch.object(trial, "preflight") as check, \
             patch.object(trial, "execute_once") as execute:
            with patch.object(trial, "ROOT", self.data):
                self.assertEqual(trial.main(["--check"]), 0)
                self.assertEqual(trial.main(["--check", "--authorization", trial.AUTHORIZATION]), 2)
                self.assertEqual(trial.main(["--execute"]), 2)
                self.assertEqual(trial.main(["--execute", "--authorization", "wrong"]), 2)
            self.assertEqual(check.call_count, 1)
            execute.assert_not_called()

    def test_run_requires_clean_pushed_branch(self):
        with patch.object(trial, "_git", side_effect=lambda *args: {
            ("rev-parse", "--show-toplevel"): str(ROOT),
            ("branch", "--show-current"): trial.BRANCH,
            ("status", "--porcelain=v1", "--untracked-files=all"): " M changed.py",
        }[args]), patch.object(trial.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
            with self.assertRaisesRegex(trial.TrialBlocked, "UNCOMMITTED_OR_UNPUSHED"):
                trial.check_repository(execute=True)

    def test_single_run_uses_bound_job_api_and_no_model_in_synthetic_test(self):
        calls = []
        source = self.source
        device = self.gpu
        class FakeRegistry:
            def register_provider(self, provider):
                calls.append("local_registry_only")
        class FakeJobs:
            def __init__(self, **kwargs):
                self.sources = SimpleNamespace(load=lambda study_id: source)
            def create_job(self, **kwargs):
                calls.append(("create", kwargs))
                return {"job_id": "seg-" + "f" * 32}
            def run_job(self, job_id):
                calls.append(("run", job_id))
                return {"state": "succeeded", "outcome": {"code": "qualified_execution"}}
            def cancel_job(self, job_id):
                calls.append(("cancel", job_id))
        alias = self.data / "python"
        alias.symlink_to(self.py.name)
        with patch.object(trial, "preflight", return_value=(source, device)), \
             patch.object(trial, "SegmentationModelRegistry", FakeRegistry), \
             patch.object(trial, "SegmentationJobService", FakeJobs), \
             patch.object(trial, "MRIStudyBoundProvider", return_value=object()), \
             patch.object(trial, "MRIWorkerExecutor", side_effect=lambda **kw: (calls.append(("python", kw["python_executable"])), object())[1]), \
             patch.object(trial, "CanonicalSegmentationSourceRepository", return_value=SimpleNamespace(
                 load=lambda study_id: source)), \
             patch.object(trial, "qualify_mri_stored_source", return_value=(True, "synthetic")), \
             patch.object(trial, "_preview_running", return_value=False):
            result = trial.execute_once(data_dir=self.data, python=alias, bridge=self.bridge,
                                       gpu_discovery=lambda: (device,))
        self.assertEqual(result["state"], "succeeded")
        self.assertIn(("python", self.py), calls)
        creates = [item[1] for item in calls if isinstance(item, tuple) and item[0] == "create"]
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0]["source_study_id"], source.study_id)
        self.assertEqual(creates[0]["parameters"], {"mode": "fastest"})
        self.assertEqual(sum(1 for item in calls if isinstance(item, tuple) and item[0] == "run"), 1)
        self.assertFalse((self.data / "segmentation").exists())

    def test_job_exception_is_recorded_as_failure_without_retry(self):
        source = self.source
        device = self.gpu
        calls = []
        class FakeJobs:
            def __init__(self, **kwargs):
                self.sources = SimpleNamespace(load=lambda study_id: source)
            def create_job(self, **kwargs):
                return {"job_id": "seg-" + "f" * 32}
            def run_job(self, job_id):
                calls.append("run")
                raise ValueError("private patient source")
            def fail_job(self, job_id, **kwargs):
                calls.append("sealed_failure")
            def cancel_job(self, job_id):
                calls.append("cancel")
        with patch.object(trial, "preflight", return_value=(source, device)), \
             patch.object(trial, "SegmentationModelRegistry", return_value=SimpleNamespace(register_provider=lambda p: None)), \
             patch.object(trial, "SegmentationJobService", FakeJobs), \
             patch.object(trial, "MRIStudyBoundProvider", return_value=object()), \
             patch.object(trial, "MRIWorkerExecutor", return_value=object()), \
             patch.object(trial, "CanonicalSegmentationSourceRepository", return_value=SimpleNamespace(
                 load=lambda study_id: source)), \
             patch.object(trial, "qualify_mri_stored_source", return_value=(True, "synthetic")), \
             patch.object(trial, "_preview_running", return_value=False):
            with self.assertRaises(ValueError):
                trial.execute_once(data_dir=self.data, python=self.py, bridge=self.bridge,
                                   gpu_discovery=lambda: (device,))
        self.assertEqual(calls, ["run", "sealed_failure"])

    def test_no_normal_application_registration_or_environment_toggle(self):
        source = (ROOT / "scripts/phase6j_c5d_single_trial.py").read_text(encoding="utf-8")
        self.assertNotIn('os.environ["VOXELATLAS_MRI_PYTHON"]', source)
        self.assertIn('SegmentationJobService(', source)
        self.assertIn('MRIStudyBoundProvider(', source)
        self.assertIn('parameters={"mode": "fastest"}', source)
        self.assertIn('execution_permission=lambda: True', source)


if __name__ == "__main__":
    unittest.main()
