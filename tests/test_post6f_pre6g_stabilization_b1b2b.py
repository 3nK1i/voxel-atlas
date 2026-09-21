"""B1B2B: real byte-bound labels, immutable CT, no extraction or auto-hiding."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from skimage.measure import marching_cubes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from voxelatlas.volume_surfaces import (  # noqa: E402
    VolumeDerivedSurface, VolumeSurfaceService,
    VolumeSurfaceUnavailableError, VolumeSurfaceValidationError,
)


class B1B2BRegionTransportTests(unittest.TestCase):
    def test_isolated_worker_binds_exact_original_triangle_order_and_keeps_source(self):
        ct = np.full((18, 26, 26), -1000, dtype=np.float32)
        ct[2:16, 2:14, 2:14] = 0
        ct[4:13, 4:10, 4:10] = 650
        ct[3:15, 19:23, 2:24] = 0
        ct[4:14, 20:22, 4:22] = 650
        verts, faces, normals, _ = marching_cubes(ct, level=300, allow_degenerate=False)
        positions = np.asarray(verts, dtype='<f4').tobytes()
        normal_bytes = np.asarray(normals, dtype='<f4').tobytes()
        indices = np.asarray(faces, dtype='<u4').tobytes()
        payload = struct.pack('<4s7I', b'VXVS', 1, len(verts), faces.size,
                              len(positions), len(normal_bytes), len(indices), 1) + positions + normal_bytes + indices
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study = root / 'studies' / ('a' * 32)
            study.mkdir(parents=True)
            source_path = study / 'volume.npy'
            np.save(source_path, ct, allow_pickle=False)
            source_sha = sha256(source_path.read_bytes()).hexdigest()
            surface_sha = sha256(payload).hexdigest()
            source = SimpleNamespace(study_dir=study, volume_path=source_path,
                                     modality='CT', intensity_units='HU',
                                     source_series_uid='synthetic',
                                     array_index_to_patient_lps=np.eye(4).tolist())
            surface_id = 'vsurf-' + 'b' * 32
            surface = VolumeDerivedSurface(
                study_id=study.name, source_series_uid='synthetic', source_type='canonical_volume',
                source_modality='CT', intensity_units='HU', isovalue=300.0, quality='native',
                extraction='marching_cubes_isovalue', coordinate_system='patient_lps',
                vertex_count=len(verts), triangle_count=len(faces),
                bounds_lps_mm=(0.,0.,0.,17.,25.,25.), payload_sha256=surface_sha,
                payload=payload, surface_id=surface_id, provenance_sha256='c'*64,
                runtime_fingerprint_sha256='d'*64,
            )
            class SourceService:
                def source_latest(self):
                    return source
            service = VolumeSurfaceService(
                data_dir=root, volume_rendering_service=SourceService(),
                worker_python=sys.executable,
                worker_script=ROOT / 'scripts' / 'phase6d1_volume_surface_worker.py',
                timeout_seconds=90,
            )
            service._cache[(study.name, source_sha, '300', 'test-runtime')] = surface
            result = service.region_evidence_latest(surface_id=surface_id)
            self.assertEqual(result.surface_id, surface_id)
            self.assertEqual(result.surface_sha256, surface_sha)
            self.assertEqual(len(result.labels), len(faces))
            self.assertEqual(sum(result.face_counts), len(faces))
            self.assertGreater(result.face_counts[1], 0)
            self.assertGreater(result.face_counts[2], 0)
            self.assertEqual(result.classification, 'not_anatomical')
            self.assertEqual(sha256(source_path.read_bytes()).hexdigest(), source_sha)
            self.assertEqual(service.region_evidence_latest(surface_id=surface_id), result)
            with self.assertRaises(VolumeSurfaceUnavailableError):
                service.region_evidence_latest(surface_id='vsurf-' + 'e'*32)
            # A different canonical source invalidates the resident-surface binding.
            changed = ct.copy()
            changed[0, 0, 0] = -998
            np.save(source_path, changed, allow_pickle=False)
            with self.assertRaises(VolumeSurfaceUnavailableError):
                service.region_evidence_latest(surface_id=surface_id)

    def test_auth_and_binary_route_contract_not_auto_enabled(self):
        app = (ROOT/'backend/voxelatlas/app.py').read_text(encoding='utf-8')
        viewer = (ROOT/'web/js/volume-surface-viewer.js').read_text(encoding='utf-8')
        index = (ROOT/'web/index.html').read_text(encoding='utf-8')
        self.assertIn('@app.get("/api/studies/latest/volume-surface/regions")', app)
        route = app.split('@app.get("/api/studies/latest/volume-surface/regions")',1)[1].split('@app.get(',1)[0]
        self.assertIn('Depends(require_username)', route)
        self.assertIn('"Cache-Control": "no-store"', route)
        self.assertIn('evidence.labels', route)
        self.assertIn('target.surfaceId', viewer)
        self.assertIn('target.payloadSha256', viewer)
        self.assertIn('this.current !== target', viewer)
        self.assertIn('<option value="all">Full geometry</option>', index)
        self.assertIn('<select id="volumeSurfaceRegionMode" disabled>', index)
        self.assertNotIn('value="hide-region-1" selected', index)


if __name__ == '__main__':
    unittest.main()
