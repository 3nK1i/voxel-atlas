"""Synthetic failure-stage coverage; no real MRI inference or patient artifacts."""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.mri_label_map_import import QualifiedMRIResultImporter
import test_phase6j_d2_mri_label_map_import as d2_tests

SPEC = importlib.util.spec_from_file_location(
    "phase6j_d2_import_entrypoint_stage_test", ROOT / "scripts/phase6j_d2_import_mri_label_map.py"
)
assert SPEC is not None and SPEC.loader is not None
ENTRY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENTRY)


class StageReportingTests(unittest.TestCase):
    def test_reported_failure_stage_has_fixed_allowlisted_value_and_no_exception(self):
        for stage in ("REPOSITORY", "PRE_IMPORT_QUALIFICATION", "WORKER_EXECUTION",
                      "WORKER_OUTPUT_VALIDATION", "PERSISTED_MAP_RELOAD",
                      "POST_IMPORT_ACCEPTANCE"):
            with self.subTest(stage=stage), io.StringIO() as output:
                with contextlib.redirect_stdout(output):
                    ENTRY._report_blocked(stage=stage, do_import=True)
                self.assertEqual(output.getvalue().splitlines(), [
                    "D2_STATUS=BLOCKED", f"D2_FAILURE_STAGE={stage}",
                ])
        with self.assertRaises(ValueError):
            ENTRY._report_blocked(stage="PATIENT=private", do_import=True)

    def test_check_mode_never_emits_failure_stage(self):
        with io.StringIO() as output, contextlib.redirect_stdout(output):
            ENTRY._report_blocked(stage="REPOSITORY", do_import=False)
            self.assertEqual(output.getvalue().splitlines(), ["D2_STATUS=BLOCKED"])

    def test_importer_marks_final_stage_without_exposing_exception_details(self):
        importer = object.__new__(QualifiedMRIResultImporter)
        importer.maps = mock.Mock()
        importer.qualify = mock.Mock(side_effect=[(mock.sentinel.source, {"job_id": "a" * 32,
                                      "outcome": {"nonzero_voxels": 1}}),
                                      RuntimeError("private contents must not print")])
        importer.maps.import_succeeded_job.return_value = {}
        stages = []
        with self.assertRaisesRegex(RuntimeError, "private"):
            importer.import_current(python_executable="/opt/synthetic/python",
                                    worker_script=Path("/opt/synthetic/worker.py"),
                                    diagnostic_stage=stages.append)
        self.assertEqual(stages, ["IMPORT_REQUALIFICATION",
                                  "POST_IMPORT_REQUALIFICATION"])
        self.assertEqual(importer.maps.import_succeeded_job.call_count, 1)

    def test_synthetic_import_reports_worker_persistence_reload_and_acceptance(self):
        case = d2_tests.QualifiedMRIImportTests("test_import_produces_immutable_idempotent_mri_map")
        case.setUp()
        self.addCleanup(case.doCleanups)
        stages = []
        original_model_calls = len(case.harness.executor.calls)
        descriptor = case.importer.import_current(
            python_executable="/opt/synthetic/python", worker_script=case.worker,
            diagnostic_stage=stages.append,
        )
        self.assertEqual(descriptor["state"], "ready")
        self.assertEqual(len(case.harness.executor.calls), original_model_calls)
        self.assertEqual(stages, [
            "IMPORT_REQUALIFICATION", "GENERIC_JOB_CONTRACT", "EXISTING_MAP_LOOKUP",
            "DESTINATION_SETUP", "WORKER_EXECUTION", "WORKER_OUTPUT_VALIDATION",
            "MANIFEST_WRITE", "ARTIFACT_PERSISTENCE", "PERSISTED_MAP_RELOAD",
            "POST_IMPORT_REQUALIFICATION", "POST_IMPORT_ACCEPTANCE",
            "PERSISTED_MAP_RELOAD",
        ])

    def test_worker_failure_is_classified_and_staging_is_cleaned(self):
        case = d2_tests.QualifiedMRIImportTests("test_import_produces_immutable_idempotent_mri_map")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.maps._worker_runner = mock.Mock(side_effect=OSError("synthetic private failure"))
        stages = []
        with self.assertRaises(Exception):
            case.importer.import_current(
                python_executable="/opt/synthetic/python", worker_script=case.worker,
                diagnostic_stage=stages.append,
            )
        self.assertEqual(stages[-1], "WORKER_EXECUTION")
        root = case.root / "segmentation" / "label-maps"
        self.assertEqual(list(root.iterdir()), [])

    def test_entrypoint_import_failure_reports_safe_stage_without_data_writes(self):
        with tempfile.TemporaryDirectory() as root:
            temporary = Path(root)
            data = temporary / "data"
            data.mkdir()
            worker = temporary / "worker.py"
            worker.write_text("# synthetic worker, never executed\n", encoding="utf-8")
            python_executable = temporary / "python"
            python_executable.write_bytes(b"synthetic executable; never executed\n")
            job = {"job_id": "a" * 32}

            class FakeImporter:
                def __init__(self, **kwargs):
                    pass

                def qualify(self):
                    return mock.Mock(study_id="b" * 32), job

                def import_current(self, *, diagnostic_stage, **kwargs):
                    diagnostic_stage("PERSISTED_MAP_RELOAD")
                    raise RuntimeError("SENSITIVE INTERNAL ERROR MUST NOT LEAK")

            def git(*args):
                if args == ("rev-parse", "--show-toplevel"):
                    return str(temporary)
                if args == ("branch", "--show-current"):
                    return ENTRY.BRANCH
                if args == ("status", "--porcelain=v1", "--untracked-files=all"):
                    return ""
                return "c" * 40

            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(ENTRY, "ROOT", temporary))
                stack.enter_context(mock.patch.object(ENTRY, "PYTHON", python_executable))
                stack.enter_context(mock.patch.object(ENTRY, "WORKER", worker))
                stack.enter_context(mock.patch.object(ENTRY, "_git", side_effect=git))
                stack.enter_context(mock.patch.object(ENTRY, "_no_active_jobs"))
                stack.enter_context(mock.patch.object(ENTRY, "SegmentationJobService"))
                stack.enter_context(mock.patch.object(ENTRY, "SegmentationLabelMapService"))
                stack.enter_context(mock.patch.object(ENTRY, "QualifiedMRIResultImporter", FakeImporter))
                stack.enter_context(mock.patch.object(ENTRY, "socket"))
                stack.enter_context(mock.patch.object(ENTRY, "fcntl"))
                stack.enter_context(mock.patch.object(ENTRY, "os"))
                stack.enter_context(mock.patch.object(ENTRY.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="c" * 40 + "\trefs/heads/phase6-accurate-surfaces\n")))
                # Patch only the module-local OS calls, not os.path globally.
                ENTRY.os.open.return_value = 9
                ENTRY.os.access.return_value = True
                ENTRY.os.O_RDONLY = 0
                ENTRY.os.O_DIRECTORY = 0
                ENTRY.os.O_NOFOLLOW = 0
                ENTRY.os.close.return_value = None
                with io.StringIO() as output, contextlib.redirect_stdout(output):
                    result = ENTRY.main(["--import", "--confirmation", ENTRY.CONFIRMATION])
                    self.assertEqual(result, 1)
                    self.assertEqual(output.getvalue().splitlines(), [
                        "D2_STATUS=BLOCKED", "D2_FAILURE_STAGE=PERSISTED_MAP_RELOAD",
                    ])


if __name__ == "__main__":
    unittest.main()
