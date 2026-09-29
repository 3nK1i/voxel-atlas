from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / "scripts" / "phase6d1_volume_surface_worker.py"


def load_worker_module():
    spec = importlib.util.spec_from_file_location("phase6d1_volume_surface_worker", WORKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("worker module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Phase6D1DegenerateFaceCleanupCorrectionTests(unittest.TestCase):
    def test_bounded_cleanup_removes_only_tiny_degenerate_fraction_and_compacts_vertices(self):
        worker = load_worker_module()
        positions = np.asarray(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [99, 99, 99], [7, 7, 7]],
            dtype=np.float64,
        )
        orientation = np.asarray([[0, 0, 1]] * 5, dtype=np.float64)
        valid = np.tile(np.asarray([[0, 1, 2]], dtype=np.int64), (19_999, 1))
        degenerate = np.asarray([[0, 0, 1]], dtype=np.int64)
        faces = np.concatenate((valid, degenerate), axis=0)

        clean_positions, clean_faces, clean_orientation, cleanup = (
            worker.bounded_degenerate_face_cleanup(positions, faces, orientation)
        )

        self.assertEqual(cleanup["raw_vertex_count"], 5)
        self.assertEqual(cleanup["raw_triangle_count"], 20_000)
        self.assertEqual(cleanup["degenerate_triangle_count"], 1)
        self.assertAlmostEqual(cleanup["degenerate_triangle_fraction"], 1 / 20_000)
        self.assertEqual(cleanup["unreferenced_vertex_count"], 2)
        self.assertEqual(cleanup["final_vertex_count"], 3)
        self.assertEqual(cleanup["final_triangle_count"], 19_999)
        self.assertEqual(clean_positions.shape, (3, 3))
        self.assertEqual(clean_orientation.shape, (3, 3))
        self.assertTrue(np.all(clean_faces >= 0))
        self.assertTrue(np.all(clean_faces < 3))

    def test_cleanup_fails_when_degenerate_fraction_exceeds_safety_bound(self):
        worker = load_worker_module()
        positions = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64)
        orientation = np.asarray([[0, 0, 1]] * 3, dtype=np.float64)
        valid = np.tile(np.asarray([[0, 1, 2]], dtype=np.int64), (99, 1))
        degenerate = np.asarray([[0, 0, 1]], dtype=np.int64)
        faces = np.concatenate((valid, degenerate), axis=0)

        with self.assertRaisesRegex(ValueError, "degenerate-face cleanup exceeds safety bound"):
            worker.bounded_degenerate_face_cleanup(positions, faces, orientation)

    def test_worker_failure_reason_is_bounded_and_sanitized(self):
        from voxelatlas.volume_surfaces import _worker_failure_reason

        reason = _worker_failure_reason(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": "ValueError",
                    "error_code": "degenerate_face_budget_exceeded",
                }
            )
        )
        self.assertEqual(reason, "degenerate_face_budget_exceeded")
        self.assertEqual(_worker_failure_reason("not-json"), "worker_execution_failed")
        self.assertEqual(
            _worker_failure_reason(json.dumps({"status": "failed", "error_code": "../secret path"})),
            "worker_execution_failed",
        )

    def test_service_surfaces_only_allowlisted_worker_failure_code(self):
        from types import SimpleNamespace
        from voxelatlas.segmentation_surface_runtime import SegmentationSurfaceRuntimeReport
        from voxelatlas.volume_surfaces import VolumeSurfaceService, VolumeSurfaceUnavailableError

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study_dir = root / "studies" / ("a" * 32)
            derived = study_dir / "derived"
            derived.mkdir(parents=True)
            volume_path = derived / "volume.npy"
            volume = np.zeros((4, 5, 6), dtype=np.float32)
            volume[1:3, 1:4, 2:5] = 800.0
            np.save(volume_path, volume, allow_pickle=False)
            source = SimpleNamespace(
                study_dir=study_dir,
                volume_path=volume_path,
                source_series_uid="1.2.3",
                modality="CT",
                dtype="float32",
                shape=tuple(volume.shape),
                spacing_mm=(1.0, 1.0, 1.0),
                array_index_to_patient_lps=(
                    (1.0, 0.0, 0.0, 0.0),
                    (0.0, 1.0, 0.0, 0.0),
                    (0.0, 0.0, 1.0, 0.0),
                    (0.0, 0.0, 0.0, 1.0),
                ),
                intensity_units="HU",
                value_range=(0.0, 800.0),
                volume_created_at_utc="2026-09-10T10:00:00+00:00",
                source_descriptor_sha256="1" * 64,
                volume=volume,
            )

            class VolumeService:
                def source_latest(self):
                    return source

            class Qualifier:
                def qualify(self, python_executable):
                    return SegmentationSurfaceRuntimeReport(
                        True, "qualified", "qualified",
                        python_version="3.11.16",
                        numpy_version="2.4.6",
                        scikit_image_version="0.26.0",
                        runtime_fingerprint_sha256="2" * 64,
                    )

            class Completed:
                returncode = 1
                stdout = json.dumps({
                    "status": "failed",
                    "error_type": "ValueError",
                    "error_code": "degenerate_face_budget_exceeded",
                }) + "\n"
                stderr = "/private/path/that/must/not/be/exposed"

            service = VolumeSurfaceService(
                data_dir=root,
                volume_rendering_service=VolumeService(),
                worker_python="/opt/voxelatlas-surface/bin/python",
                worker_script=WORKER_PATH,
                runtime_qualifier=Qualifier(),
                runner=lambda *args, **kwargs: Completed(),
            )
            with self.assertRaises(VolumeSurfaceUnavailableError) as caught:
                service.surface_latest(isovalue=300.0)

        self.assertEqual(
            str(caught.exception),
            "Volume surface worker failed: degenerate_face_budget_exceeded",
        )
        self.assertNotIn("private", str(caught.exception))

    def test_worker_contract_reports_cleanup_metadata_and_safe_error_codes(self):
        text = WORKER_PATH.read_text(encoding="utf-8")
        self.assertIn('"degenerate_triangle_count"', text)
        self.assertIn('"degenerate_triangle_fraction"', text)
        self.assertIn('"unreferenced_vertex_count"', text)
        self.assertIn('"error_code"', text)
        self.assertNotIn('"error": str(exc)', text)


if __name__ == "__main__":
    unittest.main()
