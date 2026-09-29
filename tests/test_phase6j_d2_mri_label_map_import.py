"""D2 synthetic tests: fake mask/worker only; no DICOM, model, or GPU."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))

from voxelatlas.mri_label_map_import import QualifiedMRIResultImporter
from voxelatlas.segmentation import SegmentationValidationError
from voxelatlas.segmentation_label_maps import SegmentationLabelMapService
from test_phase5c_canonical_label_map_import import CanonicalizingRunner, Completed
import test_phase6j_c4b_mri_study_bound_jobs as c4b


class MRICanonicalizingRunner(CanonicalizingRunner):
    """Phase5C fake subprocess adapted to the MRI [0,50] label inventory."""
    def __call__(self, command, **kwargs):
        completed = super().__call__(command, **kwargs)
        path = Path(command[command.index("--output-npy") + 1])
        array = np.load(path, allow_pickle=False)
        array[array == 3] = 0
        array[array == 1] = 50
        with path.open("wb") as output:
            np.save(output, array, allow_pickle=False)
        report = json.loads(completed.stdout)
        report.update({
            "canonical_label_map_sha256": sha256(path.read_bytes()).hexdigest(),
            "canonical_label_map_bytes": path.stat().st_size,
            "present_labels": [0, 50], "maximum_label": 50, "nonzero_voxels": 1,
        })
        return Completed(returncode=0, stdout=json.dumps(report))


class QualifiedMRIImportTests(unittest.TestCase):
    def setUp(self):
        # Existing C4B fixture has a fake MRI executor and synthetic small MR volume.
        harness = c4b.MRIBoundJobs("test_parameter_contract_and_default_closed_execution")
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        self.harness = harness
        self.root = harness.data
        # The C4B fixture intentionally writes mock bytes rather than NPY;
        # D2 must exercise a genuine small synthetic float32 canonical array.
        with (self.root / "studies" / ("a" * 32) / "derived/volume.npy").open("wb") as output:
            np.save(output, np.zeros((2, 3, 4), dtype=np.float32), allow_pickle=False)
        self.input_bytes = b"synthetic-nifti-input-no-patient-data"
        harness.executor.overrides = {"input_nifti_sha256": sha256(self.input_bytes).hexdigest()}
        harness.permit = True
        created = harness.create()
        self.job = harness.jobs.run_job(str(created["job_id"]))
        self.assertEqual(self.job["state"], "succeeded")
        workspace = self.root / "segmentation/jobs" / str(self.job["job_id"]) / "provider/totalsegmentator-mri"
        (workspace / "input").mkdir(parents=True, exist_ok=True)
        (workspace / "input/canonical-mri.nii.gz").write_bytes(self.input_bytes)
        (workspace / "output/provider-report.json").write_text('{"synthetic":true}', encoding="utf-8")
        self.runner = MRICanonicalizingRunner()
        self.worker = self.root / "fake_phase5c_worker.py"
        self.worker.write_text("# synthetic no-execution worker\n", encoding="utf-8")
        self.maps = SegmentationLabelMapService(
            data_dir=self.root, job_service=harness.jobs, worker_runner=self.runner,
        )
        self.report_calls = 0
        def report_check(report, input_path, mask_path):
            self.report_calls += 1
            self.assertEqual(report.name, "provider-report.json")
            self.assertEqual(input_path.name, "canonical-mri.nii.gz")
            self.assertEqual(mask_path.name, "labels.nii.gz")
        self.importer = QualifiedMRIResultImporter(
            data_dir=self.root, jobs=harness.jobs, label_maps=self.maps,
            provider_report_check=report_check,
        )

    def assert_not_imported(self):
        self.assertFalse((self.root / "segmentation/label-maps").exists())
        self.assertEqual(self.runner.commands, [])

    def test_read_only_qualification_and_no_model_reexecution(self):
        original_model_calls = len(self.harness.executor.calls)
        source, job = self.importer.qualify()
        self.assertEqual(source.modality, "MR")
        self.assertEqual(job["job_id"], self.job["job_id"])
        self.assertEqual(len(self.harness.executor.calls), original_model_calls)
        self.assertEqual(self.report_calls, 1)
        self.assert_not_imported()

    def test_import_produces_immutable_idempotent_mri_map(self):
        calls_before = len(self.harness.executor.calls)
        first = self.importer.import_current(python_executable="/opt/test/python", worker_script=self.worker)
        second = self.importer.import_current(python_executable="/opt/test/python", worker_script=self.worker)
        self.assertEqual(first, second)
        self.assertEqual(first["source_modality"], "MR")
        self.assertEqual(first["model_id"], "total_mr")
        self.assertEqual(first["task"], "total_mr")
        self.assertEqual(first["class_count"], 50)
        self.assertEqual(first["present_labels"], [0, 50])
        self.assertEqual(first["nonzero_voxels"], 1)
        self.assertEqual(first["coordinate_system"], "patient_lps")
        self.assertIs(first["resampled"], False)
        self.assertEqual(self.maps.get(first["label_map_id"]), first)
        self.assertEqual(len(self.runner.commands), 1)
        self.assertEqual(len(self.harness.executor.calls), calls_before)
        self.assertEqual(self.harness.jobs.get_job(self.job["job_id"]), self.job)

    def test_corrupted_mask_blocks_before_any_import(self):
        mask = self.root / "segmentation/jobs" / self.job["job_id"] / "provider/totalsegmentator-mri/output/labels.nii.gz"
        mask.write_bytes(mask.read_bytes() + b"drift")
        with self.assertRaises(SegmentationValidationError):
            self.importer.import_current(python_executable="/opt/test/python", worker_script=self.worker)
        self.assert_not_imported()

    def test_source_change_blocks_before_any_import(self):
        source = self.harness.jobs.sources.load("a" * 32)
        source.volume_path.write_bytes(source.volume_path.read_bytes() + b"drift")
        with self.assertRaises(SegmentationValidationError):
            self.importer.qualify()
        self.assert_not_imported()

    def test_wrong_study_or_ct_current_source_blocks(self):
        study = self.root / "studies" / ("a" * 32)
        manifest = study / "manifest.json"
        payload = json.loads(manifest.read_text())
        payload["volume"]["modality"] = "CT"
        (study / "derived/volume.json").write_text(json.dumps(payload["volume"]))
        manifest.write_text(json.dumps(payload))
        with self.assertRaises(SegmentationValidationError):
            self.importer.qualify()
        self.assert_not_imported()

    def test_wrong_series_or_mapping_blocks(self):
        manifest = self.root / "segmentation/jobs" / self.job["job_id"] / "manifest.json"
        for key, value in (("source_series_uid", "9.9.9"), ("model_id", "total")):
            with self.subTest(key=key):
                original = manifest.read_bytes()
                try:
                    job = json.loads(original)
                    job["provenance"][key] = value
                    job["provenance_sha256"] = self.harness.jobs.canonical_json_sha256(job["provenance"])
                    manifest.write_text(json.dumps(job))
                    with self.assertRaises(SegmentationValidationError):
                        self.importer.qualify()
                    self.assert_not_imported()
                finally:
                    manifest.write_bytes(original)

    def test_wrong_mask_label_inventory_fails_and_never_presents_map(self):
        class InvalidWorker(MRICanonicalizingRunner):
            def __call__(self, command, **kwargs):
                report = super().__call__(command, **kwargs)
                data = json.loads(report.stdout)
                data["present_labels"] = [0, 51]
                return Completed(returncode=0, stdout=json.dumps(data))
        self.maps._worker_runner = InvalidWorker()
        with self.assertRaises(SegmentationValidationError):
            self.importer.import_current(python_executable="/opt/test/python", worker_script=self.worker)
        self.assertEqual(self.maps.list(), [])


    def test_changed_input_hash_blocks_before_import(self):
        path = self.root / "segmentation/jobs" / self.job["job_id"] / "provider/totalsegmentator-mri/input/canonical-mri.nii.gz"
        path.write_bytes(b"modified-input")
        with self.assertRaises(SegmentationValidationError):
            self.importer.qualify()
        self.assert_not_imported()

    def test_provider_report_failure_blocks_before_import(self):
        def fail_report(_report, _input, _mask):
            raise SegmentationValidationError("Synthetic provider report rejected")
        self.importer.report_check = fail_report
        with self.assertRaises(SegmentationValidationError):
            self.importer.qualify()
        self.assert_not_imported()

    def test_symlinked_mask_parent_blocks_before_import(self):
        job_dir = self.root / "segmentation/jobs" / self.job["job_id"]
        output_dir = job_dir / "provider/totalsegmentator-mri/output"
        real_output = job_dir / "provider/totalsegmentator-mri/hidden-output"
        output_dir.rename(real_output)
        output_dir.symlink_to(real_output, target_is_directory=True)
        with self.assertRaises(SegmentationValidationError):
            self.importer.qualify()
        self.assert_not_imported()

    def test_no_matching_succeeded_job_blocks_before_import(self):
        manifest = self.root / "segmentation/jobs" / self.job["job_id"] / "manifest.json"
        manifest.unlink()
        with self.assertRaises(SegmentationValidationError):
            self.importer.qualify()
        self.assert_not_imported()

    def test_wrong_nonzero_count_is_rejected_before_persisting_map(self):
        class WrongVoxelCountWorker(MRICanonicalizingRunner):
            def __call__(self, command, **kwargs):
                completed = super().__call__(command, **kwargs)
                path = Path(command[command.index("--output-npy") + 1])
                labels = np.load(path, allow_pickle=False)
                labels.flat[2] = 50
                with path.open("wb") as output:
                    np.save(output, labels, allow_pickle=False)
                report = json.loads(completed.stdout)
                report.update({
                    "nonzero_voxels": 2,
                    "canonical_label_map_sha256": sha256(path.read_bytes()).hexdigest(),
                    "canonical_label_map_bytes": path.stat().st_size,
                })
                return Completed(returncode=0, stdout=json.dumps(report))
        self.maps._worker_runner = WrongVoxelCountWorker()
        with self.assertRaises(SegmentationValidationError):
            self.importer.import_current(python_executable="/opt/test/python", worker_script=self.worker)
        self.assertEqual(self.maps.list(), [])

    def test_existing_default_registry_and_ui_are_unchanged(self):
        from voxelatlas.segmentation import build_default_segmentation_registry
        registry = build_default_segmentation_registry()
        self.assertFalse(any(model["model_id"] == "total_mr" and model["available"] for model in registry.list_public()))
        self.assert_not_imported()


if __name__ == "__main__":
    unittest.main()
