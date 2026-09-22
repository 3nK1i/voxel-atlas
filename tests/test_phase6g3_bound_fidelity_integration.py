"""6G3 synthetic integration tests: no patient artifacts, server, or writes."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import json
import struct
import sys
import tempfile
import unittest

import numpy as np
from skimage.measure import marching_cubes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from voxelatlas.segmentation_surfaces import SegmentationSurface  # noqa: E402
from voxelatlas.segmentation_surface_fidelity_report import bound_fidelity_report  # noqa: E402


class BoundIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'labels.npy'
        self.labels = np.zeros((7, 8, 9), dtype=np.uint16)
        self.labels[1:6, 2:7, 2:8] = 91
        np.save(self.path, self.labels, allow_pickle=False)
        self.affine = np.eye(4, dtype=np.float64)
        self.affine[:3, :3] = [[0., 0., -2.], [0., 3., 0.], [4., 0., 0.]]
        self.affine[:3, 3] = [22., 30., 60.]
        self.study = 'a' * 32
        self.mapid = 'map-' + 'b' * 32
        self.descriptor = {
            'state': 'ready', 'label_map_id': self.mapid, 'source_study_id': self.study,
            'coordinate_system': 'patient_lps', 'length_units': 'mm', 'representation': 'label_map',
            'artifact_format': 'npy', 'dtype': 'uint16', 'axis_order': ['slice', 'row', 'column'],
            'shape': list(self.labels.shape), 'artifact_sha256': sha256(self.path.read_bytes()).hexdigest(),
            'artifact_bytes': self.path.stat().st_size, 'array_index_to_patient_lps': self.affine.tolist(),
            'present_labels': [0, 91], 'identity_sha256': 'c' * 64,
            'provenance_sha256': 'd' * 64,
            'source_volume_descriptor_sha256': 'a' * 64,
            'source_volume_artifact_sha256': 'b' * 64,
        }
        mask = self.labels == 91
        v, f, _, _ = marching_cubes(np.pad(mask.astype(np.uint8), 1), level=.5,
                                     gradient_direction='descent', allow_degenerate=False,
                                     method='lewiner')
        self.vertices = (v.astype(np.float64) - 1) @ self.affine[:3, :3].T + self.affine[:3, 3]
        self.faces = f.astype(np.uint32)
        self.accurate = self.make_surface('accurate', self.vertices)
        self.refined = self.make_surface('refined', self.vertices + [.07, .04, .05], self.accurate)
        self.descriptors = self.make_descriptors()
        self.indices = {k: v['slice_count'] // 2 for k, v in self.descriptors.items()}

    def make_surface(self, quality, vertices, accurate=None):
        p = np.asarray(vertices, dtype='<f4')
        n = np.tile(np.asarray([[0, 0, 1]], dtype='<f4'), (len(p), 1))
        f = np.asarray(self.faces.reshape(-1), dtype='<u4')
        payload = struct.pack('<4s8I', b'VXSF', 2, 91, len(p), len(f), p.nbytes, n.nbytes,
                              f.nbytes, 1) + p.tobytes() + n.tobytes() + f.tobytes()
        return SegmentationSurface(
            label_map_id=self.mapid, label_id=91, quality=quality,
            extraction='marching_cubes_half_voxel', coordinate_system='patient_lps', stride=1,
            vertex_count=len(p), triangle_count=len(f) // 3,
            bounds_lps_mm=tuple(np.r_[p.min(0), p.max(0)].astype(float)),
            payload_sha256=sha256(payload).hexdigest(), payload=payload,
            schema_version=2, media_type='application/x-voxelatlas-surface-v2',
            surface_id='surf-' + ('1' if quality == 'accurate' else '2') * 32,
            provenance_sha256='e' * 64, normal_count=len(p),
            refinement='bounded_taubin_vertex_clustering' if quality == 'refined' else '',
            reference_surface_id=accurate.surface_id if accurate else '',
            reference_payload_sha256=accurate.payload_sha256 if accurate else '',
        )

    def make_descriptors(self):
        corners = np.array([[i, j, k] for i in (0, 6) for j in (0, 7) for k in (0, 8)])
        world = corners @ self.affine[:3, :3].T + self.affine[:3, 3]
        mi, ma = world.min(0), world.max(0)
        inv = np.linalg.inv(self.affine[:3, :3])
        spacing = [1. / np.linalg.norm(inv @ np.eye(3)[axis]) for axis in range(3)]
        result = {}
        for name, n, h, v, reverse in (('axial', 2, 0, 1, False),
                                      ('coronal', 1, 0, 2, True),
                                      ('sagittal', 0, 1, 2, True)):
            def axis(a):
                count = int(round((ma[a] - mi[a]) / spacing[a])) + 1
                return count, (ma[a] - mi[a]) / (count - 1)
            count, ds = axis(n)
            width, dx = axis(h)
            height, dy = axis(v)
            result[name] = dict(plane=name, normal_axis='xyz'[n], horizontal_axis='xyz'[h],
                                vertical_axis='xyz'[v], vertical_reverse=reverse,
                                slice_count=count, slice_spacing_mm=ds,
                                position_range_mm=[mi[n], ma[n]],
                                image_width=width, image_height=height,
                                horizontal_range_mm=[mi[h], ma[h]],
                                vertical_range_mm=[mi[v], ma[v]], pixel_spacing_mm=[dy, dx])
        return result

    def run_report(self, surfaces=None, descriptor=None, indices=None, path=None,
                   mpr_study_id=None):
        return bound_fidelity_report(
            source_study_id=self.study,
            mpr_study_id=self.study if mpr_study_id is None else mpr_study_id,
            label_map_descriptor=self.descriptor if descriptor is None else descriptor,
            label_artifact_path=self.path if path is None else path,
            label_id=91, surfaces={'accurate': self.accurate, 'refined': self.refined}
            if surfaces is None else surfaces,
            mpr_descriptors=self.descriptors,
            slice_indices=self.indices if indices is None else indices,
            mesh_sample_limit=96, contour_sample_limit=96,
        )

    def test_source_bound_accurate_and_refined_are_reported_separately(self):
        before = self.path.read_bytes()
        report = self.run_report()
        self.assertEqual(report['status'], 'sampled_evidence_only')
        self.assertEqual(set(report['surfaces']), {'accurate', 'refined'})
        self.assertLess(report['surfaces']['accurate']['surface_distances']['symmetric_max_sampled_mm'], 1e-3)
        self.assertGreater(report['surfaces']['refined']['surface_distances']['symmetric_max_sampled_mm'], .01)
        self.assertTrue(report['surfaces']['accurate']['mpr']['all_planes_have_contours'])
        self.assertTrue(report['surfaces']['refined']['mpr']['all_planes_have_contours'])
        self.assertEqual(report['source']['roi_index_start'], [1, 2, 2])
        self.assertEqual(report['source']['roi_shape'], [5, 5, 6])
        self.assertEqual(report['source']['coordinate_system'], 'patient_lps')
        self.assertEqual(report['source']['artifact_sha256'], self.descriptor['artifact_sha256'])
        self.assertEqual(report['sampling_claim'], 'sampled_not_exhaustive')
        self.assertEqual(report['raster_overlay_equivalence'], 'not_evaluated')
        self.assertEqual(report['clinical_validation'], 'not_claimed')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(sha256(self.accurate.payload).hexdigest(), self.accurate.payload_sha256)
        self.assertEqual(report['source']['label_id'], 91)
        self.assertTrue(json.dumps(report, allow_nan=False))

    def test_missing_refined_is_explicit_and_not_zero(self):
        report = self.run_report(surfaces={'accurate': self.accurate})
        self.assertEqual(report['status'], 'needs_review')
        self.assertEqual(report['surfaces']['refined']['status'], 'not_available')
        self.assertNotIn('surface_distances', report['surfaces']['refined'])

    def test_wrong_study_label_and_mpr_are_rejected(self):
        for changes in ({'source_study_id': 'f' * 32}, {'present_labels': [0, 1]},
                        {'coordinate_system': 'ras'}, {'shape': [7, 8, 10]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_report(descriptor={**self.descriptor, **changes})
        with self.assertRaises(ValueError):
            self.run_report(mpr_study_id='e' * 32)

    def test_digest_mismatch_and_invalid_surface_link_fail_closed(self):
        bad = {**self.descriptor, 'artifact_sha256': '0' * 64}
        with self.assertRaises(ValueError):
            self.run_report(descriptor=bad)
        with self.assertRaises(ValueError):
            self.run_report(surfaces={'accurate': replace(self.accurate, payload_sha256='0' * 64)})
        with self.assertRaises(ValueError):
            self.run_report(surfaces={'accurate': self.accurate,
                                      'refined': replace(self.refined, reference_surface_id='surf-invalid')})
        with self.assertRaises(ValueError):
            self.run_report(surfaces={'accurate': replace(self.accurate, label_map_id='map-other')})

    def test_mutated_npy_content_and_symlink_are_rejected(self):
        self.path.write_bytes(self.path.read_bytes() + b'X')
        with self.assertRaises(ValueError):
            self.run_report()
        self.path.unlink()
        link = Path(self.temp.name) / 'linked.npy'
        link.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            self.run_report(path=link)

    def test_finite_budget_failure_is_not_a_partial_qualified_report(self):
        with patch('voxelatlas.segmentation_surface_fidelity_report.MAX_6G1_MASK_VOXELS', 10):
            with self.assertRaisesRegex(ValueError, 'ROI exceeds'):
                self.run_report()

    def test_wrong_mpr_world_bounds_and_surface_quality_fail_closed(self):
        bad = {k: dict(v) for k, v in self.descriptors.items()}
        bad['axial']['horizontal_range_mm'] = [100., 114.]
        original = self.descriptors
        try:
            self.descriptors = bad
            with self.assertRaises(ValueError):
                self.run_report()
        finally:
            self.descriptors = original
        with self.assertRaises(ValueError):
            self.run_report(surfaces={'accurate': replace(self.accurate, quality='preview')})

    def test_missing_one_plane_is_visible_in_overall_status(self):
        indices = dict(self.indices)
        indices['axial'] = self.descriptors['axial']['slice_count'] - 1
        report = self.run_report(indices=indices)
        self.assertEqual(report['status'], 'needs_review')
        self.assertEqual(report['surfaces']['accurate']['mpr']['planes']['axial']['status'],
                         'no_contours_at_selected_slice')


if __name__ == '__main__':
    unittest.main()
