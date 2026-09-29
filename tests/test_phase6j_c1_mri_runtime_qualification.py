"""6J-C1 MRI task/runtime qualification: no DICOM, weights, or real GPU required."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from voxelatlas.mri_runtime_qualification import (  # noqa: E402
    MRI_MAPPING_JSON_SHA256, MRIRuntimeQualifier, qualify_mri_runtime_payload,
)


def payload() -> dict[str, object]:
    return dict(
        schema_version=1, python_version="3.11.16", totalsegmentator_version="2.18.0",
        torch_version="2.14.0", nnunetv2_version="2.8.1", python_api_available=True,
        task="total_mr", task_modality="MR", task_class_count=50,
        task_mapping_sha256=MRI_MAPPING_JSON_SHA256,
        cuda_available=True, cuda_device_count=1, cuda_total_memory_mib=[6144],
    )


class MRIQualificationTests(unittest.TestCase):
    def test_valid_runtime_is_still_not_execution_ready(self):
        report = qualify_mri_runtime_payload(payload())
        self.assertTrue(report.runtime_qualified)
        self.assertFalse(report.execution_ready)
        self.assertEqual(report.cuda_total_memory_mib, (6144,))
        self.assertEqual(report.public_dict()["cuda_total_memory_mib"], [6144])
        self.assertNotIn("python_executable", report.public_dict())

    def test_version_task_mapping_and_gpu_fail_closed(self):
        alterations = (
            ("version_mismatch", "totalsegmentator_version", "2.17.0"),
            ("python_version_unsupported", "python_version", "3.9.19"),
            ("task_mismatch", "task", "total"),
            ("task_mismatch", "task_modality", "CT"),
            ("class_contract_mismatch", "task_class_count", 117),
            ("mapping_mismatch", "task_mapping_sha256", "a" * 64),
            ("python_api_unavailable", "python_api_available", False),
            ("cuda_unavailable", "cuda_available", False),
        )
        for code, field, value in alterations:
            with self.subTest(code=code, field=field):
                item = deepcopy(payload())
                item[field] = value
                if field == "cuda_available":
                    item["cuda_device_count"] = 0
                    item["cuda_total_memory_mib"] = []
                report = qualify_mri_runtime_payload(item)
                self.assertEqual(report.status_code, code)
                self.assertFalse(report.runtime_qualified)
                self.assertFalse(report.execution_ready)

    def test_malformed_gpu_and_schema_are_rejected(self):
        for change in (
            {"schema_version": True},
            {"cuda_device_count": True},
            {"cuda_total_memory_mib": [0]},
            {"cuda_total_memory_mib": [6144, 6144]},
            {"cuda_available": False},
            {"task_class_count": True},
        ):
            with self.subTest(change=change):
                report = qualify_mri_runtime_payload({**payload(), **change})
                self.assertFalse(report.runtime_qualified)
                self.assertFalse(report.execution_ready)

    def test_probe_uses_isolated_child_and_does_not_emit_stderr(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload()), stderr="/private/patient/study")
        result = MRIRuntimeQualifier(runner=runner).qualify("/safe/env/bin/python")
        self.assertTrue(result.runtime_qualified)
        self.assertEqual(calls[0][0][:3], ["/safe/env/bin/python", "-I", "-c"])
        self.assertFalse(calls[0][1]["shell"])
        self.assertTrue(calls[0][1]["capture_output"])
        self.assertNotIn("private", str(result.public_dict()))
        self.assertNotIn("TotalSegmentator", str(calls[0][0][0]))

    def test_probe_errors_are_generic_and_fail_closed(self):
        for outcome, code in (
            (FileNotFoundError("/secret/private"), "runtime_unavailable"),
            (subprocess.TimeoutExpired("python", 1), "probe_timeout"),
        ):
            def runner(command, **kwargs):
                raise outcome
            result = MRIRuntimeQualifier(runner=runner).qualify("python")
            self.assertEqual(result.status_code, code)
            self.assertFalse(result.execution_ready)
            self.assertNotIn("secret", result.message)
        bad = MRIRuntimeQualifier(runner=lambda *a, **k: SimpleNamespace(
            returncode=1, stdout="", stderr="PATIENT_SECRET")).qualify("python")
        self.assertEqual(bad.status_code, "probe_failed")
        self.assertNotIn("SECRET", str(bad.public_dict()))


if __name__ == "__main__":
    unittest.main()
