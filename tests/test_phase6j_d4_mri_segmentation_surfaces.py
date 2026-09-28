"""Phase 6J-D4: qualified MRI label maps reuse segmentation-derived 3D surfaces.

Synthetic only: no patient data, MRI inference, production import, or model execution.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.mri_task_contract import MRI_TASK_SOURCE_MAPPING_SHA256  # noqa: E402
from voxelatlas.segmentation_surface_runtime import SegmentationSurfaceRuntimeReport  # noqa: E402
from voxelatlas.segmentation_surfaces import (  # noqa: E402
    ACCURATE_SURFACE_HEADER,
    ACCURATE_SURFACE_MEDIA_TYPE,
    ACCURATE_SURFACE_QUALITY,
    REFINED_MRI_TOTAL_MR_MAX_DISPLACEMENT_MM,
    REFINED_MRI_TOTAL_MR_PRESENTATION_RECONSTRUCTION,
    REFINED_MRI_TOTAL_MR_PRESENTATION_SIGMA_MM,
    REFINED_MRI_TOTAL_MR_PROFILE,
    REFINED_SURFACE_ALGORITHM_VERSION,
    REFINED_SURFACE_REFINEMENT,
    REFINED_TOTAL_DISPLACEMENT_FRACTION,
    SegmentationSurface,
    SegmentationSurfaceService,
    _refined_policy,
    _validate_refined_payload,
)


STUDY_ID = "a" * 32
LABEL_MAP_ID = "map-" + "d" * 32
JOB_ID = "seg-" + "1" * 32
STUDY_UID = "1.2.840.113619.2.1"
SERIES_UID = "1.2.840.113619.2.2"


class StudyRepository:
    def latest_manifest(self) -> dict[str, object]:
        return {"study_id": STUDY_ID}


class LabelMaps:
    def __init__(self, descriptor: dict[str, object]):
        self.descriptor = descriptor

    def get(self, label_map_id: str) -> dict[str, object]:
        if label_map_id != LABEL_MAP_ID:
            raise AssertionError("unexpected label map")
        return dict(self.descriptor)

    def list(self, *, study_id: str | None = None) -> list[dict[str, object]]:
        return [dict(self.descriptor)] if study_id == STUDY_ID else []


def make_mri_surface_service(root: Path) -> SegmentationSurfaceService:
    labels = np.zeros((5, 6, 7), dtype=np.uint16)
    labels[1:4, 1:5, 1:6] = 50  # brain
    labels[2:5, 2:4, 3:5] = 21  # spinal cord; deliberately overwrites a small region

    map_dir = root / "segmentation" / "label-maps" / LABEL_MAP_ID
    map_dir.mkdir(parents=True)
    path = map_dir / "labels.npy"
    np.save(path, labels, allow_pickle=False)
    artifact_sha = sha256(path.read_bytes()).hexdigest()

    descriptor: dict[str, object] = {
        "label_map_id": LABEL_MAP_ID,
        "state": "ready",
        "source_study_id": STUDY_ID,
        "source_study_instance_uid": STUDY_UID,
        "source_series_uid": SERIES_UID,
        "source_modality": "MR",
        "source_volume_descriptor_sha256": "2" * 64,
        "source_volume_artifact_sha256": "3" * 64,
        "segmentation_job_id": JOB_ID,
        "segmentation_terminal_provenance_sha256": "4" * 64,
        "provider_id": "totalsegmentator",
        "provider_version": "2.18.0",
        "model_id": "total_mr",
        "model_version": "2.18.0",
        "model_descriptor_sha256": "5" * 64,
        "task": "total_mr",
        "task_definition_sha256": MRI_TASK_SOURCE_MAPPING_SHA256,
        "class_count": 50,
        "coordinate_system": "patient_lps",
        "representation": "label_map",
        "artifact_format": "npy",
        "artifact_sha256": artifact_sha,
        "shape": list(labels.shape),
        "dtype": "uint16",
        "axis_order": ["slice", "row", "column"],
        "present_labels": [0, 21, 50],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 1.5, 10.0],
            [0.0, 1.25, 0.0, 20.0],
            [2.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "clinical_validation": "not_claimed",
    }
    return SegmentationSurfaceService(
        data_dir=root,
        study_repository=StudyRepository(),
        label_map_service=LabelMaps(descriptor),
    )


class MRI3DSurfaceReuseTests(unittest.TestCase):
    def test_total_mr_descriptor_reuses_provider_neutral_surface_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            descriptor = make_mri_surface_service(Path(tmp)).descriptor_latest(
                label_map_id=LABEL_MAP_ID
            )

        self.assertTrue(descriptor["ready"])
        self.assertEqual(descriptor["label_map_id"], LABEL_MAP_ID)
        self.assertEqual(descriptor["source_study_id"], STUDY_ID)
        self.assertEqual(descriptor["source_modality"], "MR")
        self.assertEqual(descriptor["provider_id"], "totalsegmentator")
        self.assertEqual(descriptor["model_id"], "total_mr")
        self.assertEqual(descriptor["present_labels"], [21, 50])
        self.assertEqual(descriptor["clinical_validation"], "not_claimed")


    def test_total_mr_refined_surface_uses_stronger_bounded_presentation_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = make_mri_surface_service(Path(tmp))
            descriptor = service.descriptor_latest(label_map_id=LABEL_MAP_ID)
            public_policy = descriptor["refined_surface"]
            internal_policy = _refined_policy(service.label_map_service.get(LABEL_MAP_ID))

        self.assertEqual(
            public_policy["refinement_profile"],
            REFINED_MRI_TOTAL_MR_PROFILE,
        )
        self.assertEqual(
            internal_policy["refinement_profile"],
            REFINED_MRI_TOTAL_MR_PROFILE,
        )
        self.assertGreater(internal_policy["smoothing_iterations"], 2)
        self.assertGreater(internal_policy["smoothing_displacement_fraction"], 0.25)
        self.assertEqual(
            internal_policy["total_displacement_fraction"],
            REFINED_TOTAL_DISPLACEMENT_FRACTION,
        )
        self.assertEqual(
            public_policy["maximum_displacement_fraction_of_minimum_voxel_step"],
            REFINED_TOTAL_DISPLACEMENT_FRACTION,
        )
        self.assertEqual(
            internal_policy["presentation_reconstruction"],
            REFINED_MRI_TOTAL_MR_PRESENTATION_RECONSTRUCTION,
        )
        self.assertEqual(
            internal_policy["presentation_sigma_mm"],
            REFINED_MRI_TOTAL_MR_PRESENTATION_SIGMA_MM,
        )
        self.assertEqual(
            internal_policy["maximum_displacement_mm"],
            REFINED_MRI_TOTAL_MR_MAX_DISPLACEMENT_MM,
        )
        self.assertEqual(
            public_policy["maximum_displacement_mm"],
            REFINED_MRI_TOTAL_MR_MAX_DISPLACEMENT_MM,
        )

    def test_ct_standard_refinement_policy_is_unchanged(self):
        policy = _refined_policy()
        self.assertNotIn("refinement_profile", policy)
        self.assertEqual(policy["smoothing_iterations"], 2)
        self.assertEqual(policy["taubin_lambda"], 0.33)
        self.assertEqual(policy["taubin_mu"], -0.34)
        self.assertEqual(policy["smoothing_displacement_fraction"], 0.25)
        self.assertEqual(
            policy["total_displacement_fraction"],
            REFINED_TOTAL_DISPLACEMENT_FRACTION,
        )

    def test_total_mr_presentation_smoothing_is_stronger_without_relaxing_bound(self):
        spec = importlib.util.spec_from_file_location(
            "phase6b_surface_worker_d4_quality",
            ROOT / "scripts" / "phase6b_surface_worker.py",
        )
        self.assertIsNotNone(spec)
        worker = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(worker)

        positions = np.asarray([
            [0.0, 0.0, 0.0], [3.0, 0.0, 0.0],
            [3.0, 3.0, 0.0], [0.0, 3.0, 0.0],
            [0.0, 0.0, 3.0], [3.0, 0.0, 3.0],
            [3.0, 3.0, 3.0], [0.0, 3.0, 3.0],
        ], dtype=np.float64)
        faces = np.asarray([
            [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
            [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
            [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
        ], dtype=np.int64)
        affine = np.eye(4, dtype=np.float64)
        shape = (8, 8, 8)
        standard = _refined_policy()
        mri_descriptor = {
            "source_modality": "MR",
            "provider_id": "totalsegmentator",
            "model_id": "total_mr",
            "task": "total_mr",
            "clinical_validation": "not_claimed",
        }
        mri = _refined_policy(mri_descriptor)

        standard_limit = standard["smoothing_displacement_fraction"]
        mri_limit = mri["smoothing_displacement_fraction"]
        standard_positions = worker.smooth_bounded(
            positions, faces,
            iterations=standard["smoothing_iterations"],
            factor_lambda=standard["taubin_lambda"],
            factor_mu=standard["taubin_mu"],
            limit_mm=standard_limit, affine=affine, shape=shape,
        )
        mri_positions = worker.smooth_bounded(
            positions, faces,
            iterations=mri["smoothing_iterations"],
            factor_lambda=mri["taubin_lambda"],
            factor_mu=mri["taubin_mu"],
            limit_mm=mri_limit, affine=affine, shape=shape,
        )

        standard_mean = float(np.linalg.norm(standard_positions - positions, axis=1).mean())
        mri_displacement = np.linalg.norm(mri_positions - positions, axis=1)
        self.assertGreater(float(mri_displacement.mean()), standard_mean)
        self.assertLessEqual(
            float(mri_displacement.max()),
            REFINED_TOTAL_DISPLACEMENT_FRACTION + 1e-9,
        )

    def test_total_mr_worker_report_and_backend_validation_share_exact_profile(self):
        if importlib.util.find_spec("skimage") is None:
            self.skipTest(
                "scikit-image is isolated to the qualified surface runtime; "
                "the real reconstruction path is covered by the D4 runtime probe"
            )

        def load_worker(name: str, filename: str):
            spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
            self.assertIsNotNone(spec)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            return module

        worker6a = load_worker("phase6a_surface_worker_d4_test", "phase6a_surface_worker.py")
        worker6b = load_worker("phase6b_surface_worker_d4_test", "phase6b_surface_worker.py")
        runtime_identity = worker6b.runtime_identity()
        self.assertEqual(worker6a.runtime_identity(), runtime_identity)
        runtime = SegmentationSurfaceRuntimeReport(
            True, "qualified", "qualified",
            runtime_identity["python_version"],
            runtime_identity["numpy_version"],
            runtime_identity["scikit_image_version"],
            runtime_identity["runtime_fingerprint_sha256"],
        )

        shape = (32, 32, 32)
        z, y, x = np.indices(shape, dtype=np.float64)
        center = np.asarray(shape, dtype=np.float64) / 2.0
        mask = (
            ((z - center[0]) / 9.5) ** 2
            + ((y - center[1]) / 11.0) ** 2
            + ((x - center[2]) / 10.0) ** 2
            <= 1.0
        )
        labels = np.zeros(shape, dtype=np.uint16)
        labels[mask] = 50
        indices = np.argwhere(mask)
        minimum = indices.min(axis=0)
        maximum = indices.max(axis=0)
        affine = np.asarray(
            [
                [1.50, 0.00, 0.00, 10.0],
                [0.00, 0.82, 0.00, 20.0],
                [0.00, 0.00, 0.82, 30.0],
                [0.00, 0.00, 0.00, 1.0],
            ],
            dtype=np.float64,
        )
        descriptor = {
            "source_modality": "MR", "provider_id": "totalsegmentator",
            "model_id": "total_mr", "task": "total_mr",
            "clinical_validation": "not_claimed",
            "array_index_to_patient_lps": affine.tolist(),
            "shape": list(shape),
        }

        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            label_map_path = stage / "labels.npy"
            accurate_path = stage / "accurate.vxsf2"
            refined_path = stage / "refined.vxsf2"
            np.save(label_map_path, labels, allow_pickle=False)
            label_sha = sha256(label_map_path.read_bytes()).hexdigest()

            accurate_request = {
                "schema_version": 2, "operation": "extract_accurate_surface",
                "label_id": 50, "expected_label_map_sha256": label_sha,
                "shape": list(shape),
                "minimum_index": [int(value) for value in minimum],
                "maximum_index": [int(value) for value in maximum],
                "voxel_count": int(mask.sum()),
                "array_index_to_patient_lps": affine.tolist(),
                "extraction": "marching_cubes_half_voxel",
                "expected_runtime_fingerprint_sha256": runtime_identity["runtime_fingerprint_sha256"],
                "max_vertices": 1_500_000, "max_triangles": 2_500_000,
                "max_payload_bytes": 96 * 1024 * 1024,
                "source_label_map": "immutable", "clinical_validation": "not_claimed",
            }
            accurate_report = worker6a.extract_surface(
                label_map=label_map_path,
                request=accurate_request,
                output=accurate_path,
            )
            accurate_payload = accurate_path.read_bytes()
            reference_id = "surf-" + "8" * 32
            reference = SegmentationSurface(
                label_map_id=LABEL_MAP_ID, label_id=50,
                quality=ACCURATE_SURFACE_QUALITY,
                extraction="marching_cubes_half_voxel", coordinate_system="patient_lps",
                stride=1,
                vertex_count=int(accurate_report["vertex_count"]),
                triangle_count=int(accurate_report["triangle_count"]),
                bounds_lps_mm=tuple(float(value) for value in accurate_report["bounds_lps_mm"]),
                payload_sha256=sha256(accurate_payload).hexdigest(),
                payload=accurate_payload, schema_version=2,
                media_type=ACCURATE_SURFACE_MEDIA_TYPE, surface_id=reference_id,
                provenance_sha256="a" * 64,
                normal_count=int(accurate_report["vertex_count"]),
            )
            request = {
                "schema_version": 2, "operation": "refine_accurate_surface",
                "refinement": REFINED_SURFACE_REFINEMENT,
                "refinement_algorithm_version": REFINED_SURFACE_ALGORITHM_VERSION,
                "label_id": 50, "reference_surface_id": reference_id,
                "reference_surface_sha256": reference.payload_sha256,
                "array_index_to_patient_lps": affine.tolist(),
                "shape": list(shape),
                "expected_runtime_fingerprint_sha256": runtime_identity["runtime_fingerprint_sha256"],
                "max_vertices": 1_500_000, "max_triangles": 2_500_000,
                "max_payload_bytes": 96 * 1024 * 1024,
                "policy": _refined_policy(descriptor),
                "label_map_npy": str(label_map_path.resolve(strict=True)),
                "expected_label_map_sha256": label_sha,
                "source_label_map": "immutable", "clinical_validation": "not_claimed",
            }
            report = worker6b.refine_surface(
                reference_surface=accurate_path, request=request, output=refined_path
            )
            _, _, _, validated = _validate_refined_payload(
                refined_path.read_bytes(), label_id=50, report=report, runtime=runtime,
                reference_surface=reference, descriptor=descriptor,
            )

        self.assertEqual(report["refinement_profile"], REFINED_MRI_TOTAL_MR_PROFILE)
        self.assertTrue(report["presentation_reconstruction_applied"])
        self.assertEqual(
            report["presentation_reconstruction"],
            REFINED_MRI_TOTAL_MR_PRESENTATION_RECONSTRUCTION,
        )
        self.assertLessEqual(
            validated["max_displacement_mm"], validated["displacement_limit_mm"] + 1e-9
        )

    def test_mri_brain_and_spinal_cord_reuse_patient_lps_surface_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = make_mri_surface_service(Path(tmp))
            spinal = service.surface_latest(
                label_id=21,
                label_map_id=LABEL_MAP_ID,
                quality="preview",
            )
            brain = service.surface_latest(
                label_id=50,
                label_map_id=LABEL_MAP_ID,
                quality="preview",
            )

        for surface, label_id in ((spinal, 21), (brain, 50)):
            with self.subTest(label_id=label_id):
                self.assertEqual(surface.label_map_id, LABEL_MAP_ID)
                self.assertEqual(surface.label_id, label_id)
                self.assertEqual(surface.coordinate_system, "patient_lps")
                self.assertGreater(surface.vertex_count, 0)
                self.assertGreater(surface.triangle_count, 0)
                self.assertEqual(len(surface.bounds_lps_mm), 6)
                self.assertEqual(surface.quality, "preview")


if __name__ == "__main__":
    unittest.main()
