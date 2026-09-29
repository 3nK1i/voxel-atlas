"""Synthetic-only Phase 6G2 tests: no patient files, credentials, or runtime writes."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
from skimage.measure import marching_cubes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from voxelatlas.segmentation_surface_mpr_agreement import (  # noqa: E402
    _intersect_triangles,
    _point_to_segments_mm,
    three_plane_mpr_surface_agreement_mm,
)


class Phase6G2MprAgreement(unittest.TestCase):
    def setUp(self):
        self.mask = np.zeros((7, 8, 9), dtype=bool)
        self.mask[1:6, 2:7, 2:8] = True
        self.affine = np.eye(4)
        # Acquisition axes differ from LPS world axes and spacings are anisotropic.
        self.affine[:3, :3] = [[0., 0., -2.], [0., 3., 0.], [4., 0., 0.]]
        self.affine[:3, 3] = [22., 30., 60.]
        vertices, self.faces, _, _ = marching_cubes(np.pad(self.mask.astype(np.uint8), 1), level=0.5,
                                                     gradient_direction='descent', allow_degenerate=False,
                                                     method='lewiner')
        self.vertices = (vertices - 1.) @ self.affine[:3, :3].T + self.affine[:3, 3]
        self.descriptors = self.make_descriptors()
        self.indices = {name: value['slice_count'] // 2 for name, value in self.descriptors.items()}
        self.mask.setflags(write=False)
        self.vertices.setflags(write=False)
        self.faces.setflags(write=False)

    def make_descriptors(self):
        corners = np.array([[s, r, c] for s in (0, self.mask.shape[0] - 1)
                            for r in (0, self.mask.shape[1] - 1)
                            for c in (0, self.mask.shape[2] - 1)], dtype=float)
        world = corners @ self.affine[:3, :3].T + self.affine[:3, 3]
        mins, maxs = world.min(axis=0), world.max(axis=0)
        inverse = np.linalg.inv(self.affine[:3, :3])
        spacing = [1. / np.linalg.norm(inverse @ np.eye(3)[axis]) for axis in range(3)]
        descriptors = {}
        for name, n, h, v, rev in (
            ('axial', 2, 0, 1, False), ('coronal', 1, 0, 2, True),
            ('sagittal', 0, 1, 2, True),
        ):
            def spec(axis):
                count = int(round((maxs[axis] - mins[axis]) / spacing[axis])) + 1
                return count, (maxs[axis] - mins[axis]) / (count - 1)
            count, ds = spec(n)
            width, dh = spec(h)
            height, dv = spec(v)
            descriptors[name] = {
                'plane': name, 'normal_axis': 'xyz'[n], 'horizontal_axis': 'xyz'[h],
                'vertical_axis': 'xyz'[v], 'vertical_reverse': rev,
                'slice_count': count, 'slice_spacing_mm': ds,
                'position_range_mm': [mins[n], maxs[n]],
                'image_width': width, 'image_height': height,
                'horizontal_range_mm': [mins[h], maxs[h]],
                'vertical_range_mm': [mins[v], maxs[v]],
                'pixel_spacing_mm': [dv, dh],
            }
        return descriptors

    def check(self, positions=None, *, sample_limit=128, descriptors=None, indices=None):
        return three_plane_mpr_surface_agreement_mm(
            self.mask, self.affine, self.vertices if positions is None else positions, self.faces,
            self.descriptors if descriptors is None else descriptors,
            self.indices if indices is None else indices, sample_limit=sample_limit,
        )

    def test_exact_reference_has_zero_three_plane_contour_distance(self):
        result = self.check()
        self.assertTrue(result['all_planes_have_contours'])
        self.assertEqual(result['units'], 'mm')
        self.assertEqual(result['coordinate_system'], 'patient_lps')
        self.assertFalse(result['source_mutation'])
        self.assertEqual(result['raster_mpr_overlay_equivalence'], 'not_computed')
        self.assertEqual(result['clinical_validation'], 'not_claimed')
        for name, plane in result['planes'].items():
            with self.subTest(plane=name):
                self.assertEqual(plane['status'], 'sampled_contour_agreement')
                self.assertLess(plane['symmetric_max_sampled_mm'], 1e-9)
                self.assertTrue(plane['candidate_to_reference']['exact_target_segment_distance_per_sample'])
                self.assertFalse(plane['qualified'])
        self.assertFalse(self.mask.flags.writeable)
        self.assertFalse(self.vertices.flags.writeable)
        self.assertFalse(self.faces.flags.writeable)

    def test_translated_mesh_has_detectable_error_in_all_three_planes(self):
        moved = self.vertices + [0.55, 0.45, 0.60]
        result = self.check(moved)
        for plane in result['planes'].values():
            self.assertEqual(plane['status'], 'sampled_contour_agreement')
            self.assertGreater(plane['symmetric_max_sampled_mm'], 0.1)
        np.testing.assert_array_equal(self.vertices + [0.55, 0.45, 0.60], moved)

    def test_mpr_world_planes_and_vertical_orientation_are_not_acquisition_indices(self):
        result = self.check(sample_limit=10)
        self.assertEqual(result['planes']['axial']['mpr_vertical_reversed'], False)
        self.assertEqual(result['planes']['coronal']['mpr_vertical_reversed'], True)
        self.assertEqual(result['planes']['sagittal']['mpr_vertical_reversed'], True)
        for name, descriptor in self.descriptors.items():
            self.assertAlmostEqual(result['planes'][name]['plane_position_lps_mm'],
                                   descriptor['position_range_mm'][0] + self.indices[name]
                                   * descriptor['slice_spacing_mm'])
            self.assertLessEqual(result['planes'][name]['candidate_to_reference']['sample_count'], 10)

    def test_exact_segment_distance_is_not_endpoint_only(self):
        points = np.array([[5., 3.], [12., 0.]])
        segments = np.array([[[0., 0.], [10., 0.]]])
        values, tests = _point_to_segments_mm(points, segments)
        np.testing.assert_allclose(values, [3., 2.], atol=1e-12)
        self.assertEqual(tests, 2)

    def test_acquired_volume_edge_and_no_contour_are_not_silent_zero_agreement(self):
        boundary = np.zeros_like(self.mask)
        boundary[0:2, 3:5, 3:5] = True
        v, f, _, _ = marching_cubes(np.pad(boundary.astype(np.uint8), 1), level=0.5,
                                    gradient_direction='descent', allow_degenerate=False,
                                    method='lewiner')
        v = (v - 1) @ self.affine[:3, :3].T + self.affine[:3, 3]
        # Select an LPS Z plane outside this bounded region but within the study.
        new_indices = dict(self.indices)
        new_indices['axial'] = self.descriptors['axial']['slice_count'] - 1
        result = three_plane_mpr_surface_agreement_mm(boundary, self.affine, v, f,
                                                      self.descriptors, new_indices)
        self.assertFalse(result['all_planes_have_contours'])
        self.assertEqual(result['planes']['axial']['status'], 'no_contours_at_selected_slice')
        # The padded virtual exterior is retained: a boundary-reaching mask can still
        # yield an intersection on a valid interior LPS slice.
        new_indices['axial'] = 0
        result = three_plane_mpr_surface_agreement_mm(boundary, self.affine, v, f,
                                                      self.descriptors, new_indices)
        self.assertEqual(result['planes']['axial']['status'], 'sampled_contour_agreement')
        self.assertLess(result['planes']['axial']['symmetric_max_sampled_mm'], 1e-9)

    def test_mismatched_mpr_descriptors_and_invalid_inputs_fail_closed(self):
        cases = []
        altered = {k: dict(v) for k, v in self.descriptors.items()}
        altered['axial']['normal_axis'] = 'x'
        cases.append((altered, self.indices, self.vertices, self.mask, self.affine, 16))
        altered = {k: dict(v) for k, v in self.descriptors.items()}
        altered['coronal']['vertical_reverse'] = False
        cases.append((altered, self.indices, self.vertices, self.mask, self.affine, 16))
        altered = {k: dict(v) for k, v in self.descriptors.items()}
        altered['sagittal']['slice_spacing_mm'] = 1e3
        cases.append((altered, self.indices, self.vertices, self.mask, self.affine, 16))
        wrong_idx = dict(self.indices); wrong_idx['axial'] = 10000
        cases.append((self.descriptors, wrong_idx, self.vertices, self.mask, self.affine, 16))
        cases.append((self.descriptors, self.indices, self.vertices, self.mask, self.affine, 0))
        cases.append((self.descriptors, self.indices, self.vertices, self.mask, self.affine, 257))
        bad_v = self.vertices.copy(); bad_v[0, 1] = np.nan
        cases.append((self.descriptors, self.indices, bad_v, self.mask, self.affine, 16))
        bad_mask = self.mask.astype(np.uint8)
        cases.append((self.descriptors, self.indices, self.vertices, bad_mask, self.affine, 16))
        bad_affine = self.affine.copy(); bad_affine[3, 0] = 1
        cases.append((self.descriptors, self.indices, self.vertices, self.mask, bad_affine, 16))
        for descriptor, indices, vertices, mask, affine, limit in cases:
            with self.subTest(case=len(cases)):
                with self.assertRaises(ValueError):
                    three_plane_mpr_surface_agreement_mm(mask, affine, vertices, self.faces,
                                                         descriptor, indices, sample_limit=limit)

    def test_coplanar_face_does_not_claim_contour(self):
        tri = np.asarray([[[0., 0., 1.], [1., 0., 1.], [0., 1., 1.]]])
        with self.assertRaisesRegex(ValueError, 'Coplanar'):
            _intersect_triangles(tri, 2, 1., 0, 1)


if __name__ == '__main__':
    unittest.main()
