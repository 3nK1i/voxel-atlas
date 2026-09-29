from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
REQUIREMENTS = ROOT / "requirements" / "segmentation-totalsegmentator.txt"
RUNNER = ROOT / "scripts" / "run_phase5b1_checks.sh"
PROBE = ROOT / "scripts" / "check_phase5b1_totalsegmentator_environment.py"
DOC = ROOT / "docs" / "phase_history" / "PHASE5B1_TOTALSEGMENTATOR_RUNTIME_QUALIFICATION.md"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.totalsegmentator_runtime import (  # noqa: E402
    EXPECTED_TOTAL_CLASS_COUNT,
    EXPECTED_TOTAL_TASK_DEFINITION_SHA256,
    PINNED_TOTALSEGMENTATOR_VERSION,
    TotalSegmentatorRuntimeQualifier,
    build_totalsegmentator_invocation,
    validate_totalsegmentator_parameters,
)


def qualified_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "python_version": "3.11.9",
        "totalsegmentator_version": PINNED_TOTALSEGMENTATOR_VERSION,
        "torch_version": "2.7.1+cu128",
        "nnunetv2_version": "2.6.2",
        "python_api_available": True,
        "task": "total",
        "task_modality": "CT",
        "task_class_count": EXPECTED_TOTAL_CLASS_COUNT,
        "task_definition_sha256": EXPECTED_TOTAL_TASK_DEFINITION_SHA256,
        "task_requires_license": False,
        "cuda_available": True,
        "cuda_device_count": 1,
        "cuda_devices": [
            {
                "index": 0,
                "name": "NVIDIA GeForce RTX 2060",
                "total_memory_mib": 6144,
            }
        ],
    }
    payload.update(overrides)
    return payload


