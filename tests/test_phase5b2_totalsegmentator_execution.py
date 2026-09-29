from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.totalsegmentator_execution import (  # noqa: E402
    _CUDA_PREFLIGHT_PROGRAM,
    EXPECTED_TOTAL_WEIGHT_IDS,
    MINIMUM_CUDA_FREE_MEMORY_MIB,
    ProcessExecutionError,
    ProcessExecutionResult,
    SupervisedProcessRunner,
    TotalSegmentatorExecutionError,
    TotalSegmentatorProvider,
    build_controlled_runtime_paths,
    build_totalsegmentator_environment,
    build_weights_download_invocation,
    create_weights_manifest,
    load_weights_manifest,
    prepare_controlled_runtime,
    select_memory_strategy,
    validate_bridge_export_report,
    validate_mask_inspection_report,
    validate_provider_run_report,
)
from voxelatlas.totalsegmentator_runtime import (  # noqa: E402
    EXPECTED_TOTAL_TASK_DEFINITION_SHA256,
    PINNED_TOTALSEGMENTATOR_VERSION,
    build_totalsegmentator_invocation,
    TotalSegmentatorCudaDevice,
    TotalSegmentatorRuntimeReport,
)
from voxelatlas.segmentation import (  # noqa: E402
    CanonicalSegmentationSource,
    SegmentationDevice,
    SegmentationExecutionContext,
)


class FakeProcess:
    def __init__(self, returncode: int | None = 0, polls: int = 0) -> None:
        self.returncode = None if polls else returncode
        self._final_returncode = returncode
        self._polls = polls
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        if self._polls:
            self._polls -= 1
            return None
        self.returncode = self._final_returncode
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return int(self.returncode or 0)


