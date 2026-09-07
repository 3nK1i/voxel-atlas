from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.segmentation import (  # noqa: E402
    SegmentationConflictError,
    SegmentationDevice,
    SegmentationDeviceSelector,
    SegmentationExecutionRequirements,
    SegmentationJobService,
    SegmentationModelDescriptor,
    SegmentationModelRegistry,
    SegmentationProviderResult,
    SegmentationUnavailableError,
    SegmentationValidationError,
    build_default_segmentation_registry,
)


STUDY_ID = "a" * 32


def write_canonical_volume(root: Path, *, modality: str = "CT") -> tuple[Path, dict[str, object]]:
    study_dir = root / "studies" / STUDY_ID
    derived_dir = study_dir / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    (derived_dir / "volume.npy").write_bytes(b"voxelatlas-canonical-volume")
    descriptor: dict[str, object] = {
        "schema_version": 1,
        "ready": True,
        "created_at_utc": "2026-09-07T12:00:00+00:00",
        "source_series_uid": "1.2.840.series",
        "source_instance_count": 2,
        "modality": modality,
        "dtype": "float32",
        "shape": [2, 3, 4],
        "axis_order": ["slice", "row", "column"],
        "spacing_mm": [2.0, 0.5, 0.75],
        "origin_patient_lps_mm": [10.0, 20.0, 30.0],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 0.75, 10.0],
            [0.0, 0.5, 0.0, 20.0],
            [2.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "intensity_units": "HU" if modality == "CT" else "modality",
        "value_range": [-1024.0, 1500.0] if modality == "CT" else [0.0, 900.0],
        "artifact_path": "derived/volume.npy",
        "metadata_path": "derived/volume.json",
    }
    (derived_dir / "volume.json").write_text(
        json.dumps(descriptor, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 5,
        "study_id": STUDY_ID,
        "study_instance_uid": "1.2.840.study",
        "created_at_utc": "2026-09-07T11:00:00+00:00",
        "modalities": [modality],
        "reconstruction_ready": True,
        "reconstruction_series_uid": "1.2.840.series",
        "series": [],
        "volume": descriptor,
    }
    (study_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return study_dir, descriptor


def available_model(
    *,
    modalities: tuple[str, ...] = ("CT",),
    devices: tuple[str, ...] = ("cuda", "cpu"),
    version: str = "1.0.0",
) -> SegmentationModelDescriptor:
    return SegmentationModelDescriptor(
        provider_id="test-provider",
        provider_version="1.0.0",
        model_id="whole-body",
        model_version=version,
        display_name="Test whole-body model",
        task="multi_structure",
        capabilities=("anatomical_segmentation", "full_resolution"),
        supported_modalities=modalities,
        available=True,
        availability_reason=None,
        execution=SegmentationExecutionRequirements(
            supported_devices=devices,
            minimum_cuda_memory_mib=4096,
        ),
    )


class RecordingProvider:
    def __init__(self, descriptor: SegmentationModelDescriptor | None = None) -> None:
        self.descriptor = available_model() if descriptor is None else descriptor
        self.received_parameters: dict[str, object] | None = None

    def validate_parameters(self, parameters: dict[str, object]) -> dict[str, object]:
        if set(parameters) - {"fast"}:
            raise SegmentationValidationError("Unsupported model parameter")
        return {"fast": bool(parameters.get("fast", False))}

    def run(self, context) -> SegmentationProviderResult:
        self.received_parameters = context.parameters
        context.report_progress(
            stage="loading_model",
            percent=10.0,
            message="Loading qualified provider",
        )
        context.raise_if_cancelled()
        context.report_progress(
            stage="inference",
            percent=80.0,
            message="Running provider",
        )
        return SegmentationProviderResult(
            outcome={"provider_run_id": "test-run", "output_kind": "provider_native"}
        )


class FailingProvider(RecordingProvider):
    def run(self, context) -> SegmentationProviderResult:
        del context
        raise RuntimeError("/private/patient/location credential=should-not-leak")


def registry_with_provider(
    provider: RecordingProvider | None = None,
) -> tuple[SegmentationModelRegistry, RecordingProvider]:
    runtime = RecordingProvider() if provider is None else provider
    registry = SegmentationModelRegistry()
    registry.register_provider(runtime)
    return registry, runtime


def gpu_devices() -> tuple[SegmentationDevice, ...]:
    return (
        SegmentationDevice(
            kind="cuda",
            selector="cuda:0",
            name="GPU Small",
            index=0,
            total_memory_mib=6144,
            free_memory_mib=5000,
        ),
        SegmentationDevice(
            kind="cuda",
            selector="cuda:1",
            name="GPU Large",
            index=1,
            total_memory_mib=32768,
            free_memory_mib=25000,
        ),
    )


class Phase5AModelRegistryTests(unittest.TestCase):
    def test_default_registry_declares_totalsegmentator_as_ct_only_and_unavailable(self) -> None:
        registry = build_default_segmentation_registry()
        models = registry.list_public()

        self.assertEqual(len(models), 1)
        model = models[0]
        self.assertEqual(model["provider_id"], "totalsegmentator")
        self.assertEqual(model["model_id"], "total")
        self.assertEqual(model["supported_modalities"], ["CT"])
        self.assertFalse(model["available"])
        self.assertIn("Phase 5B", model["availability_reason"])
        self.assertNotIn("MR", model["supported_modalities"])

    def test_registry_order_is_deterministic_and_duplicate_identity_is_rejected(self) -> None:
        first = replace(available_model(), model_id="z-model", display_name="Z")
        second = replace(available_model(), model_id="a-model", display_name="A")
        registry = SegmentationModelRegistry((first, second))

        self.assertEqual(
            [item["model_id"] for item in registry.list_public()],
            ["a-model", "z-model"],
        )
        with self.assertRaisesRegex(SegmentationValidationError, "duplicate"):
            registry.register_descriptor(first)

    def test_model_descriptor_rejects_ambiguous_modality_or_identity(self) -> None:
        with self.assertRaises(SegmentationValidationError):
            replace(available_model(), supported_modalities=("CT", "ct"))
        with self.assertRaises(SegmentationValidationError):
            replace(available_model(), model_id="../../model")


class Phase5ADevicePolicyTests(unittest.TestCase):
    def test_auto_selects_most_available_compatible_gpu_deterministically(self) -> None:
        selector = SegmentationDeviceSelector(discovery=gpu_devices)
        selected = selector.select(available_model(), "auto")

        self.assertEqual(selected.selector, "cuda:1")
        self.assertEqual(selected.free_memory_mib, 25000)

    def test_explicit_cuda_cpu_and_invalid_requests_are_never_silently_changed(self) -> None:
        selector = SegmentationDeviceSelector(discovery=gpu_devices)

        self.assertEqual(selector.select(available_model(), "cuda:0").selector, "cuda:0")
        self.assertEqual(selector.select(available_model(), "cpu").selector, "cpu")
        with self.assertRaisesRegex(SegmentationUnavailableError, "cuda:7"):
            selector.select(available_model(), "cuda:7")
        with self.assertRaisesRegex(SegmentationValidationError, "device"):
            selector.select(available_model(), "../../gpu")

    def test_auto_uses_cpu_only_when_the_model_explicitly_permits_it(self) -> None:
        cpu_model = available_model(devices=("cpu",))
        cuda_model = available_model(devices=("cuda",))
        selector = SegmentationDeviceSelector(discovery=lambda: ())

        self.assertEqual(selector.select(cpu_model, "auto").selector, "cpu")
        with self.assertRaisesRegex(SegmentationUnavailableError, "compatible"):
            selector.select(cuda_model, "auto")


class Phase5AJobLifecycleTests(unittest.TestCase):
    def make_service(
        self,
        root: Path,
        *,
        registry: SegmentationModelRegistry | None = None,
        devices=gpu_devices,
    ) -> SegmentationJobService:
        selected_registry, _ = registry_with_provider() if registry is None else (registry, None)
        identifiers = iter(("1" * 32, "2" * 32, "3" * 32))
        return SegmentationJobService(
            data_dir=root,
            registry=selected_registry,
            device_discovery=devices,
            id_factory=lambda: next(identifiers),
        )

    def test_job_manifest_is_atomic_safe_and_bound_to_the_canonical_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, descriptor = write_canonical_volume(root)
            canonical_before = (study_dir / "derived" / "volume.npy").read_bytes()
            service = self.make_service(root)

            job = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="auto",
                parameters={"fast": True},
            )
            manifest_path = (
                root / "segmentation" / "jobs" / job["job_id"] / "manifest.json"
            )
            stored = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(job["job_id"], "seg-" + "1" * 32)
            self.assertEqual(job["state"], "queued")
            self.assertEqual(job["provenance"]["source_study_id"], STUDY_ID)
            self.assertEqual(
                job["provenance"]["canonical_volume_descriptor_sha256"],
                service.canonical_json_sha256(descriptor),
            )
            self.assertEqual(len(job["provenance"]["canonical_volume_artifact_sha256"]), 64)
            self.assertEqual(job["provenance"]["selected_device"]["selector"], "cuda:1")
            self.assertEqual(job["provenance"]["parameters"], {"fast": True})
            self.assertEqual(len(stored["provenance_sha256"]), 64)
            self.assertEqual((study_dir / "derived" / "volume.npy").read_bytes(), canonical_before)
            self.assertEqual(list(manifest_path.parent.glob("*.tmp")), [])
            self.assertNotIn(str(root), json.dumps(job))

    def test_ct_model_cannot_be_created_for_mr_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root, modality="MR")
            service = self.make_service(root)

            with self.assertRaisesRegex(SegmentationConflictError, "MR"):
                service.create_job(
                    provider_id="test-provider",
                    model_id="whole-body",
                    device_request="auto",
                    parameters={},
                )
            self.assertFalse((root / "segmentation").exists())

    def test_unavailable_model_never_creates_a_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            service = SegmentationJobService(
                data_dir=root,
                registry=build_default_segmentation_registry(),
                device_discovery=lambda: (),
            )

            with self.assertRaisesRegex(SegmentationUnavailableError, "Phase 5B"):
                service.create_job(
                    provider_id="totalsegmentator",
                    model_id="total",
                    device_request="auto",
                    parameters={},
                )
            self.assertFalse((root / "segmentation").exists())

    def test_transitions_progress_and_cancellation_are_validated_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            service = self.make_service(root)
            job = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
            )
            job_id = job["job_id"]

            with self.assertRaisesRegex(SegmentationConflictError, "queued"):
                service.complete_job(job_id, SegmentationProviderResult(outcome={}))
            self.assertEqual(service.begin_job(job_id)["state"], "starting")
            self.assertEqual(service.mark_running(job_id)["state"], "running")
            progress = service.report_progress(
                job_id,
                stage="inference",
                percent=45.0,
                message="Segmenting anatomy",
            )
            self.assertEqual(progress["progress"]["percent"], 45.0)
            with self.assertRaisesRegex(SegmentationConflictError, "monotonic"):
                service.report_progress(
                    job_id,
                    stage="loading_model",
                    percent=20.0,
                    message="Moving backwards",
                )
            first_cancel = service.cancel_job(job_id)
            second_cancel = service.cancel_job(job_id)
            self.assertEqual(first_cancel["state"], "cancelling")
            self.assertEqual(second_cancel, first_cancel)
            cancelled = service.mark_cancelled(job_id)
            self.assertEqual(cancelled["state"], "cancelled")
            self.assertEqual(service.cancel_job(job_id), cancelled)

    def test_queued_cancellation_is_immediately_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            service = self.make_service(root)
            job = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
            )

            cancelled = service.cancel_job(job["job_id"])

            self.assertEqual(cancelled["state"], "cancelled")
            self.assertIsNotNone(cancelled["completed_at_utc"])

    def test_run_job_uses_provider_contract_and_records_terminal_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            registry, provider = registry_with_provider()
            service = self.make_service(root, registry=registry)
            job = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={"fast": True},
            )

            completed = service.run_job(job["job_id"])

            self.assertEqual(completed["state"], "succeeded")
            self.assertEqual(completed["progress"]["percent"], 100.0)
            self.assertEqual(completed["outcome"]["provider_run_id"], "test-run")
            self.assertEqual(provider.received_parameters, {"fast": True})
            self.assertEqual(
                completed["terminal_provenance"]["terminal_state"],
                "succeeded",
            )
            self.assertEqual(
                completed["terminal_provenance"]["outcome"],
                completed["outcome"],
            )
            self.assertEqual(len(completed["terminal_provenance_sha256"]), 64)

    def test_unexpected_provider_failure_is_recorded_without_leaking_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            registry, _ = registry_with_provider(FailingProvider())
            service = self.make_service(root, registry=registry)
            job = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
            )

            failed = service.run_job(job["job_id"])

            self.assertEqual(failed["state"], "failed")
            self.assertEqual(failed["outcome"]["code"], "provider_failure")
            self.assertEqual(
                failed["outcome"]["message"],
                "Segmentation provider execution failed",
            )
            self.assertNotIn("patient", json.dumps(failed).lower())
            self.assertNotIn("credential", json.dumps(failed).lower())

    def test_interrupted_job_is_failed_durably_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            registry, _ = registry_with_provider()
            service = self.make_service(root, registry=registry)
            job = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
            )
            service.begin_job(job["job_id"])
            service.mark_running(job["job_id"])

            recovered = SegmentationJobService(
                data_dir=root,
                registry=registry,
                device_discovery=lambda: (),
            ).get_job(job["job_id"])

            self.assertEqual(recovered["state"], "failed")
            self.assertEqual(recovered["outcome"]["code"], "interrupted")
            self.assertNotIn(str(root), json.dumps(recovered))

    def test_provenance_source_and_model_drift_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, descriptor = write_canonical_volume(root)
            registry, provider = registry_with_provider()
            service = self.make_service(root, registry=registry)
            first = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
            )
            descriptor["created_at_utc"] = "2026-09-07T13:00:00+00:00"
            (study_dir / "derived" / "volume.json").write_text(
                json.dumps(descriptor, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            manifest_path = study_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["volume"] = descriptor
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SegmentationConflictError, "canonical volume changed"):
                service.begin_job(first["job_id"])

            write_canonical_volume(root)
            second = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
            )
            provider.descriptor = replace(provider.descriptor, model_version="2.0.0")
            with self.assertRaisesRegex(SegmentationConflictError, "registered model changed"):
                service.begin_job(second["job_id"])

    def test_manifest_provenance_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            service = self.make_service(root)
            job = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
            )
            manifest_path = (
                root / "segmentation" / "jobs" / job["job_id"] / "manifest.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["provenance"]["model_version"] = "tampered"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SegmentationValidationError, "immutable provenance"):
                service.get_job(job["job_id"])

    def test_terminal_timestamp_or_outcome_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            service = self.make_service(root)
            job = service.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
            )
            cancelled = service.cancel_job(job["job_id"])
            manifest_path = (
                root / "segmentation" / "jobs" / cancelled["job_id"] / "manifest.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["completed_at_utc"] = "2099-01-01T00:00:00+00:00"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                SegmentationValidationError,
                "immutable terminal provenance",
            ):
                service.get_job(job["job_id"])

    def test_invalid_identifier_cannot_escape_the_job_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            service = self.make_service(root)

            with self.assertRaisesRegex(SegmentationValidationError, "job identifier"):
                service.get_job("../../manifest")

    def test_symlinked_job_repository_cannot_redirect_runtime_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp)
            write_canonical_volume(root)
            (root / "segmentation").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(SegmentationValidationError, "unsafe"):
                self.make_service(root)
            self.assertEqual(list(outside.iterdir()), [])


