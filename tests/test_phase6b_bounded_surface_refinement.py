from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import sys
import importlib.util
import math
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.test_phase6a_accurate_patient_space_surfaces import (  # noqa: E402
    LABEL_MAP_ID,
    decode_accurate,
    make_service,
)
from voxelatlas.segmentation_surfaces import (  # noqa: E402
    ACCURATE_SURFACE_QUALITY,
    REFINED_SURFACE_QUALITY,
    REFINED_SURFACE_REFINEMENT,
)


class Phase6BBoundedSurfaceRefinementTests(unittest.TestCase):
    def test_descriptor_preserves_accurate_reference_and_prefers_refined_presentation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp))
            descriptor = service.descriptor_latest(label_map_id=LABEL_MAP_ID)

        self.assertEqual(descriptor["default_quality"], ACCURATE_SURFACE_QUALITY)
        self.assertEqual(descriptor["presentation_quality"], REFINED_SURFACE_QUALITY)
        self.assertEqual(descriptor["refined_surface"]["reference_quality"], ACCURATE_SURFACE_QUALITY)
        self.assertEqual(descriptor["refined_surface"]["refinement"], REFINED_SURFACE_REFINEMENT)
        self.assertEqual(descriptor["refined_surface"]["refinement_algorithm_version"], 2)
        self.assertTrue(descriptor["refined_surface"]["bounded_local_face_topology_repair"])
        self.assertTrue(descriptor["refined_surface"]["vertex_fan_manifold_required"])
        self.assertTrue(descriptor["accurate_surface"]["native_mask_resolution"])
        self.assertTrue(descriptor["preview_surface"]["available"])

    def test_refined_surface_is_deterministic_bounded_and_keeps_accurate_reference_unchanged(self) -> None:
        labels = np.zeros((12, 12, 12), dtype=np.uint16)
        zz, yy, xx = np.indices(labels.shape)
        sphere = (zz - 5.5) ** 2 + (yy - 5.5) ** 2 + (xx - 5.5) ** 2 <= 4.6 ** 2
        labels[sphere] = 7
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp), labels=labels)
            accurate_before = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality=ACCURATE_SURFACE_QUALITY
            )
            refined_first = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality=REFINED_SURFACE_QUALITY
            )
            refined_second = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality=REFINED_SURFACE_QUALITY
            )
            accurate_after = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality=ACCURATE_SURFACE_QUALITY
            )

        self.assertEqual(accurate_before.payload_sha256, accurate_after.payload_sha256)
        self.assertEqual(refined_first.payload_sha256, refined_second.payload_sha256)
        self.assertEqual(refined_first.surface_id, refined_second.surface_id)
        self.assertEqual(refined_first.reference_surface_id, accurate_before.surface_id)
        self.assertEqual(refined_first.reference_payload_sha256, accurate_before.payload_sha256)
        self.assertEqual(refined_first.refinement, REFINED_SURFACE_REFINEMENT)
        self.assertGreaterEqual(refined_first.triangle_count, 1)
        self.assertLess(refined_first.triangle_count, accurate_before.triangle_count)
        self.assertTrue(refined_first.decimation_applied)
        self.assertGreaterEqual(refined_first.triangle_retention_ratio, 0.70)
        self.assertLessEqual(refined_first.max_displacement_mm, refined_first.displacement_limit_mm + 1e-6)
        decoded = decode_accurate(refined_first)
        self.assertEqual(decoded["vertex_count"], refined_first.vertex_count)
        self.assertTrue(np.all(np.isfinite(decoded["normals"])))

    def test_refined_worker_repairs_only_safe_topology_and_preserves_topology_invariants(self) -> None:
        labels = np.zeros((10, 10, 10), dtype=np.uint16)
        labels[2:8, 2:8, 2:8] = 7
        labels[4:6, 4:6, 8] = 7
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp), labels=labels)
            refined = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality=REFINED_SURFACE_QUALITY
            )

        self.assertEqual(refined.boundary_edge_count, 0)
        self.assertEqual(refined.nonmanifold_edge_count, 0)
        self.assertEqual(refined.nonmanifold_vertex_count, 0)
        self.assertGreaterEqual(refined.connected_component_count, 1)
        self.assertNotEqual(refined.euler_characteristic, 0x7FFFFFFF)
        self.assertGreaterEqual(refined.topology_repair_count, 0)



    def test_safe_topology_cleanup_removes_only_duplicate_degenerate_and_unreferenced_data(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "phase6b_surface_worker", ROOT / "scripts" / "phase6b_surface_worker.py"
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        positions = np.asarray([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [9.0, 9.0, 9.0],
        ], dtype=np.float64)
        normals = np.asarray([
            [-1.0, -1.0, -1.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 0.0],
        ], dtype=np.float64)
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        faces = np.asarray([
            [0, 2, 1],
            [0, 1, 3],
            [0, 3, 2],
            [1, 2, 3],
            [0, 2, 1],
            [0, 0, 1],
        ], dtype=np.int64)
        cleaned_positions, _, cleaned_faces, repairs, _, removed_unreferenced = (
            module.compact_mesh(positions, normals, faces)
        )
        metrics = module.topology_metrics(len(cleaned_positions), cleaned_faces)
        self.assertEqual(len(cleaned_positions), 4)
        self.assertEqual(len(cleaned_faces), 4)
        self.assertEqual(repairs, 3)
        self.assertEqual(removed_unreferenced, 1)
        self.assertEqual(metrics["boundary_edge_count"], 0)
        self.assertEqual(metrics["nonmanifold_edge_count"], 0)
        self.assertEqual(metrics["connected_component_count"], 1)
        self.assertEqual(metrics["euler_characteristic"], 2)
        self.assertEqual(metrics["component_euler_signature"], [2])

    def test_component_euler_signature_is_preserved_per_connected_component(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "phase6b_surface_worker", ROOT / "scripts" / "phase6b_surface_worker.py"
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        faces = np.asarray([
            [0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3],
            [4, 6, 5], [4, 5, 7], [4, 7, 6], [5, 6, 7],
        ], dtype=np.int64)
        metrics = module.topology_metrics(8, faces)
        self.assertEqual(metrics["connected_component_count"], 2)
        self.assertEqual(metrics["euler_characteristic"], 4)
        self.assertEqual(metrics["component_euler_signature"], [2, 2])

    def test_vertex_fan_manifold_check_rejects_bow_tie_vertex(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "phase6b_surface_worker", ROOT / "scripts" / "phase6b_surface_worker.py"
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        faces = np.asarray([
            [0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3],
            [0, 5, 4], [0, 4, 6], [0, 6, 5], [4, 5, 6],
        ], dtype=np.int64)
        metrics = module.topology_metrics(7, faces)
        self.assertEqual(metrics["boundary_edge_count"], 0)
        self.assertEqual(metrics["nonmanifold_edge_count"], 0)
        self.assertEqual(metrics["nonmanifold_vertex_count"], 1)
        self.assertEqual(metrics["connected_component_count"], 1)

    def test_bounded_local_face_repair_closes_real_study_anomaly_pattern_without_motion(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "phase6b_surface_worker", ROOT / "scripts" / "phase6b_surface_worker.py"
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        major_count = 110
        minor_count = 110
        major_radius = 4.0
        minor_radius = 1.0
        positions = []
        normals = []
        for major_index in range(major_count):
            theta = 2.0 * math.pi * major_index / major_count
            for minor_index in range(minor_count):
                phi = 2.0 * math.pi * minor_index / minor_count
                positions.append([
                    (major_radius + minor_radius * math.cos(phi)) * math.cos(theta),
                    (major_radius + minor_radius * math.cos(phi)) * math.sin(theta),
                    minor_radius * math.sin(phi),
                ])
                normals.append([
                    math.cos(phi) * math.cos(theta),
                    math.cos(phi) * math.sin(theta),
                    math.sin(phi),
                ])
        positions_array = np.asarray(positions, dtype=np.float64)
        normals_array = np.asarray(normals, dtype=np.float64)

        def vertex(i: int, j: int) -> int:
            return (i % major_count) * minor_count + (j % minor_count)

        faces = []
        for major_index in range(major_count):
            for minor_index in range(minor_count):
                first = vertex(major_index, minor_index)
                second = vertex(major_index + 1, minor_index)
                third = vertex(major_index + 1, minor_index + 1)
                fourth = vertex(major_index, minor_index + 1)
                faces.extend(([first, second, third], [first, third, fourth]))
        valid_faces = np.asarray(faces, dtype=np.int64)
        defective_faces = np.vstack(
            (valid_faces, np.asarray([[0, 2, 3], [0, 3, 1]], dtype=np.int64))
        )
        defective_metrics = module.topology_metrics(
            len(positions_array), defective_faces
        )
        self.assertEqual(defective_metrics["boundary_edge_count"], 2)
        self.assertEqual(defective_metrics["nonmanifold_edge_count"], 2)
        self.assertEqual(defective_metrics["connected_component_count"], 1)

        (
            repaired_positions,
            _,
            repaired_faces,
            repaired_metrics,
            repair_report,
        ) = module.repair_local_topology(
            positions_array,
            normals_array,
            defective_faces,
            defective_metrics,
        )
        self.assertTrue(repair_report["applied"])
        self.assertEqual(repair_report["anomaly_edge_count"], 4)
        self.assertEqual(repair_report["candidate_face_count"], 6)
        self.assertEqual(repair_report["removed_face_count"], 2)
        self.assertLessEqual(
            repair_report["removed_face_fraction"],
            module.LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION,
        )
        self.assertLessEqual(
            repair_report["removed_area_fraction"],
            module.LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION,
        )
        self.assertEqual(repair_report["initial_displacement_mm"], 0.0)
        self.assertEqual(repaired_metrics["boundary_edge_count"], 0)
        self.assertEqual(repaired_metrics["nonmanifold_edge_count"], 0)
        self.assertEqual(repaired_metrics["nonmanifold_vertex_count"], 0)
        self.assertEqual(repaired_metrics["connected_component_count"], 1)
        self.assertEqual(len(repaired_faces), len(valid_faces))
        self.assertTrue(np.array_equal(repaired_positions, positions_array))

    def test_worker_and_backend_accept_repaired_topology_as_refinement_baseline(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "phase6b_surface_worker", ROOT / "scripts" / "phase6b_surface_worker.py"
        )
        self.assertIsNotNone(spec)
        worker = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(worker)
        from voxelatlas.segmentation_surface_runtime import SegmentationSurfaceRuntimeReport
        from voxelatlas.segmentation_surfaces import (
            ACCURATE_SURFACE_HEADER,
            ACCURATE_SURFACE_MEDIA_TYPE,
            REFINED_SURFACE_ALGORITHM_VERSION,
            SegmentationSurface,
            _refined_policy,
            _validate_refined_payload,
        )

        major_count = 110
        minor_count = 110
        major_radius = 4.0
        minor_radius = 1.0
        positions = []
        normals = []
        for major_index in range(major_count):
            theta = 2.0 * math.pi * major_index / major_count
            for minor_index in range(minor_count):
                phi = 2.0 * math.pi * minor_index / minor_count
                positions.append([
                    (major_radius + minor_radius * math.cos(phi)) * math.cos(theta) + 10.0,
                    (major_radius + minor_radius * math.cos(phi)) * math.sin(theta) + 10.0,
                    minor_radius * math.sin(phi) + 10.0,
                ])
                normals.append([
                    math.cos(phi) * math.cos(theta),
                    math.cos(phi) * math.sin(theta),
                    math.sin(phi),
                ])

        def vertex(i: int, j: int) -> int:
            return (i % major_count) * minor_count + (j % minor_count)

        faces = []
        for major_index in range(major_count):
            for minor_index in range(minor_count):
                first = vertex(major_index, minor_index)
                second = vertex(major_index + 1, minor_index)
                third = vertex(major_index + 1, minor_index + 1)
                fourth = vertex(major_index, minor_index + 1)
                faces.extend(([first, second, third], [first, third, fourth]))
        defective_faces = np.vstack(
            (
                np.asarray(faces, dtype=np.uint32),
                np.asarray([[0, 2, 3], [0, 3, 1]], dtype=np.uint32),
            )
        )
        positions32 = np.asarray(positions, dtype="<f4")
        normals32 = np.asarray(normals, dtype="<f4")
        indices32 = defective_faces.reshape(-1).astype("<u4")
        payload = ACCURATE_SURFACE_HEADER.pack(
            b"VXSF",
            2,
            7,
            len(positions32),
            len(indices32),
            positions32.nbytes,
            normals32.nbytes,
            indices32.nbytes,
            1,
        ) + positions32.tobytes() + normals32.tobytes() + indices32.tobytes()
        payload_sha = sha256(payload).hexdigest()
        reference_id = "surf-" + "a" * 32
        # This contract test executes under the lightweight backend venv.
        # The production worker obtains this identity inside the separately
        # qualified Phase 6A surface runtime, where scikit-image is installed.
        # Stub only the runtime identity here so the integration contract does
        # not violate the heavy-runtime isolation boundary it is meant to test.
        runtime_identity = {
            "python_version": "3.12.3",
            "numpy_version": "2.5.3",
            "scikit_image_version": "0.26.0",
            "runtime_fingerprint_sha256": (
                "0425a289f9c6c757bcff573985df9413682d7fcebcdc36d4ca85f276b90707b4"
            ),
        }
        worker.runtime_identity = lambda: dict(runtime_identity)
        runtime = SegmentationSurfaceRuntimeReport(
            True,
            "qualified",
            "Segmentation surface runtime contract is qualified",
            runtime_identity["python_version"],
            runtime_identity["numpy_version"],
            runtime_identity["scikit_image_version"],
            runtime_identity["runtime_fingerprint_sha256"],
        )
        reference_surface = SegmentationSurface(
            label_map_id=LABEL_MAP_ID,
            label_id=7,
            quality=ACCURATE_SURFACE_QUALITY,
            extraction="marching_cubes_half_voxel",
            coordinate_system="patient_lps",
            stride=1,
            vertex_count=len(positions32),
            triangle_count=len(defective_faces),
            bounds_lps_mm=tuple(
                float(value)
                for value in np.concatenate((positions32.min(axis=0), positions32.max(axis=0)))
            ),
            payload_sha256=payload_sha,
            payload=payload,
            schema_version=2,
            media_type=ACCURATE_SURFACE_MEDIA_TYPE,
            surface_id=reference_id,
            provenance_sha256="b" * 64,
            normal_count=len(positions32),
        )
        affine = np.eye(4, dtype=np.float64).tolist()
        request = {
            "schema_version": 2,
            "operation": "refine_accurate_surface",
            "refinement": REFINED_SURFACE_REFINEMENT,
            "refinement_algorithm_version": REFINED_SURFACE_ALGORITHM_VERSION,
            "label_id": 7,
            "reference_surface_id": reference_id,
            "reference_surface_sha256": payload_sha,
            "array_index_to_patient_lps": affine,
            "shape": [32, 32, 32],
            "expected_runtime_fingerprint_sha256": runtime_identity[
                "runtime_fingerprint_sha256"
            ],
            "max_vertices": 1_500_000,
            "max_triangles": 2_500_000,
            "max_payload_bytes": 96 * 1024 * 1024,
            "policy": _refined_policy(),
            "source_label_map": "immutable",
            "clinical_validation": "not_claimed",
        }
        with tempfile.TemporaryDirectory() as tmp:
            reference_path = Path(tmp) / "reference.vxsf2"
            output_path = Path(tmp) / "refined.vxsf2"
            reference_path.write_bytes(payload)
            report = worker.refine_surface(
                reference_surface=reference_path,
                request=request,
                output=output_path,
            )
            _, _, _, validated = _validate_refined_payload(
                output_path.read_bytes(),
                label_id=7,
                report=report,
                runtime=runtime,
                reference_surface=reference_surface,
                descriptor={
                    "array_index_to_patient_lps": affine,
                    "shape": [32, 32, 32],
                },
            )

        self.assertTrue(report["topology_local_repair_applied"])
        self.assertEqual(report["post_compact_reference_boundary_edge_count"], 2)
        self.assertEqual(report["post_compact_reference_nonmanifold_edge_count"], 2)
        self.assertEqual(report["topology_repair_removed_face_count"], 2)
        self.assertEqual(report["topology_repair_initial_displacement_mm"], 0.0)
        self.assertEqual(report["repaired_reference_boundary_edge_count"], 0)
        self.assertEqual(report["repaired_reference_nonmanifold_edge_count"], 0)
        self.assertEqual(report["repaired_reference_nonmanifold_vertex_count"], 0)
        self.assertEqual(validated["reference_boundary_edge_count"], 2)
        self.assertEqual(validated["reference_nonmanifold_edge_count"], 2)
        self.assertEqual(validated["boundary_edge_count"], 0)
        self.assertEqual(validated["nonmanifold_edge_count"], 0)
        self.assertEqual(validated["nonmanifold_vertex_count"], 0)

    def test_boundary_touching_refinement_stays_inside_canonical_voxel_cell_bounds(self) -> None:
        labels = np.zeros((5, 6, 7), dtype=np.uint16)
        labels[0:3, 0:4, 0:5] = 7
        affine = [
            [0.0, -1.25, 0.15, 12.0],
            [0.9, 0.0, 0.0, -8.0],
            [0.1, 0.0, 2.2, 35.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = make_service(Path(tmp), labels=labels, affine=affine)
            refined = service.surface_latest(
                label_id=7, label_map_id=LABEL_MAP_ID, quality=REFINED_SURFACE_QUALITY
            )
        decoded = decode_accurate(refined)
        matrix = np.asarray(affine, dtype=np.float64)
        recovered = (
            decoded["positions"].astype(np.float64) - matrix[:3, 3]
        ) @ np.linalg.inv(matrix[:3, :3]).T
        self.assertTrue(np.all(recovered >= -0.5 - 2e-5))
        self.assertTrue(
            np.all(recovered <= np.asarray(labels.shape, dtype=np.float64) - 0.5 + 2e-5)
        )

    def test_phase6b_worker_does_not_absorb_phase6c_or_6g_policy(self) -> None:
        worker = (ROOT / "scripts" / "phase6b_surface_worker.py").read_text(encoding="utf-8")
        lowered = worker.lower()
        self.assertNotIn("export", lowered)
        self.assertNotIn("surface_to_mask", lowered)
        self.assertNotIn("hausdorff", lowered)
        self.assertNotIn("presentation profile", lowered)
        self.assertNotIn("exploded", lowered)


class Phase6BFrontendContractTests(unittest.TestCase):

    def test_authenticated_api_transports_refinement_reference_and_bounds(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from voxelatlas.app import create_app
            from voxelatlas.passwords import hash_password
            from voxelatlas import config
            from voxelatlas.segmentation_surfaces import (
                ACCURATE_SURFACE_HEADER,
                ACCURATE_SURFACE_MEDIA_TYPE,
                SegmentationSurface,
            )
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(f"HTTP dependencies unavailable: {exc}")

        positions = np.asarray(
            [[1.0, 2.0, 3.0], [2.0, 2.0, 3.0], [1.0, 3.0, 3.0]],
            dtype="<f4",
        )
        normals = np.asarray([[0.0, 0.0, 1.0]] * 3, dtype="<f4")
        indices = np.asarray([0, 1, 2], dtype="<u4")
        payload = ACCURATE_SURFACE_HEADER.pack(
            b"VXSF",
            2,
            7,
            3,
            3,
            positions.nbytes,
            normals.nbytes,
            indices.nbytes,
            1,
        ) + positions.tobytes() + normals.tobytes() + indices.tobytes()

        class StubSurfaceService:
            def descriptor_latest(self, *, label_map_id=None):
                return {
                    "ready": True,
                    "label_map_id": label_map_id or LABEL_MAP_ID,
                    "source_study_id": "0123456789abcdef0123456789abcdef",
                    "coordinate_system": "patient_lps",
                }

            def surface_latest(self, *, label_id, label_map_id, quality):
                self.requested_quality = quality
                return SegmentationSurface(
                    label_map_id=label_map_id,
                    label_id=label_id,
                    quality=quality,
                    extraction="marching_cubes_half_voxel",
                    coordinate_system="patient_lps",
                    stride=1,
                    vertex_count=3,
                    triangle_count=1,
                    bounds_lps_mm=(1.0, 2.0, 3.0, 2.0, 3.0, 3.0),
                    payload_sha256=__import__("hashlib").sha256(payload).hexdigest(),
                    payload=payload,
                    schema_version=2,
                    media_type=ACCURATE_SURFACE_MEDIA_TYPE,
                    surface_id="surf-" + "8" * 32,
                    provenance_sha256="9" * 64,
                    normal_count=3,
                    refinement=REFINED_SURFACE_REFINEMENT,
                    reference_surface_id="surf-" + "7" * 32,
                    reference_payload_sha256="6" * 64,
                    topology_repair_count=0,
                    boundary_edge_count=0,
                    nonmanifold_edge_count=0,
                    connected_component_count=1,
                    euler_characteristic=1,
                    max_displacement_mm=0.12,
                    displacement_limit_mm=0.40,
                    triangle_retention_ratio=0.80,
                    decimation_applied=True,
                    decimation_cell_size_index=0.8,
                )

        service = StubSurfaceService()
        with tempfile.TemporaryDirectory() as tmp:
            settings = config.AppSettings(
                environment="test",
                session_secret="x" * 48,
                secure_cookies=False,
                session_cookie_name="voxelatlas_session",
                allowed_hosts=("testserver", "127.0.0.1", "localhost"),
                data_dir=Path(tmp),
                max_upload_mib=512,
                auth_username="engineer",
                auth_password_hash=hash_password("correct horse battery staple"),
                session_ttl_minutes=60,
            )
            with TestClient(
                create_app(settings=settings, segmentation_surface_service=service)
            ) as client:
                client.post(
                    "/api/auth/login",
                    json={
                        "username": "engineer",
                        "password": "correct horse battery staple",
                    },
                )
                response = client.get(
                    "/api/studies/latest/segmentation-surfaces/7",
                    params={"label_map_id": LABEL_MAP_ID, "quality": "refined"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.requested_quality, "refined")
        self.assertEqual(response.headers["x-voxelatlas-surface-refinement"], REFINED_SURFACE_REFINEMENT)
        self.assertEqual(response.headers["x-voxelatlas-surface-reference-id"], "surf-" + "7" * 32)
        self.assertEqual(response.headers["x-voxelatlas-surface-reference-sha256"], "6" * 64)
        self.assertEqual(response.headers["x-voxelatlas-surface-max-displacement-mm"], "0.120000")
        self.assertEqual(response.headers["x-voxelatlas-surface-displacement-limit-mm"], "0.400000")
        self.assertEqual(response.headers["x-voxelatlas-surface-triangle-retention"], "0.800000000")
        self.assertEqual(response.headers["x-voxelatlas-surface-decimation-applied"], "true")
        self.assertEqual(response.headers["x-voxelatlas-surface-decimation-cell-index"], "0.800000")

    def test_browser_prefers_refined_v2_surface_without_removing_accurate(self) -> None:
        module = (ROOT / "web" / "js" / "segmentation-surface-viewer.js").read_text(
            encoding="utf-8"
        )
        app = (ROOT / "backend" / "voxelatlas" / "app.py").read_text(encoding="utf-8")
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("this.descriptor.presentation_quality", module)
        self.assertIn("this.descriptor.default_quality", module)
        self.assertIn("refined", module)
        self.assertIn("X-VoxelAtlas-Surface-Reference-Id", app)
        self.assertIn("X-VoxelAtlas-Surface-Max-Displacement-Mm", app)
        self.assertIn("Patient LPS refined surface", index)


if __name__ == "__main__":
    unittest.main()
