from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.segmentation import (  # noqa: E402
    SegmentationDevice,
    SegmentationExecutionRequirements,
    SegmentationJobService,
    SegmentationModelDescriptor,
    SegmentationModelRegistry,
    SegmentationProviderResult,
    SegmentationValidationError,
)
from voxelatlas.segmentation_label_maps import (  # noqa: E402
    SegmentationLabelMapService,
)


STUDY_ID = "a" * 32
TASK_DEFINITION_SHA256 = "d" * 64
IDENTITY_MATRIX = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]
PATIENT_LPS_AFFINE = [
    [0.0, 0.0, 0.75, 10.0],
    [0.0, 0.5, 0.0, 20.0],
    [2.0, 0.0, 0.0, 30.0],
    [0.0, 0.0, 0.0, 1.0],
]


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_canonical_volume(root: Path) -> tuple[Path, dict[str, object]]:
    study_dir = root / "studies" / STUDY_ID
    derived = study_dir / "derived"
    derived.mkdir(parents=True)
    volume = np.arange(24, dtype=np.float32).reshape((2, 3, 4))
    np.save(derived / "volume.npy", volume, allow_pickle=False)
    descriptor: dict[str, object] = {
        "schema_version": 1,
        "ready": True,
        "created_at_utc": "2026-09-08T10:00:00+00:00",
        "source_series_uid": "1.2.840.series",
        "source_instance_count": 2,
        "modality": "CT",
        "dtype": "float32",
        "shape": [2, 3, 4],
        "axis_order": ["slice", "row", "column"],
        "spacing_mm": [2.0, 0.5, 0.75],
        "origin_patient_lps_mm": [10.0, 20.0, 30.0],
        "array_index_to_patient_lps": PATIENT_LPS_AFFINE,
        "intensity_units": "HU",
        "value_range": [-1024.0, 1500.0],
        "artifact_path": "derived/volume.npy",
        "metadata_path": "derived/volume.json",
    }
    (derived / "volume.json").write_text(
        json.dumps(descriptor, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 5,
        "study_id": STUDY_ID,
        "study_instance_uid": "1.2.840.study",
        "created_at_utc": "2026-09-08T09:00:00+00:00",
        "modalities": ["CT"],
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


def test_model() -> SegmentationModelDescriptor:
    return SegmentationModelDescriptor(
        provider_id="test-provider",
        provider_version="1.0.0",
        model_id="whole-body",
        model_version="1.0.0",
        display_name="Test whole-body model",
        task="multi_structure",
        capabilities=("anatomical_segmentation", "full_resolution"),
        supported_modalities=("CT",),
        available=True,
        availability_reason=None,
        execution=SegmentationExecutionRequirements(supported_devices=("cpu",)),
    )


class ArtifactProvider:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.descriptor = test_model()

    def validate_parameters(self, parameters: dict[str, object]) -> dict[str, object]:
        if parameters:
            raise SegmentationValidationError("parameters are unsupported")
        return {}

    def run(self, context) -> SegmentationProviderResult:
        relative = Path("provider/test-provider/output/labels.nii.gz")
        mask = self.root / "segmentation" / "jobs" / context.job_id / relative
        mask.parent.mkdir(parents=True, exist_ok=True)
        mask.write_bytes(b"qualified-provider-mask")
        return SegmentationProviderResult(
            outcome={
                "code": "qualified_execution",
                "message": "Full-resolution non-clinical CT segmentation completed",
                "provider": {
                    "provider_version": "1.0.0",
                    "task": "multi_structure",
                    "modality": "CT",
                    "device": "cpu",
                    "resolution": "full",
                    "output_mode": "multilabel_nifti",
                    "class_count": 3,
                    "task_definition_sha256": TASK_DEFINITION_SHA256,
                    "runtime_seconds": 1.0,
                },
                "weights_manifest_sha256": "e" * 64,
                "memory_strategy": "standard",
                "input_nifti_sha256": "f" * 64,
                "mask_nifti_sha256": file_sha256(mask),
                "mask_bytes": mask.stat().st_size,
                "present_labels": [0, 1, 3],
                "nonzero_voxels": 2,
                "mask_artifact": relative.as_posix(),
                "provider_runtime_seconds": 1.0,
                "supervisor_runtime_seconds": 1.0,
                "clinical_validation": "not_claimed",
            }
        )


def successful_job(root: Path) -> dict[str, object]:
    write_canonical_volume(root)
    provider = ArtifactProvider(root)
    registry = SegmentationModelRegistry()
    registry.register_provider(provider)
    service = SegmentationJobService(
        data_dir=root,
        registry=registry,
        device_discovery=lambda: (),
        id_factory=lambda: "1" * 32,
    )
    job = service.create_job(
        provider_id="test-provider",
        model_id="whole-body",
        device_request="cpu",
        parameters={},
        source_study_id=STUDY_ID,
    )
    return service.run_job(str(job["job_id"]))


@dataclass
class Completed:
    returncode: int
    stdout: str
    stderr: str = ""


class CanonicalizingRunner:
    def __init__(self, *, mutation: str | None = None) -> None:
        self.mutation = mutation
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: object) -> Completed:
        self.commands.append(list(command))
        self.assert_safe_invocation(command, kwargs)
        output = Path(command[command.index("--output-npy") + 1])
        source = Path(command[command.index("--source-npy") + 1])
        metadata_path = Path(command[command.index("--source-json") + 1])
        mask = Path(command[command.index("--mask-nifti") + 1])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        labels = np.zeros(tuple(metadata["shape"]), dtype=np.uint16)
        labels.flat[1] = 1
        labels.flat[2] = 3
        with output.open("xb") as handle:
            np.save(handle, labels, allow_pickle=False)
        report: dict[str, object] = {
            "schema_version": 1,
            "operation": "canonicalize_label_map",
            "source_artifact_sha256": file_sha256(source),
            "source_descriptor_sha256": canonical_sha256(metadata),
            "provider_mask_sha256": file_sha256(mask),
            "canonical_label_map_sha256": file_sha256(output),
            "canonical_label_map_bytes": output.stat().st_size,
            "shape": metadata["shape"],
            "dtype": "uint16",
            "axis_order": ["slice", "row", "column"],
            "coordinate_system": "patient_lps",
            "length_units": "mm",
            "array_index_to_patient_lps": metadata["array_index_to_patient_lps"],
            "model_index_to_patient_lps": metadata["array_index_to_patient_lps"],
            "source_to_model_index": IDENTITY_MATRIX,
            "model_to_source_index": IDENTITY_MATRIX,
            "resampled": False,
            "interpolation": "none",
            "minimum_label": 0,
            "maximum_label": 3,
            "present_labels": [0, 1, 3],
            "nonzero_voxels": 2,
        }
        if self.mutation == "labels":
            report["present_labels"] = [0, 1]
        elif self.mutation == "affine":
            report["model_index_to_patient_lps"] = IDENTITY_MATRIX
        elif self.mutation == "transform":
            report["source_to_model_index"] = [row[:] for row in IDENTITY_MATRIX]
            report["source_to_model_index"][0][3] = 1.0  # type: ignore[index]
        return Completed(returncode=0, stdout=json.dumps(report))

    @staticmethod
    def assert_safe_invocation(command: list[str], kwargs: dict[str, object]) -> None:
        if kwargs.get("shell") is not False:
            raise AssertionError("worker must not use a shell")
        if kwargs.get("check") is not False or kwargs.get("capture_output") is not True:
            raise AssertionError("worker process must be bounded and captured")
        if "-I" not in command:
            raise AssertionError("worker Python must be isolated")


def make_import_service(
    root: Path,
    runner: CanonicalizingRunner | None = None,
) -> tuple[SegmentationLabelMapService, CanonicalizingRunner, Path]:
    selected_runner = CanonicalizingRunner() if runner is None else runner
    worker = root / "phase5c_worker.py"
    worker.write_text("# test worker\n", encoding="utf-8")
    service = SegmentationLabelMapService(data_dir=root, worker_runner=selected_runner)
    return service, selected_runner, worker


class Phase5CCanonicalImportTests(unittest.TestCase):
    def test_succeeded_job_import_is_immutable_idempotent_and_patient_lps_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = successful_job(root)
            service, runner, worker = make_import_service(root)

            first = service.import_succeeded_job(
                job_id=str(job["job_id"]),
                python_executable="/opt/seg/python",
                worker_script=worker,
            )
            second = service.import_succeeded_job(
                job_id=str(job["job_id"]),
                python_executable="/opt/seg/python",
                worker_script=worker,
            )

            self.assertEqual(first, second)
            self.assertRegex(str(first["label_map_id"]), r"^map-[0-9a-f]{32}$")
            self.assertEqual(first["state"], "ready")
            self.assertRegex(str(first["identity_sha256"]), r"^[0-9a-f]{64}$")
            self.assertRegex(str(first["provenance_sha256"]), r"^[0-9a-f]{64}$")
            self.assertEqual(first["source_study_id"], STUDY_ID)
            self.assertEqual(first["source_study_instance_uid"], "1.2.840.study")
            self.assertEqual(first["segmentation_job_id"], job["job_id"])
            self.assertEqual(first["coordinate_system"], "patient_lps")
            self.assertEqual(first["length_units"], "mm")
            self.assertEqual(first["shape"], [2, 3, 4])
            self.assertEqual(first["dtype"], "uint16")
            self.assertEqual(first["array_index_to_patient_lps"], PATIENT_LPS_AFFINE)
            self.assertEqual(first["source_to_model_index"], IDENTITY_MATRIX)
            self.assertEqual(first["model_to_source_index"], IDENTITY_MATRIX)
            self.assertFalse(first["resampled"])
            self.assertEqual(first["interpolation"], "none")
            self.assertEqual(first["present_labels"], [0, 1, 3])
            self.assertEqual(first["clinical_validation"], "not_claimed")
            self.assertNotIn(str(root), json.dumps(first))
            self.assertEqual(service.get(str(first["label_map_id"])), first)
            self.assertEqual(service.list(study_id=STUDY_ID), [first])
            self.assertEqual(len(runner.commands), 1, "second import must reuse sealed artifact")

            map_root = root / "segmentation" / "label-maps" / str(first["label_map_id"])
            manifest = json.loads((map_root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["provenance_sha256"],
                canonical_sha256(manifest["provenance"]),
            )
            artifact = map_root / "labels.npy"
            self.assertEqual(file_sha256(artifact), first["artifact_sha256"])

            artifact.write_bytes(b"tampered")
            with self.assertRaisesRegex(SegmentationValidationError, "artifact.*changed"):
                service.get(str(first["label_map_id"]))

    def test_import_rejects_nonterminal_job_and_changed_source_or_provider_mask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_volume(root)
            service, _, worker = make_import_service(root)
            provider = ArtifactProvider(root)
            registry = SegmentationModelRegistry()
            registry.register_provider(provider)
            jobs = SegmentationJobService(
                data_dir=root,
                registry=registry,
                device_discovery=lambda: (),
                id_factory=lambda: "2" * 32,
            )
            queued = jobs.create_job(
                provider_id="test-provider",
                model_id="whole-body",
                device_request="cpu",
                parameters={},
                source_study_id=STUDY_ID,
            )
            with self.assertRaisesRegex(SegmentationValidationError, "succeeded"):
                service.import_succeeded_job(
                    job_id=str(queued["job_id"]),
                    python_executable="/opt/seg/python",
                    worker_script=worker,
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = successful_job(root)
            service, _, worker = make_import_service(root)
            volume = root / "studies" / STUDY_ID / "derived" / "volume.npy"
            volume.write_bytes(volume.read_bytes() + b"drift")
            with self.assertRaisesRegex(SegmentationValidationError, "source.*changed"):
                service.import_succeeded_job(
                    job_id=str(job["job_id"]),
                    python_executable="/opt/seg/python",
                    worker_script=worker,
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = successful_job(root)
            service, _, worker = make_import_service(root)
            mask = (
                root
                / "segmentation"
                / "jobs"
                / str(job["job_id"])
                / "provider/test-provider/output/labels.nii.gz"
            )
            mask.write_bytes(mask.read_bytes() + b"drift")
            with self.assertRaisesRegex(SegmentationValidationError, "Provider mask.*changed"):
                service.import_succeeded_job(
                    job_id=str(job["job_id"]),
                    python_executable="/opt/seg/python",
                    worker_script=worker,
                )

    def test_worker_report_rejects_label_geometry_and_transform_drift(self) -> None:
        for mutation, message in (
            ("labels", "label inventory"),
            ("affine", "Model Patient LPS"),
            ("transform", "transform"),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                job = successful_job(root)
                service, _, worker = make_import_service(
                    root,
                    CanonicalizingRunner(mutation=mutation),
                )
                with self.assertRaisesRegex(SegmentationValidationError, message):
                    service.import_succeeded_job(
                        job_id=str(job["job_id"]),
                        python_executable="/opt/seg/python",
                        worker_script=worker,
                    )
                maps = root / "segmentation" / "label-maps"
                self.assertEqual(
                    [item for item in maps.iterdir() if not item.name.startswith(".import-")],
                    [],
                )

    def test_identifier_and_symlink_boundaries_cannot_escape_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = SegmentationLabelMapService(data_dir=Path(tmp))
            with self.assertRaisesRegex(SegmentationValidationError, "label-map identifier"):
                service.get("../../labels")

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            segmentation = root / "segmentation"
            segmentation.mkdir()
            (segmentation / "label-maps").symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaisesRegex(SegmentationValidationError, "unsafe"):
                SegmentationLabelMapService(data_dir=root)
            self.assertEqual(list(Path(outside).iterdir()), [])


class Phase5CWorkerGeometryTests(unittest.TestCase):
    @staticmethod
    def load_worker_module():
        path = ROOT / "scripts" / "phase5c_label_map_worker.py"
        spec = importlib.util.spec_from_file_location("phase5c_label_map_worker_test", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("worker module could not be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_worker_converts_ras_affine_to_patient_lps_without_resampling(self) -> None:
        worker = self.load_worker_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, _ = write_canonical_volume(root)
            source_npy = study_dir / "derived" / "volume.npy"
            source_json = study_dir / "derived" / "volume.json"
            mask_path = root / "mask.nii.gz"
            mask_path.write_bytes(b"synthetic-nifti")
            output = root / "labels.npy"
            labels = np.zeros((2, 3, 4), dtype=np.uint8)
            labels.flat[1] = 1
            labels.flat[2] = 3
            lps_affine = np.asarray(PATIENT_LPS_AFFINE, dtype=np.float64)
            ras_affine = np.diag([-1.0, -1.0, 1.0, 1.0]) @ lps_affine
            image = SimpleNamespace(shape=labels.shape, affine=ras_affine, dataobj=labels)
            previous = sys.modules.get("nibabel")
            sys.modules["nibabel"] = SimpleNamespace(load=lambda path: image)
            try:
                report = worker.canonicalize_label_map(
                    source_npy=source_npy,
                    source_json=source_json,
                    mask_nifti=mask_path,
                    output_npy=output,
                    maximum_label=3,
                )
            finally:
                if previous is None:
                    sys.modules.pop("nibabel", None)
                else:
                    sys.modules["nibabel"] = previous

            canonical = np.load(output, allow_pickle=False)
            self.assertEqual(str(canonical.dtype), "uint16")
            self.assertTrue(np.array_equal(canonical, labels))
            self.assertEqual(report["coordinate_system"], "patient_lps")
            self.assertTrue(
                np.allclose(report["array_index_to_patient_lps"], PATIENT_LPS_AFFINE)
            )
            self.assertTrue(np.allclose(report["source_to_model_index"], np.eye(4)))
            self.assertTrue(np.allclose(report["model_to_source_index"], np.eye(4)))
            self.assertFalse(report["resampled"])
            self.assertEqual(report["interpolation"], "none")
            self.assertEqual(report["present_labels"], [0, 1, 3])

    def test_worker_rejects_noncanonical_model_grid_instead_of_silent_resampling(self) -> None:
        worker = self.load_worker_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir, _ = write_canonical_volume(root)
            mask_path = root / "mask.nii.gz"
            mask_path.write_bytes(b"synthetic-nifti")
            output = root / "labels.npy"
            labels = np.zeros((2, 3, 4), dtype=np.uint8)
            lps_affine = np.asarray(PATIENT_LPS_AFFINE, dtype=np.float64)
            ras_affine = np.diag([-1.0, -1.0, 1.0, 1.0]) @ lps_affine
            ras_affine[0, 3] += 2.0
            image = SimpleNamespace(shape=labels.shape, affine=ras_affine, dataobj=labels)
            previous = sys.modules.get("nibabel")
            sys.modules["nibabel"] = SimpleNamespace(load=lambda path: image)
            try:
                with self.assertRaisesRegex(ValueError, "canonical Patient LPS grid"):
                    worker.canonicalize_label_map(
                        source_npy=study_dir / "derived" / "volume.npy",
                        source_json=study_dir / "derived" / "volume.json",
                        mask_nifti=mask_path,
                        output_npy=output,
                        maximum_label=3,
                    )
            finally:
                if previous is None:
                    sys.modules.pop("nibabel", None)
                else:
                    sys.modules["nibabel"] = previous
            self.assertFalse(output.exists())


class StubLabelMapService:
    descriptor = {
        "label_map_id": "map-" + "4" * 32,
        "state": "ready",
        "source_study_id": STUDY_ID,
        "coordinate_system": "patient_lps",
    }

    def list(self, *, study_id: str | None = None) -> list[dict[str, object]]:
        if study_id not in {None, STUDY_ID}:
            return []
        return [dict(self.descriptor)]

    def get(self, label_map_id: str) -> dict[str, object]:
        if label_map_id != self.descriptor["label_map_id"]:
            raise SegmentationValidationError("label-map identifier is invalid")
        return dict(self.descriptor)


class Phase5CLabelMapHttpTests(unittest.TestCase):
    def test_default_label_map_service_reuses_the_application_job_service(self) -> None:
        try:
            from voxelatlas import config
            from voxelatlas.app import create_app
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(f"HTTP dependencies unavailable: {exc}")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = SegmentationJobService(data_dir=root)
            settings = config.AppSettings(
                environment="test",
                session_secret="x" * 48,
                secure_cookies=False,
                session_cookie_name="voxelatlas_session",
                allowed_hosts=("testserver", "127.0.0.1", "localhost"),
                data_dir=root,
                max_upload_mib=512,
                auth_username=None,
                auth_password_hash=None,
                session_ttl_minutes=60,
            )
            app = create_app(settings=settings, segmentation_service=jobs)

        self.assertIs(app.state.segmentation_label_map_service._job_service, jobs)

    def test_descriptor_routes_are_authenticated_no_store_and_path_safe(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from voxelatlas import config
            from voxelatlas.app import create_app
            from voxelatlas.passwords import hash_password
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(f"HTTP dependencies unavailable: {exc}")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            with TestClient(
                create_app(
                    settings=settings,
                    segmentation_label_map_service=StubLabelMapService(),
                )
            ) as client:
                denied = client.get("/api/segmentation/label-maps")
                client.post(
                    "/api/auth/login",
                    json={
                        "username": "engineer",
                        "password": "correct horse battery staple",
                    },
                )
                listed = client.get(
                    "/api/segmentation/label-maps",
                    params={"study_id": STUDY_ID},
                )
                inspected = client.get(
                    "/api/segmentation/label-maps/map-" + "4" * 32
                )
                invalid = client.get("/api/segmentation/label-maps/not-valid")

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(inspected.status_code, 200)
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(len(listed.json()["label_maps"]), 1)
        self.assertEqual(inspected.json()["label_map"]["state"], "ready")
        for response in (listed, inspected, invalid):
            self.assertEqual(response.headers.get("cache-control"), "no-store")
            self.assertNotIn(str(root), response.text)


if __name__ == "__main__":
    unittest.main()