class Phase5AHttpContractTests(unittest.TestCase):
    def test_segmentation_http_contract_is_authenticated_safe_and_no_store(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from voxelatlas import config
            from voxelatlas.app import create_app
            from voxelatlas.passwords import hash_password
        except ModuleNotFoundError as exc:  # pragma: no cover - workstation dependency profile
            self.skipTest(f"HTTP test dependencies unavailable: {exc}")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            registry, _ = registry_with_provider()
            service = SegmentationJobService(
                data_dir=root,
                registry=registry,
                device_discovery=lambda: (),
                id_factory=lambda: "2" * 32,
            )
            settings = config.AppSettings(
                environment="test",
                session_secret="x" * 48,
                secure_cookies=False,
                session_cookie_name="voxelatlas_session",
                allowed_hosts=("testserver", "127.0.0.1", "localhost"),
                data_dir=root,
                max_upload_mib=512,
                auth_username="engineer",
                auth_password_hash=hash_password("correct horse battery staple"),
                session_ttl_minutes=60,
            )
            with TestClient(create_app(settings=settings, segmentation_service=service)) as client:
                denied = client.get("/api/segmentation/models")
                client.post(
                    "/api/auth/login",
                    json={"username": "engineer", "password": "correct horse battery staple"},
                )
                models = client.get("/api/segmentation/models")
                devices = client.get("/api/segmentation/devices")
                created = client.post(
                    "/api/segmentation/jobs",
                    json={
                        "provider_id": "test-provider",
                        "model_id": "whole-body",
                        "device": "cpu",
                        "parameters": {"fast": True},
                    },
                )
                job_id = created.json()["job"]["job_id"]
                listed = client.get("/api/segmentation/jobs")
                inspected = client.get(f"/api/segmentation/jobs/{job_id}")
                cancelled = client.post(f"/api/segmentation/jobs/{job_id}/cancel")
                invalid = client.get("/api/segmentation/jobs/not-a-valid-id")

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(models.status_code, 200)
        self.assertEqual(devices.status_code, 200)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(inspected.status_code, 200)
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(invalid.status_code, 422)
        for response in (models, devices, created, listed, inspected, cancelled, invalid):
            self.assertEqual(response.headers.get("cache-control"), "no-store")
            self.assertNotIn(str(root), response.text)
        self.assertEqual(cancelled.json()["job"]["state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