class Phase5B2TotalSegmentatorExecutionTests(unittest.TestCase):
    def _write_weight_tree(self, root: Path) -> None:
        for task_id in EXPECTED_TOTAL_WEIGHT_IDS:
            dataset = root / f"Dataset{task_id}_TotalSegmentator"
            dataset.mkdir(parents=True)
            (dataset / "dataset.json").write_text(
                json.dumps({"dataset_id": task_id}), encoding="utf-8"
            )
            (dataset / "fold_0.pth").write_bytes(f"weights-{task_id}".encode())

    def test_runtime_paths_and_config_are_private_controlled_and_telemetry_off(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary) / "voxelatlas-data"
            paths = build_controlled_runtime_paths(data_dir)
            self.assertEqual(
                paths.root,
                data_dir.resolve()
                / "segmentation"
                / "providers"
                / "totalsegmentator"
                / PINNED_TOTALSEGMENTATOR_VERSION,
            )
            prepare_controlled_runtime(paths)
            config = json.loads(paths.config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["totalseg_id"], "voxelatlas-controlled")
            self.assertFalse(config["send_usage_stats"])
            self.assertEqual(config["prediction_counter"], 0)
            self.assertTrue(config["statistics_disclaimer_shown"])
            self.assertEqual(paths.config_path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(paths.root.is_symlink())

            env = build_totalsegmentator_environment(paths, base_environment={"PATH": "/bin"})
            self.assertEqual(env["TOTALSEG_HOME_DIR"], str(paths.home))
            self.assertEqual(env["TOTALSEG_WEIGHTS_PATH"], str(paths.weights))
            self.assertEqual(env["nnUNet_results"], str(paths.weights))
            self.assertEqual(env["PATH"], "/bin")

    def test_weight_download_is_explicit_total_task_and_manifest_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_controlled_runtime_paths(Path(temporary))
            prepare_controlled_runtime(paths)
            plan = build_weights_download_invocation(
                python_executable="/opt/voxelatlas-seg/bin/python",
                paths=paths,
            )
            self.assertEqual(plan.command[0], "/opt/voxelatlas-seg/bin/python")
            self.assertEqual(plan.command[1:3], ("-I", "-m"))
            self.assertIn("totalseg_download_weights", plan.command[3])
            self.assertEqual(plan.command[-2:], ("--task", "total"))
            self.assertFalse(plan.shell)

            self._write_weight_tree(paths.weights)
            created = create_weights_manifest(paths)
            loaded = load_weights_manifest(paths)
            self.assertEqual(loaded.sha256, created.sha256)
            self.assertEqual(loaded.task_ids, EXPECTED_TOTAL_WEIGHT_IDS)
            self.assertGreater(loaded.total_bytes, 0)

            next(paths.weights.rglob("*.pth")).write_bytes(b"drift")
            with self.assertRaises(TotalSegmentatorExecutionError):
                load_weights_manifest(paths)

    def test_weight_inventory_rejects_missing_ids_symlinks_and_empty_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_controlled_runtime_paths(Path(temporary))
            prepare_controlled_runtime(paths)
            self._write_weight_tree(paths.weights)
            missing = paths.weights / f"Dataset{EXPECTED_TOTAL_WEIGHT_IDS[-1]}_TotalSegmentator"
            for child in missing.iterdir():
                child.unlink()
            missing.rmdir()
            with self.assertRaises(TotalSegmentatorExecutionError):
                create_weights_manifest(paths)

    def test_memory_strategy_preserves_full_resolution_and_is_bounded(self) -> None:
        split = select_memory_strategy(
            total_memory_mib=5744,
            free_memory_mib=5200,
            source_shape=(112, 512, 574),
        )
        self.assertEqual(split, "force_split")
        direct = select_memory_strategy(
            total_memory_mib=24576,
            free_memory_mib=22000,
            source_shape=(112, 512, 574),
        )
        self.assertEqual(direct, "direct_full_resolution")
        with self.assertRaises(TotalSegmentatorExecutionError):
            select_memory_strategy(
                total_memory_mib=5744,
                free_memory_mib=MINIMUM_CUDA_FREE_MEMORY_MIB - 1,
                source_shape=(112, 512, 574),
            )

        invocation = build_totalsegmentator_invocation(
            python_executable="/opt/seg/bin/python",
            input_nifti=Path("/data/input.nii.gz"),
            output_nifti=Path("/data/labels.nii.gz"),
            report_json=Path("/data/report.json"),
            device_selector="cuda:0",
            force_split=True,
        )
        self.assertIn("--force_split", invocation.command)
        self.assertNotIn("--fast", invocation.command)
        self.assertNotIn("--fastest", invocation.command)
        self.assertNotIn("--save_lowres", invocation.command)

    def test_bridge_export_and_mask_reports_lock_patient_geometry_and_labels(self) -> None:
        source_sha = "a" * 64
        nifti_sha = "b" * 64
        affine = [
            [0.0, 0.0, -0.75, -10.0],
            [0.0, -0.5, 0.0, -20.0],
            [2.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        export = validate_bridge_export_report(
            {
                "schema_version": 1,
                "operation": "export",
                "source_artifact_sha256": source_sha,
                "source_descriptor_sha256": "c" * 64,
                "output_nifti_sha256": nifti_sha,
                "shape": [2, 3, 4],
                "dtype": "float32",
                "axis_order": ["slice", "row", "column"],
                "array_index_to_patient_ras": affine,
                "output_bytes": 100,
            },
            expected_source_sha256=source_sha,
            expected_descriptor_sha256="c" * 64,
            expected_shape=(2, 3, 4),
        )
        self.assertEqual(export["output_nifti_sha256"], nifti_sha)

        inspected = validate_mask_inspection_report(
            {
                "schema_version": 1,
                "operation": "inspect",
                "input_nifti_sha256": nifti_sha,
                "mask_nifti_sha256": "d" * 64,
                "shape": [2, 3, 4],
                "affine_matches_input": True,
                "integer_labels": True,
                "minimum_label": 0,
                "maximum_label": 117,
                "nonzero_voxels": 12,
                "present_labels": [0, 1, 117],
                "output_bytes": 80,
            },
            expected_input_sha256=nifti_sha,
            expected_shape=(2, 3, 4),
        )
        self.assertEqual(inspected["maximum_label"], 117)

        invalid = dict(inspected)
        invalid["maximum_label"] = 118
        with self.assertRaises(TotalSegmentatorExecutionError):
            validate_mask_inspection_report(
                invalid,
                expected_input_sha256=nifti_sha,
                expected_shape=(2, 3, 4),
            )

    def test_provider_report_rejects_cpu_fallback_or_reduced_resolution(self) -> None:
        classes = {str(index): f"class_{index}" for index in range(1, 118)}
        report = {
            "totalsegmentator_version": PINNED_TOTALSEGMENTATOR_VERSION,
            "nnunetv2_version": "2.8.1",
            "torch_version": "2.14.0+cu130",
            "task": "total",
            "modality": "CT",
            "license_required": False,
            "device": "gpu",
            "fast": False,
            "fastest": False,
            "save_lowres": False,
            "multilabel": True,
            "output_type": "nifti",
            "roi_subset": None,
            "input": "/private/job/input.nii.gz",
            "output": "/private/job/labels.nii.gz",
            "num_classes": 117,
            "classes": classes,
            "runtime_seconds": 321.5,
            "output_files": [],
        }
        public = validate_provider_run_report(
            report,
            expected_input=Path("/private/job/input.nii.gz"),
            expected_output=Path("/private/job/labels.nii.gz"),
        )
        self.assertEqual(public["task_definition_sha256"], EXPECTED_TOTAL_TASK_DEFINITION_SHA256)
        self.assertNotIn("input", public)
        self.assertNotIn("output", public)
        for mutation in ({"device": "cpu"}, {"fast": True}, {"save_lowres": True}):
            with self.subTest(mutation=mutation):
                with self.assertRaises(TotalSegmentatorExecutionError):
                    validate_provider_run_report(
                        {**report, **mutation},
                        expected_input=Path("/private/job/input.nii.gz"),
                        expected_output=Path("/private/job/labels.nii.gz"),
                    )

    def test_process_supervisor_enforces_cancellation_timeout_and_no_shell(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []
        process = FakeProcess(returncode=0, polls=2)

        def popen(command: list[str], **kwargs: object) -> FakeProcess:
            calls.append((command, kwargs))
            return process

        ticks = iter([0.0, 0.1, 0.2, 0.3])
        runner = SupervisedProcessRunner(
            popen=popen,
            monotonic=lambda: next(ticks),
            sleeper=lambda _: None,
        )
        with tempfile.TemporaryDirectory() as temporary:
            result = runner.run(
                ["/opt/runtime/python", "-I", "worker.py"],
                environment={"PATH": "/bin"},
                working_directory=Path(temporary),
                timeout_seconds=10,
                cancellation_check=lambda: False,
            )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(calls[0][1].get("shell", False))
        self.assertNotIn("stdout", result.public_dict())
        self.assertNotIn("stderr", result.public_dict())

        cancelled = FakeProcess(returncode=0, polls=5)
        runner = SupervisedProcessRunner(
            popen=lambda *args, **kwargs: cancelled,
            monotonic=lambda: 0.0,
            sleeper=lambda _: None,
        )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ProcessExecutionError) as caught:
                runner.run(
                    ["python", "worker.py"],
                    environment={},
                    working_directory=Path(temporary),
                    timeout_seconds=10,
                    cancellation_check=lambda: True,
                )
        self.assertEqual(caught.exception.code, "cancelled")
        self.assertTrue(cancelled.terminated)

        timed_out = FakeProcess(returncode=0, polls=5)
        timeout_ticks = iter([0.0, 11.0])
        runner = SupervisedProcessRunner(
            popen=lambda *args, **kwargs: timed_out,
            monotonic=lambda: next(timeout_ticks),
            sleeper=lambda _: None,
        )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ProcessExecutionError) as caught:
                runner.run(
                    ["python", "worker.py"],
                    environment={},
                    working_directory=Path(temporary),
                    timeout_seconds=10,
                    cancellation_check=lambda: False,
                )
        self.assertEqual(caught.exception.code, "timeout")
        self.assertTrue(timed_out.terminated)

    def test_process_supervisor_accepts_trusted_multiline_python_c_program_only(self) -> None:
        calls: list[list[str]] = []

        def popen(command: list[str], **kwargs: object) -> FakeProcess:
            del kwargs
            calls.append(command)
            return FakeProcess(returncode=0)

        runner = SupervisedProcessRunner(popen=popen)
        with tempfile.TemporaryDirectory() as temporary:
            result = runner.run(
                ["/opt/seg/python", "-I", "-c", _CUDA_PREFLIGHT_PROGRAM, "0"],
                environment={},
                working_directory=Path(temporary),
                timeout_seconds=60,
                cancellation_check=lambda: False,
                log_prefix="cuda-preflight",
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)

        invalid_commands = (
            ["python", "worker.py", "unsafe\npath"],
            ["python", "-c", "print('safe')\x00"],
        )
        for index, command in enumerate(invalid_commands):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaises(ProcessExecutionError) as caught:
                    runner.run(
                        command,
                        environment={},
                        working_directory=Path(temporary),
                        timeout_seconds=60,
                        cancellation_check=lambda: False,
                        log_prefix=f"invalid-{index}",
                    )
                self.assertEqual(caught.exception.code, "invalid_command")

    def test_provider_executes_isolated_pipeline_and_returns_only_safe_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary).resolve()
            paths = build_controlled_runtime_paths(data_dir)
            prepare_controlled_runtime(paths)
            self._write_weight_tree(paths.weights)
            weights = create_weights_manifest(paths)
            study_dir = data_dir / "studies" / ("a" * 32)
            derived = study_dir / "derived"
            derived.mkdir(parents=True)
            volume = derived / "volume.npy"
            volume.write_bytes(b"canonical-volume")
            descriptor = {
                "ready": True,
                "modality": "CT",
                "dtype": "float32",
                "shape": [112, 512, 574],
                "axis_order": ["slice", "row", "column"],
                "array_index_to_patient_lps": [
                    [0.0, 0.0, 0.75, 10.0],
                    [0.0, 0.5, 0.0, 20.0],
                    [2.0, 0.0, 0.0, 30.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
            }
            metadata = derived / "volume.json"
            metadata.write_text(json.dumps(descriptor), encoding="utf-8")
            canonical = lambda payload: json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode()
            from hashlib import sha256

            source = CanonicalSegmentationSource(
                study_id="a" * 32,
                study_instance_uid="1.2.3",
                source_series_uid="1.2.3.4",
                modality="CT",
                volume_created_at_utc="2026-09-08T00:00:00+00:00",
                descriptor_sha256=sha256(canonical(descriptor)).hexdigest(),
                artifact_sha256=sha256(volume.read_bytes()).hexdigest(),
                manifest_path=study_dir / "manifest.json",
                study_dir=study_dir,
                volume_path=volume,
                metadata_path=metadata,
            )
            bridge_script = ROOT / "scripts" / "phase5b2_nifti_worker.py"
            runtime_report = TotalSegmentatorRuntimeReport(
                qualified=True,
                status_code="qualified",
                message="qualified",
                cuda_devices=(TotalSegmentatorCudaDevice(0, "GPU", 5744),),
            )
            qualifier = Mock()
            qualifier.qualify.return_value = runtime_report

            class PipelineRunner:
                def run(self, command: object, **kwargs: object) -> ProcessExecutionResult:
                    command = list(command)  # type: ignore[arg-type]
                    work = Path(kwargs["working_directory"])
                    prefix = str(kwargs["log_prefix"])
                    work.mkdir(parents=True, exist_ok=True)
                    stdout = work / f"{prefix}.stdout.log"
                    stderr = work / f"{prefix}.stderr.log"
                    stderr.write_text("", encoding="utf-8")
                    if prefix == "cuda-preflight":
                        payload = {
                            "schema_version": 1,
                            "index": 0,
                            "name": "NVIDIA GeForce RTX 2060",
                            "free_memory_mib": 5200,
                            "total_memory_mib": 5744,
                            "compute_capability": [7, 5],
                            "execution_result": 65536.0,
                        }
                    elif prefix == "nifti-export":
                        output = Path(command[command.index("--output-nifti") + 1])
                        output.write_bytes(b"nifti-input")
                        payload = {
                            "schema_version": 1,
                            "operation": "export",
                            "source_artifact_sha256": source.artifact_sha256,
                            "source_descriptor_sha256": source.descriptor_sha256,
                            "output_nifti_sha256": sha256(output.read_bytes()).hexdigest(),
                            "shape": [112, 512, 574],
                            "dtype": "float32",
                            "axis_order": ["slice", "row", "column"],
                            "array_index_to_patient_ras": [
                                [0.0, 0.0, -0.75, -10.0],
                                [0.0, -0.5, 0.0, -20.0],
                                [2.0, 0.0, 0.0, 30.0],
                                [0.0, 0.0, 0.0, 1.0],
                            ],
                            "output_bytes": output.stat().st_size,
                        }
                    elif prefix == "totalsegmentator":
                        if "--force_split" not in command or "--fast" in command:
                            raise AssertionError("full-resolution memory strategy changed")
                        output = Path(command[command.index("-o") + 1])
                        report_path = Path(command[command.index("--report") + 1])
                        output.write_bytes(b"labels")
                        report_path.write_text(
                            json.dumps(
                                {
                                    "totalsegmentator_version": PINNED_TOTALSEGMENTATOR_VERSION,
                                    "nnunetv2_version": "2.8.1",
                                    "torch_version": "2.14.0+cu130",
                                    "task": "total",
                                    "modality": "CT",
                                    "license_required": False,
                                    "device": "gpu",
                                    "fast": False,
                                    "fastest": False,
                                    "save_lowres": False,
                                    "multilabel": True,
                                    "output_type": "nifti",
                                    "roi_subset": None,
                                    "input": command[command.index("-i") + 1],
                                    "output": str(output),
                                    "num_classes": 117,
                                    "classes": {
                                        str(index): f"class_{index}" for index in range(1, 118)
                                    },
                                    "runtime_seconds": 300.0,
                                    "output_files": [],
                                }
                            ),
                            encoding="utf-8",
                        )
                        payload = {"status": "complete"}
                    else:
                        input_path = Path(command[command.index("--input-nifti") + 1])
                        mask_path = Path(command[command.index("--mask-nifti") + 1])
                        payload = {
                            "schema_version": 1,
                            "operation": "inspect",
                            "input_nifti_sha256": sha256(input_path.read_bytes()).hexdigest(),
                            "mask_nifti_sha256": sha256(mask_path.read_bytes()).hexdigest(),
                            "shape": [112, 512, 574],
                            "affine_matches_input": True,
                            "integer_labels": True,
                            "minimum_label": 0,
                            "maximum_label": 117,
                            "nonzero_voxels": 1000,
                            "present_labels": [0, 1, 117],
                            "output_bytes": mask_path.stat().st_size,
                        }
                    stdout.write_text(json.dumps(payload), encoding="utf-8")
                    return ProcessExecutionResult(0, 1.0, stdout, stderr)

            provider = TotalSegmentatorProvider(
                data_dir=data_dir,
                python_executable="/opt/seg/python",
                bridge_script=bridge_script,
                process_runner=PipelineRunner(),  # type: ignore[arg-type]
                runtime_qualifier=qualifier,
            )
            progress: list[tuple[str, float]] = []
            context = SegmentationExecutionContext(
                job_id="seg-" + "b" * 32,
                source=source,
                model=provider.descriptor,
                device=SegmentationDevice(
                    kind="cuda",
                    selector="cuda:0",
                    name="NVIDIA GeForce RTX 2060",
                    index=0,
                    total_memory_mib=5744,
                    free_memory_mib=5200,
                ),
                parameters={
                    "task": "total",
                    "output_mode": "multilabel_nifti",
                    "resolution": "full",
                },
                progress_reporter=lambda **values: progress.append(
                    (str(values["stage"]), float(values["percent"]))
                ),
                cancellation_check=lambda: False,
            )
            result = provider.run(context)
            self.assertEqual(result.outcome["code"], "qualified_execution")
            self.assertEqual(result.outcome["weights_manifest_sha256"], weights.sha256)
            self.assertEqual(result.outcome["memory_strategy"], "force_split")
            self.assertFalse(any(str(value).startswith("/") for value in result.outcome.values()))
            self.assertEqual(progress[-1], ("finalizing", 98.0))
            qualifier.qualify.assert_called_once_with("/opt/seg/python")

    def test_phase_boundary_scripts_and_docs_are_present(self) -> None:
        worker = (ROOT / "scripts" / "phase5b2_nifti_worker.py").read_text(encoding="utf-8")
        runner = (ROOT / "scripts" / "run_phase5b2_checks.sh").read_text(encoding="utf-8")
        doc = (
            ROOT
            / "docs"
            / "phase_history"
            / "PHASE5B2_TOTALSEGMENTATOR_EXECUTION_QUALIFICATION.md"
        ).read_text(encoding="utf-8")
        self.assertIn("LPS", worker)
        self.assertIn("RAS", worker)
        self.assertNotIn("import torch", (BACKEND / "voxelatlas" / "totalsegmentator_execution.py").read_text(encoding="utf-8"))
        self.assertIn("bash scripts/run_phase5b1_checks.sh", runner)
        self.assertIn("CLINICAL_VALIDATION=NOT_CLAIMED", runner)
        self.assertIn("Phase 5C", doc)


if __name__ == "__main__":
    unittest.main()
