"""Phase 6J-D4.5B: direct MRI intensity-surface backend.

Synthetic volumes only. No segmentation, model inference, or clinical validation.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
import sys
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_surface_runtime import SegmentationSurfaceRuntimeReport  # noqa: E402
from voxelatlas.volume_surfaces import (  # noqa: E402
    DEFAULT_CT_BONE_ISOVALUE_HU,
    DEFAULT_MR_NORMALIZED_ISOVALUE,
    MRI_NORMALIZATION_HIGH_PERCENTILE,
    MRI_NORMALIZATION_LOW_PERCENTILE,
    MRI_NORMALIZATION_PROFILE,
    MRI_PRESENTATION_GAUSSIAN_SIGMA_MM,
    MRI_SURFACE_INTENSITY_UNITS,
    VOLUME_SURFACE_FLAGS,
    VOLUME_SURFACE_HEADER,
    VOLUME_SURFACE_MAGIC,
    VolumeSurfaceService,
    VolumeSurfaceUnavailableError,
    VolumeSurfaceValidationError,
)


class FakeVolumeRenderingService:
    def __init__(self, source):
        self.source = source

    def source_latest(self):
        return self.source


def make_source(root: Path, *, modality: str, units: str):
    study_dir = root / "studies" / ("a" * 32)
    derived = study_dir / "derived"
    derived.mkdir(parents=True)
    volume_path = derived / "volume.npy"
    volume = np.zeros((12, 14, 16), dtype=np.float32)
    zz, yy, xx = np.indices(volume.shape, dtype=np.float32)
    ellipsoid = ((zz - 5.5) / 4.0) ** 2 + ((yy - 6.5) / 5.0) ** 2 + ((xx - 7.5) / 6.0) ** 2
    volume[ellipsoid <= 1.0] = 900.0
    volume[ellipsoid <= 0.55] = 1200.0
    np.save(volume_path, volume, allow_pickle=False)
    return SimpleNamespace(
        study_dir=study_dir,
        volume_path=volume_path,
        source_series_uid="1.2.840.113619.2.55.3.45",
        modality=modality,
        dtype="float32",
        shape=tuple(volume.shape),
        spacing_mm=(1.5, 0.82, 0.82),
        array_index_to_patient_lps=(
            (0.0, 0.0, 0.82, 10.0),
            (0.0, 0.82, 0.0, 20.0),
            (1.5, 0.0, 0.0, 30.0),
            (0.0, 0.0, 0.0, 1.0),
        ),
        intensity_units=units,
        value_range=(0.0, 1200.0),
        volume_created_at_utc="2026-09-28T10:00:00+00:00",
        source_descriptor_sha256="1" * 64,
        volume=volume,
    )


class Qualifier:
    def qualify(self, python_executable):
        return SegmentationSurfaceRuntimeReport(
            True,
            "qualified",
            "qualified",
            python_version="3.12.3",
            numpy_version="2.5.3",
            scikit_image_version="0.26.0",
            runtime_fingerprint_sha256="2" * 64,
        )


class DirectMRBackendTests(unittest.TestCase):
    def test_mr_descriptor_is_backend_ready_but_ui_activation_is_deferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_source(root, modality="MR", units="modality")
            service = VolumeSurfaceService(
                data_dir=root,
                volume_rendering_service=FakeVolumeRenderingService(source),
                worker_python="/qualified/surface/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
            )
            descriptor = service.descriptor_latest()

        self.assertFalse(descriptor["available"])
        self.assertTrue(descriptor["backend_available"])
        self.assertEqual(descriptor["ui_activation"], "deferred_to_phase6j_d4_5c")
        self.assertEqual(descriptor["source_modality"], "MR")
        self.assertEqual(descriptor["source_intensity_units"], "modality")
        self.assertEqual(descriptor["surface_intensity_units"], MRI_SURFACE_INTENSITY_UNITS)
        self.assertEqual(descriptor["surface_isovalue_range"], [0.0, 1.0])
        self.assertEqual(descriptor["default_isovalue"], DEFAULT_MR_NORMALIZED_ISOVALUE)
        self.assertEqual(descriptor["presets"], [])
        self.assertTrue(descriptor["custom_isovalue_supported"])
        self.assertFalse(descriptor["segmentation_required"])
        self.assertEqual(descriptor["normalization"]["profile"], MRI_NORMALIZATION_PROFILE)
        self.assertEqual(descriptor["normalization"]["semantic_identity"], "none")
        self.assertEqual(descriptor["clinical_validation"], "not_claimed")

    def test_mr_surface_request_uses_normalized_signal_and_immutable_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_source(root, modality="MR", units="modality")
            before = sha256(source.volume_path.read_bytes()).hexdigest()

            def runner(command, **kwargs):
                self.assertFalse(kwargs["shell"])
                request_path = Path(command[command.index("--request-json") + 1])
                output_path = Path(command[command.index("--output-surface") + 1])
                request = json.loads(request_path.read_text(encoding="utf-8"))
                self.assertEqual(request["source_modality"], "MR")
                self.assertEqual(request["source_intensity_units"], "modality")
                self.assertEqual(request["surface_intensity_units"], MRI_SURFACE_INTENSITY_UNITS)
                self.assertEqual(request["isovalue"], DEFAULT_MR_NORMALIZED_ISOVALUE)
                self.assertEqual(request["normalization"]["profile"], MRI_NORMALIZATION_PROFILE)
                self.assertEqual(request["normalization"]["low_percentile"], MRI_NORMALIZATION_LOW_PERCENTILE)
                self.assertEqual(request["normalization"]["high_percentile"], MRI_NORMALIZATION_HIGH_PERCENTILE)
                self.assertEqual(request["normalization"]["gaussian_sigma_mm"], MRI_PRESENTATION_GAUSSIAN_SIGMA_MM)
                self.assertEqual(request["source_volume"], "immutable")
                self.assertEqual(request["coordinate_system"], "patient_lps")

                positions = np.asarray([[10, 20, 30], [11, 20, 30], [10, 21, 30]], dtype="<f4")
                normals = np.asarray([[0, 0, 1], [0, 0, 1], [0, 0, 1]], dtype="<f4")
                indices = np.asarray([0, 1, 2], dtype="<u4")
                pos = positions.tobytes(); norm = normals.tobytes(); ind = indices.tobytes()
                payload = VOLUME_SURFACE_HEADER.pack(
                    VOLUME_SURFACE_MAGIC, 1, 3, 3, len(pos), len(norm), len(ind), VOLUME_SURFACE_FLAGS
                ) + pos + norm + ind
                output_path.write_bytes(payload)
                report = {
                    "schema_version": 1,
                    "operation": "extract_volume_isosurface",
                    "extraction": "marching_cubes_isovalue",
                    "isovalue": DEFAULT_MR_NORMALIZED_ISOVALUE,
                    "intensity_units": MRI_SURFACE_INTENSITY_UNITS,
                    "normalization": {
                        "profile": MRI_NORMALIZATION_PROFILE,
                        "low_percentile": MRI_NORMALIZATION_LOW_PERCENTILE,
                        "high_percentile": MRI_NORMALIZATION_HIGH_PERCENTILE,
                        "low_value": 0.0,
                        "high_value": 1200.0,
                        "clip_to_unit_interval": True,
                        "gaussian_sigma_mm": MRI_PRESENTATION_GAUSSIAN_SIGMA_MM,
                    },
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
                    "bounds_lps_mm": [10.0, 20.0, 30.0, 11.0, 21.0, 30.0],
                    "coordinate_system": "patient_lps",
                    "runtime_fingerprint_sha256": "2" * 64,
                    "python_version": "3.12.3",
                    "numpy_version": "2.5.3",
                    "scikit_image_version": "0.26.0",
                    "source_volume": "immutable",
                    "clinical_validation": "not_claimed",
                }
                return SimpleNamespace(returncode=0, stdout=json.dumps(report) + "\n", stderr="")

            service = VolumeSurfaceService(
                data_dir=root,
                volume_rendering_service=FakeVolumeRenderingService(source),
                worker_python="/qualified/surface/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
                runtime_qualifier=Qualifier(),
                runner=runner,
            )
            surface = service.surface_latest(isovalue=DEFAULT_MR_NORMALIZED_ISOVALUE)
            after = sha256(source.volume_path.read_bytes()).hexdigest()

        self.assertEqual(before, after)
        self.assertEqual(surface.source_modality, "MR")
        self.assertEqual(surface.intensity_units, MRI_SURFACE_INTENSITY_UNITS)
        self.assertEqual(surface.isovalue, DEFAULT_MR_NORMALIZED_ISOVALUE)
        self.assertEqual(surface.coordinate_system, "patient_lps")
        self.assertEqual(surface.payload[:4], b"VXVS")

    def test_mr_normalized_isovalue_bounds_are_not_raw_modality_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_source(root, modality="MR", units="modality")
            service = VolumeSurfaceService(
                data_dir=root,
                volume_rendering_service=FakeVolumeRenderingService(source),
                worker_python="/qualified/surface/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
            )
            for invalid in (0.0, 1.0, 300.0, float("nan"), float("inf")):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(VolumeSurfaceValidationError):
                        service.surface_latest(isovalue=invalid)

    def test_direct_ct_contract_and_region_path_remain_ct_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ct = make_source(root, modality="CT", units="HU")
            ct.value_range = (-1000.0, 1200.0)
            ct_service = VolumeSurfaceService(
                data_dir=root,
                volume_rendering_service=FakeVolumeRenderingService(ct),
                worker_python="/qualified/surface/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
            )
            descriptor = ct_service.descriptor_latest()

        self.assertTrue(descriptor["available"])
        self.assertTrue(descriptor["backend_available"])
        self.assertEqual(descriptor["ui_activation"], "enabled")
        self.assertEqual(descriptor["surface_intensity_units"], "HU")
        self.assertEqual(descriptor["default_isovalue"], DEFAULT_CT_BONE_ISOVALUE_HU)
        self.assertEqual(descriptor["normalization"], None)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mr = make_source(root, modality="MR", units="modality")
            mr_service = VolumeSurfaceService(
                data_dir=root,
                volume_rendering_service=FakeVolumeRenderingService(mr),
                worker_python="/qualified/surface/python",
                worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
            )
            with self.assertRaises(VolumeSurfaceUnavailableError):
                mr_service.region_evidence_latest(surface_id="vsurf-" + "1" * 32)


if __name__ == "__main__":
    unittest.main()
