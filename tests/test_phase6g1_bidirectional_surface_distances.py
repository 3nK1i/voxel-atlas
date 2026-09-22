"""Synthetic, study-free contract tests for sampled exact point-to-triangle distances."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
import numpy as np
from skimage.measure import marching_cubes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from voxelatlas.segmentation_surface_distances import (  # noqa: E402
    _point_to_triangles_squared,
    _sampled_to_surface,
    sampled_bidirectional_mask_surface_mm,
)


class Phase6G1Distances(unittest.TestCase):
    def setUp(self):
        self.mask = np.zeros((5, 6, 7), dtype=bool)
        self.mask[1:4, 1:5, 2:6] = True
        self.mask.setflags(write=False)
        self.affine = np.eye(4)
        self.affine[:3, :3] = [[0, 0, -2], [0, 3, 0], [4, 0, 0]]
        self.affine[:3, 3] = [12, 24, 36]
        self.vertices, self.faces = self.reference(self.mask, self.affine)
        self.vertices.setflags(write=False)
        self.faces.setflags(write=False)

    @staticmethod
    def reference(mask, affine):
        vertices, faces, _, _ = marching_cubes(
            np.pad(mask.astype(np.uint8), 1), level=0.5,
            gradient_direction='descent', allow_degenerate=False, method='lewiner',
        )
        vertices = (vertices.astype(np.float64) - 1) @ affine[:3, :3].T + affine[:3, 3]
        return vertices, faces

    def test_identical_mesh_is_zero_both_directions_in_anisotropic_lps(self):
        result = sampled_bidirectional_mask_surface_mm(self.mask, self.affine, self.vertices, self.faces, sample_limit=128)
        self.assertLess(result['symmetric_max_sampled_mm'], 1e-10)
        self.assertEqual(result['units'], 'mm')
        self.assertEqual(result['coordinate_system'], 'patient_lps')
        self.assertFalse(result['source_mutation'])
        self.assertEqual(result['whole_surface_hausdorff'], 'not_computed')
        self.assertTrue(1 <= result['candidate_to_mask']['sample_count'] <= min(len(self.faces), 128))
        self.assertGreater(result['candidate_to_mask']['sampled_triangle_fraction'], 0)
        self.assertFalse(self.mask.flags.writeable)
        self.assertFalse(self.vertices.flags.writeable)
        self.assertFalse(self.faces.flags.writeable)

    def test_candidate_translation_is_measured_in_physical_mm_bidirectionally(self):
        moved = self.vertices + np.array([10.0, 0.0, 0.0])
        result = sampled_bidirectional_mask_surface_mm(self.mask, self.affine, moved, self.faces, sample_limit=128)
        self.assertGreater(result['candidate_to_mask']['max_sampled_mm'], 1.0)
        self.assertGreater(result['mask_to_candidate']['max_sampled_mm'], 1.0)
        self.assertGreater(result['symmetric_max_sampled_mm'], 1.0)

    def test_exact_triangle_interior_distance_is_not_vertex_distance(self):
        tri = np.array([[[0., 0., 0.], [10., 0., 0.], [0., 10., 0.]]])
        self.assertAlmostEqual(float(_point_to_triangles_squared(np.array([2., 2., 3.]), tri)[0]), 9.)
        self.assertAlmostEqual(float(_point_to_triangles_squared(np.array([2., 2., 0.]), tri)[0]), 0.)
        self.assertAlmostEqual(float(_point_to_triangles_squared(np.array([7., 7., 0.]), tri)[0]), 8.)

    def test_centroid_tree_pruning_agrees_with_exhaustive_triangle_search(self):
        rng = np.random.default_rng(6301)
        # Many nondegenerate target faces with very different spatial extents,
        # including some long faces whose centroid is far from the closest point.
        target = rng.normal(size=(100, 3, 3)) * rng.uniform(0.5, 7.0, size=(100, 1, 1))
        source = rng.normal(size=(30, 3, 3)) * 3.0
        source_area = np.linalg.norm(
            np.cross(source[:, 1] - source[:, 0], source[:, 2] - source[:, 0]), axis=1
        )
        result = _sampled_to_surface(source, source_area, target, sample_limit=30)
        exhaustive = []
        for point in source.mean(axis=1):
            exhaustive.append(float(np.sqrt(np.min(_point_to_triangles_squared(point, target)))))
        self.assertAlmostEqual(result['mean_mm'], float(np.mean(exhaustive)), places=10)
        self.assertAlmostEqual(result['max_sampled_mm'], max(exhaustive), places=10)
        self.assertEqual(result['sampled_triangle_fraction'], 1.0)

    def test_true_mask_volume_edge_uses_virtual_exterior(self):
        mask = np.zeros((3, 3, 3), dtype=bool)
        mask[0, 1, 1] = True
        v, f = self.reference(mask, self.affine)
        result = sampled_bidirectional_mask_surface_mm(mask, self.affine, v, f, sample_limit=64)
        self.assertLess(result['symmetric_max_sampled_mm'], 1e-10)

    def test_sample_coverage_is_explicit_and_not_hausdorff(self):
        r = sampled_bidirectional_mask_surface_mm(self.mask, self.affine, self.vertices, self.faces, sample_limit=7)
        self.assertLessEqual(r['candidate_to_mask']['sample_count'], 7)
        self.assertLess(r['candidate_to_mask']['sampled_triangle_fraction'], 1.)
        self.assertEqual(r['trilinear_implicit_interface_distance'], 'not_computed')

    def test_bad_mesh_and_wrong_coordinate_contract_fail_closed(self):
        bad = self.vertices.copy(); bad[0, 0] = np.nan
        for vertices, faces, affine, samples in (
            (bad, self.faces, self.affine, 4),
            (self.vertices, np.array([[-1, 1, 2]]), self.affine, 4),
            (self.vertices, np.array([[0, 1, 99999]]), self.affine, 4),
            (self.vertices, self.faces[:, :2], self.affine, 4),
            (self.vertices, self.faces, np.zeros((4, 4)), 4),
            (self.vertices, self.faces, self.affine, 0),
            (self.vertices, self.faces, self.affine, 1025),
        ):
            with self.subTest(samples=samples, shape=np.shape(faces)):
                with self.assertRaises(ValueError):
                    sampled_bidirectional_mask_surface_mm(self.mask, affine, vertices, faces, sample_limit=samples)
        with self.assertRaises(ValueError):
            sampled_bidirectional_mask_surface_mm(np.zeros((3, 3, 3), bool), self.affine, self.vertices, self.faces)


if __name__ == '__main__':
    unittest.main()