class FakeCompletedProcess:
    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Phase5B1TotalSegmentatorQualificationTests(unittest.TestCase):
    def test_exact_runtime_task_and_cuda_contract_is_qualified(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def runner(command: list[str], **kwargs: object) -> FakeCompletedProcess:
            calls.append((command, kwargs))
            return FakeCompletedProcess(stdout=json.dumps(qualified_payload()))

        report = TotalSegmentatorRuntimeQualifier(runner=runner).qualify(
            "/opt/voxelatlas-seg/bin/python"
        )

        self.assertTrue(report.qualified)
        self.assertEqual(report.status_code, "qualified")
        self.assertEqual(report.totalsegmentator_version, PINNED_TOTALSEGMENTATOR_VERSION)
        self.assertEqual(report.task, "total")
        self.assertEqual(report.task_modality, "CT")
        self.assertEqual(report.task_class_count, EXPECTED_TOTAL_CLASS_COUNT)
        self.assertEqual(report.cuda_device_count, 1)
        self.assertEqual(len(calls), 1)
        command, kwargs = calls[0]
        self.assertEqual(command[0], "/opt/voxelatlas-seg/bin/python")
        self.assertEqual(command[1:3], ["-I", "-c"])
        self.assertFalse(kwargs.get("shell", False))
        self.assertTrue(kwargs.get("capture_output"))
        self.assertIn("timeout", kwargs)

        public = report.public_dict()
        self.assertNotIn("python_executable", public)
        self.assertNotIn("probe_stdout", public)
        self.assertNotIn("probe_stderr", public)

    def test_missing_runtime_timeout_and_malformed_output_fail_safely(self) -> None:
        cases: list[tuple[object, str]] = [
            (FileNotFoundError("/secret/runtime/python"), "runtime_unavailable"),
            (subprocess.TimeoutExpired(["python"], timeout=5), "probe_timeout"),
        ]
        for failure, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                def runner(command: list[str], **kwargs: object) -> FakeCompletedProcess:
                    del command, kwargs
                    raise failure  # type: ignore[misc]

                report = TotalSegmentatorRuntimeQualifier(runner=runner).qualify("python")
                self.assertFalse(report.qualified)
                self.assertEqual(report.status_code, expected_code)
                self.assertNotIn("secret", report.message.lower())

        def malformed_runner(command: list[str], **kwargs: object) -> FakeCompletedProcess:
            del command, kwargs
            return FakeCompletedProcess(stdout="not-json", stderr="/private/patient/path")

        report = TotalSegmentatorRuntimeQualifier(runner=malformed_runner).qualify("python")
        self.assertFalse(report.qualified)
        self.assertEqual(report.status_code, "invalid_probe_report")
        self.assertNotIn("private", report.message.lower())

    def test_nonzero_probe_does_not_publish_provider_traceback(self) -> None:
        def runner(command: list[str], **kwargs: object) -> FakeCompletedProcess:
            del command, kwargs
            return FakeCompletedProcess(
                returncode=1,
                stderr="Traceback: patient=/data/studies/private/volume.npy token=secret",
            )

        report = TotalSegmentatorRuntimeQualifier(runner=runner).qualify("python")
        self.assertFalse(report.qualified)
        self.assertEqual(report.status_code, "probe_failed")
        self.assertEqual(report.message, "TotalSegmentator runtime probe failed")

    def test_version_task_modality_class_license_api_and_cuda_drift_are_rejected(self) -> None:
        cases = {
            "python_version_unsupported": {"python_version": "3.9.19"},
            "version_mismatch": {"totalsegmentator_version": "2.17.0"},
            "python_api_unavailable": {"python_api_available": False},
            "task_mismatch": {"task": "total_mr"},
            "modality_mismatch": {"task_modality": "MR"},
            "class_contract_mismatch": {"task_class_count": 50},
            "task_definition_mismatch": {"task_definition_sha256": "b" * 64},
            "license_contract_mismatch": {"task_requires_license": True},
            "cuda_unavailable": {"cuda_available": False, "cuda_device_count": 0, "cuda_devices": []},
        }
        for expected_code, overrides in cases.items():
            with self.subTest(expected_code=expected_code):
                def runner(command: list[str], **kwargs: object) -> FakeCompletedProcess:
                    del command, kwargs
                    return FakeCompletedProcess(stdout=json.dumps(qualified_payload(**overrides)))

                report = TotalSegmentatorRuntimeQualifier(runner=runner).qualify("python")
                self.assertFalse(report.qualified)
                self.assertEqual(report.status_code, expected_code)

    def test_probe_schema_and_cuda_device_records_are_strict(self) -> None:
        invalid_payloads = [
            qualified_payload(schema_version=2),
            qualified_payload(cuda_device_count=2),
            qualified_payload(cuda_devices=[{"index": "0", "name": "GPU", "total_memory_mib": 1}]),
            qualified_payload(cuda_devices=[{"index": 0, "name": "/patient/path", "total_memory_mib": 1}]),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                def runner(command: list[str], **kwargs: object) -> FakeCompletedProcess:
                    del command, kwargs
                    return FakeCompletedProcess(stdout=json.dumps(payload))

                report = TotalSegmentatorRuntimeQualifier(runner=runner).qualify("python")
                self.assertFalse(report.qualified)
                self.assertEqual(report.status_code, "invalid_probe_report")

    def test_provider_parameters_lock_full_resolution_total_ct_baseline(self) -> None:
        self.assertEqual(
            validate_totalsegmentator_parameters({}),
            {
                "task": "total",
                "output_mode": "multilabel_nifti",
                "resolution": "full",
            },
        )
        for invalid in (
            {"task": "total_mr"},
            {"fast": True},
            {"fastest": True},
            {"save_lowres": True},
            {"device": "cpu"},
            {"roi_subset": ["liver"]},
            {"unknown": True},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_totalsegmentator_parameters(invalid)

    def test_invocation_is_explicit_full_resolution_multilabel_and_never_uses_shell(self) -> None:
        plan = build_totalsegmentator_invocation(
            python_executable="/opt/voxelatlas-seg/bin/python",
            input_nifti=Path("/runtime/job/input/volume.nii.gz"),
            output_nifti=Path("/runtime/job/output/labels.nii.gz"),
            report_json=Path("/runtime/job/output/provider-report.json"),
            device_selector="cuda:0",
        )
        self.assertEqual(plan.command[0], "/opt/voxelatlas-seg/bin/python")
        self.assertEqual(plan.command[1:4], ("-I", "-m", "totalsegmentator.bin.TotalSegmentator"))
        self.assertIn("total", plan.command)
        self.assertIn("--ml", plan.command)
        self.assertIn("gpu:0", plan.command)
        self.assertIn("--report", plan.command)
        self.assertNotIn("--fast", plan.command)
        self.assertNotIn("--fastest", plan.command)
        self.assertNotIn("--save_lowres", plan.command)
        self.assertNotIn("cpu", plan.command)

        for invalid_device in ("auto", "cpu", "cuda", "cuda:-1", "gpu:0", "cuda:9999"):
            with self.subTest(invalid_device=invalid_device):
                with self.assertRaises(ValueError):
                    build_totalsegmentator_invocation(
                        python_executable="python",
                        input_nifti=Path("/runtime/input.nii.gz"),
                        output_nifti=Path("/runtime/output.nii.gz"),
                        report_json=Path("/runtime/report.json"),
                        device_selector=invalid_device,
                    )

    def test_invocation_rejects_wrong_extensions_aliasing_and_relative_paths(self) -> None:
        valid = {
            "python_executable": "/opt/voxelatlas-seg/bin/python",
            "input_nifti": Path("/runtime/input.nii.gz"),
            "output_nifti": Path("/runtime/output.nii.gz"),
            "report_json": Path("/runtime/provider-report.json"),
            "device_selector": "cuda:0",
        }
        mutations = [
            {"input_nifti": Path("relative.nii.gz")},
            {"input_nifti": Path("/runtime/input.npy")},
            {"output_nifti": Path("/runtime/output")},
            {"report_json": Path("/runtime/report.txt")},
            {"output_nifti": Path("/runtime/input.nii.gz")},
            {"report_json": Path("/runtime/input.nii.gz")},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                values = {**valid, **mutation}
                with self.assertRaises(ValueError):
                    build_totalsegmentator_invocation(**values)

    def test_phase_boundary_does_not_import_or_run_heavy_runtime_in_web_process(self) -> None:
        module_text = (BACKEND / "voxelatlas" / "totalsegmentator_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import torch", module_text)
        self.assertNotIn("import totalsegmentator", module_text)
        self.assertNotIn("from totalsegmentator", module_text)
        self.assertNotIn("shell=True", module_text)

        app_text = (BACKEND / "voxelatlas" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("totalsegmentator_runtime", app_text)
        self.assertNotIn("TotalSegmentatorRuntimeQualifier", app_text)

    def test_isolated_runtime_manifest_is_exactly_pinned(self) -> None:
        lines = [
            line.strip()
            for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(lines, [f"TotalSegmentator=={PINNED_TOTALSEGMENTATOR_VERSION}"])
        backend_requirements = (ROOT / "requirements" / "backend.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("TotalSegmentator", backend_requirements)
        self.assertNotIn("torch", backend_requirements.lower())

    def test_probe_and_validation_runner_preserve_phase_boundaries(self) -> None:
        probe = PROBE.read_text(encoding="utf-8")
        runner = RUNNER.read_text(encoding="utf-8")
        doc = DOC.read_text(encoding="utf-8")
        self.assertNotIn("pip install", probe)
        self.assertIn("bash scripts/run_phase5a_checks.sh", runner)
        self.assertIn("REAL_SEGMENTATION_INFERENCE=NOT_RUN", runner)
        self.assertIn("MODEL_WEIGHTS=NOT_DOWNLOADED", runner)
        self.assertIn("no model weights", doc.lower())
        self.assertIn("Phase 5B2", doc)


if __name__ == "__main__":
    unittest.main()
