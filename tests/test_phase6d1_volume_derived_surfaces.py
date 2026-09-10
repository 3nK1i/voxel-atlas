from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class FakeVolumeRenderingService:
    def __init__(self, source):
        self.source = source

    def source_latest(self):
        return self.source


class Phase6D1VolumeDerivedSurfaceTests(unittest.TestCase):
    def make_source(self, root: Path, *, modality="CT", units="HU", value_range=(-1000.0, 1200.0)):
        study_dir = root / "studies" / ("a" * 32)
        derived = study_dir / "derived"
        derived.mkdir(parents=True)
        volume_path = derived / "volume.npy"
        volume = np.zeros((4, 5, 6), dtype=np.float32)
        volume[1:3, 1:4, 2:5] = 800.0
        np.save(volume_path, volume, allow_pickle=False)
        return SimpleNamespace(
            study_dir=study_dir,
            volume_path=volume_path,
            source_series_uid="1.2.840.113619.2.55.3.42",
            modality=modality,
            dtype="float32",
            shape=tuple(volume.shape),
            spacing_mm=(4.0, 3.0, 2.0),
            array_index_to_patient_lps=(
                (0.0, 0.0, 2.0, 10.0),
                (0.0, 3.0, 0.0, 20.0),
                (4.0, 0.0, 0.0, 30.0),
                (0.0, 0.0, 0.0, 1.0),
            ),
            intensity_units=units,
            value_range=value_range,
            volume_created_at_utc="2026-09-10T10:00:00+00:00",
            source_descriptor_sha256="1" * 64,
            volume=volume,
        )

    def test_descriptor_exposes_ct_hu_surface_without_segmentation_dependency(self):
        from voxelatlas.volume_surfaces import VolumeSurfaceService

        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(Path(tmp))
            service = VolumeSurfaceService(
                data_dir=Path(tmp),
                volume_rendering_service=FakeVolumeRenderingService(source),
                worker_python="/opt/voxelatlas-surface/bin/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
            )
            descriptor = service.descriptor_latest()

        self.assertTrue(descriptor["available"])
        self.assertEqual(descriptor["source_type"], "canonical_volume")
        self.assertEqual(descriptor["source_modality"], "CT")
        self.assertEqual(descriptor["source_intensity_units"], "HU")
        self.assertEqual(descriptor["default_isovalue"], 300.0)
        self.assertEqual(descriptor["coordinate_system"], "patient_lps")
        self.assertEqual(descriptor["segmentation_required"], False)
        self.assertEqual(descriptor["clinical_validation"], "not_claimed")

    def test_ct_isovalue_must_be_finite_and_strictly_inside_source_range(self):
        from voxelatlas.volume_surfaces import VolumeSurfaceService, VolumeSurfaceValidationError

        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(Path(tmp))
            service = VolumeSurfaceService(
                data_dir=Path(tmp),
                volume_rendering_service=FakeVolumeRenderingService(source),
                worker_python="/opt/voxelatlas-surface/bin/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
            )
            for invalid in (-1000.0, 1200.0, float("inf"), float("nan")):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(VolumeSurfaceValidationError):
                        service.surface_latest(isovalue=invalid)

    def test_mri_is_not_silently_given_a_ct_hu_surface(self):
        from voxelatlas.volume_surfaces import VolumeSurfaceService, VolumeSurfaceUnavailableError

        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_source(Path(tmp), modality="MR", units="modality", value_range=(0.0, 1500.0))
            service = VolumeSurfaceService(
                data_dir=Path(tmp),
                volume_rendering_service=FakeVolumeRenderingService(source),
                worker_python="/opt/voxelatlas-surface/bin/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
            )
            descriptor = service.descriptor_latest()
            self.assertFalse(descriptor["available"])
            self.assertEqual(descriptor["source_modality"], "MR")
            with self.assertRaises(VolumeSurfaceUnavailableError):
                service.surface_latest(isovalue=300.0)

    def test_worker_boundary_is_patient_lps_source_immutable_and_uses_dedicated_transport(self):
        from voxelatlas.segmentation_surface_runtime import SegmentationSurfaceRuntimeReport
        from voxelatlas.volume_surfaces import (
            VOLUME_SURFACE_FLAGS,
            VOLUME_SURFACE_HEADER,
            VOLUME_SURFACE_MAGIC,
            VolumeSurfaceService,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            before = sha256(source.volume_path.read_bytes()).hexdigest()

            class Qualifier:
                def qualify(self, python_executable):
                    self.python_executable = python_executable
                    return SegmentationSurfaceRuntimeReport(
                        True, "qualified", "qualified",
                        python_version="3.11.16",
                        numpy_version="2.4.6",
                        scikit_image_version="0.26.0",
                        runtime_fingerprint_sha256="2" * 64,
                    )

            def runner(command, **kwargs):
                self.assertFalse(kwargs["shell"])
                request_path = Path(command[command.index("--request-json") + 1])
                output_path = Path(command[command.index("--output-surface") + 1])
                request = json.loads(request_path.read_text(encoding="utf-8"))
                self.assertEqual(request["operation"], "extract_volume_isosurface")
                self.assertEqual(request["source_volume"], "immutable")
                self.assertEqual(request["coordinate_system"], "patient_lps")
                self.assertEqual(request["isovalue"], 300.0)
                positions = np.asarray([[10,20,30],[12,20,30],[10,23,30]], dtype="<f4")
                normals = np.asarray([[0,0,1],[0,0,1],[0,0,1]], dtype="<f4")
                indices = np.asarray([0,1,2], dtype="<u4")
                pos = positions.tobytes(); norm = normals.tobytes(); ind = indices.tobytes()
                payload = VOLUME_SURFACE_HEADER.pack(
                    VOLUME_SURFACE_MAGIC, 1, 3, 3, len(pos), len(norm), len(ind), VOLUME_SURFACE_FLAGS
                ) + pos + norm + ind
                output_path.write_bytes(payload)
                report = {
                    "schema_version": 1,
                    "operation": "extract_volume_isosurface",
                    "extraction": "marching_cubes_isovalue",
                    "isovalue": 300.0,
                    "intensity_units": "HU",
                    "vertex_count": 3,
                    "triangle_count": 1,
                    "raw_vertex_count": 3,
                    "raw_triangle_count": 1,
                    "degenerate_triangle_count": 0,
                    "degenerate_triangle_fraction": 0.0,
                    "unreferenced_vertex_count": 0,
                    "degenerate_double_area_epsilon_mm2": 1e-12,
                    "max_degenerate_triangle_fraction": 1e-4,
                    "payload_bytes": len(payload),
                    "payload_sha256": sha256(payload).hexdigest(),
                    "bounds_lps_mm": [10.0,20.0,30.0,12.0,23.0,30.0],
                    "coordinate_system": "patient_lps",
                    "runtime_fingerprint_sha256": "2" * 64,
                    "python_version": "3.11.16",
                    "numpy_version": "2.4.6",
                    "scikit_image_version": "0.26.0",
                    "source_volume": "immutable",
                    "clinical_validation": "not_claimed",
                }
                class Completed:
                    returncode = 0
                    stdout = json.dumps(report) + "\n"
                    stderr = ""
                return Completed()

            service = VolumeSurfaceService(
                data_dir=root,
                volume_rendering_service=FakeVolumeRenderingService(source),
                worker_python="/opt/voxelatlas-surface/bin/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
                runtime_qualifier=Qualifier(),
                runner=runner,
            )
            surface = service.surface_latest(isovalue=300.0)
            after = sha256(source.volume_path.read_bytes()).hexdigest()

        self.assertEqual(before, after)
        self.assertEqual(surface.source_type, "canonical_volume")
        self.assertEqual(surface.coordinate_system, "patient_lps")
        self.assertEqual(surface.intensity_units, "HU")
        self.assertEqual(surface.isovalue, 300.0)
        self.assertEqual(surface.vertex_count, 3)
        self.assertEqual(surface.triangle_count, 1)
        self.assertEqual(surface.payload[:4], b"VXVS")
        self.assertNotIn(b"VXSF", surface.payload[:4])

    def test_http_contract_is_authenticated_no_store_and_surface_source_is_explicit(self):
        from fastapi.testclient import TestClient
        from voxelatlas import config
        from voxelatlas.app import create_app
        from voxelatlas.passwords import hash_password
        from voxelatlas.volume_surfaces import VolumeDerivedSurface

        class FakeService:
            def descriptor_latest(self):
                return {
                    "schema_version": 1, "available": True, "study_id": "a" * 32,
                    "source_type": "canonical_volume", "source_modality": "CT",
                    "source_intensity_units": "HU", "source_value_range": [-1000.0, 1200.0],
                    "default_isovalue": 300.0, "coordinate_system": "patient_lps",
                    "segmentation_required": False, "clinical_validation": "not_claimed",
                }
            def surface_latest(self, *, isovalue):
                payload = b"VXVS" + b"x" * 28
                return VolumeDerivedSurface(
                    study_id="a" * 32, source_series_uid="1.2.3", source_type="canonical_volume",
                    source_modality="CT", intensity_units="HU", isovalue=float(isovalue),
                    quality="native", extraction="marching_cubes_isovalue", coordinate_system="patient_lps",
                    vertex_count=3, triangle_count=1, bounds_lps_mm=(0,0,0,1,1,1),
                    payload_sha256=sha256(payload).hexdigest(), payload=payload,
                    surface_id="vsurf-" + "1" * 32, provenance_sha256="2" * 64,
                    runtime_fingerprint_sha256="3" * 64,
                )

        with tempfile.TemporaryDirectory() as tmp:
            settings = config.AppSettings(
                environment="test", session_secret="x" * 48, secure_cookies=False,
                session_cookie_name="voxelatlas_session",
                allowed_hosts=("testserver", "127.0.0.1", "localhost"), data_dir=Path(tmp),
                max_upload_mib=512, auth_username="engineer",
                auth_password_hash=hash_password("correct horse battery staple"),
                session_ttl_minutes=60,
            )
            with TestClient(create_app(settings=settings, volume_surface_service=FakeService())) as client:
                self.assertEqual(client.get("/api/studies/latest/volume-surface").status_code, 401)
                client.post("/api/auth/login", json={"username":"engineer","password":"correct horse battery staple"})
                descriptor = client.get("/api/studies/latest/volume-surface")
                surface = client.post("/api/studies/latest/volume-surface", json={"isovalue": 300.0})

        self.assertEqual(descriptor.status_code, 200)
        self.assertEqual(descriptor.headers["cache-control"], "no-store")
        self.assertEqual(descriptor.json()["volume_surface"]["source_type"], "canonical_volume")
        self.assertEqual(surface.status_code, 200)
        self.assertEqual(surface.headers["cache-control"], "no-store")
        self.assertEqual(surface.headers["x-voxelatlas-volume-surface-source"], "canonical_volume")
        self.assertEqual(surface.headers["x-voxelatlas-volume-surface-isovalue"], "300.000000")
        self.assertEqual(surface.headers["x-voxelatlas-volume-surface-degenerate-triangles-removed"], "0")
        self.assertEqual(surface.headers["x-voxelatlas-volume-surface-unreferenced-vertices-removed"], "0")

    def test_frontend_requires_explicit_build_and_does_not_enable_phase6d2_modes(self):
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")

        self.assertIn("Build Surface", index)
        self.assertIn("volumeSurfaceBuild", app)
        self.assertIn("volumeSurfaceLayer.build", app)
        activate = app[app.index("async function activatePatientVolumeRendering"):app.index("function resetWorkspace")]
        self.assertNotIn("volumeSurfaceLayer.build(", activate)
        self.assertIn("VXVS", viewer)
        self.assertNotIn("VXSF", viewer)
        self.assertNotIn("SegmentationSurface", viewer)
        self.assertNotIn("Volume / Surface / Combined", index)

    def test_phase6d1_documented_boundary_keeps_6d2_and_6e_out_of_scope(self):
        doc = (ROOT / "docs/phase_history/PHASE6D1_VOLUME_DERIVED_SURFACES.md").read_text(encoding="utf-8")
        self.assertIn("without TotalSegmentator", doc)
        self.assertIn("Phase 6D2", doc)
        self.assertIn("not enabled", doc.lower())
        self.assertIn("Phase 6E", doc)
        self.assertIn("clinical validation is not claimed", doc.lower())


if __name__ == "__main__":
    unittest.main()
