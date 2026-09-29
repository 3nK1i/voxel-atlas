"""Synthetic tests only: no patient artifacts or clinical thresholds."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from voxelatlas.segmentation_surface_fidelity import interface_residual_mm  # noqa: E402


class Phase6G0InterfaceResidualTests(unittest.TestCase):
    def setUp(self):
        self.mask = np.zeros((4, 4, 4), dtype=bool)
        self.mask[1:3, 1:3, 1:3] = True
        self.mask.setflags(write=False)
        self.snapshot = self.mask.copy()
        self.affine = np.eye(4, dtype=float)
        self.affine[:3, :3] = np.array([[0, 0, 2], [0, 3, 0], [4, 0, 0]])
        self.affine[:3, 3] = [10, 20, 30]

    def lps(self, indices):
        indices = np.asarray(indices, dtype=float)
        return indices @ self.affine[:3, :3].T + self.affine[:3, 3]

    def test_exact_half_voxel_boundary_is_zero_mm_in_anisotropic_lps(self):
        points = self.lps([[0.5, 1.0, 1.0], [2.5, 1.0, 1.0]])
        result = interface_residual_mm(self.mask, self.affine, points)
        self.assertEqual(result['metric'], 'first_order_trilinear_interface_residual_mm')
        self.assertEqual(result['sample_count'], 2)
        self.assertEqual(result['max_mm'], 0.0)
        self.assertEqual(result['undefined_gradient_count'], 0)
        self.assertEqual(result['coordinate_system'], 'patient_lps')
        self.assertTrue(np.array_equal(self.mask, self.snapshot))
        self.assertFalse(self.mask.flags.writeable)

    def test_axis_aligned_offset_reports_physical_mm_not_voxels(self):
        # Index-axis 0 is 4 mm per voxel; 0.25 voxels -> 1 mm.
        result = interface_residual_mm(self.mask, self.affine, self.lps([[0.75, 1, 1]]))
        self.assertAlmostEqual(result['mean_mm'], 1.0)
        self.assertAlmostEqual(result['max_mm'], 1.0)

    def test_oblique_affine_and_translation_do_not_break_zero_boundary(self):
        affine = self.affine.copy()
        affine[:3, :3] = [[1.0, 0.2, -0.3], [0.1, 2.0, 0.4], [0.0, 0.2, 3.0]]
        location = np.array([[0.5, 1.0, 1.0]]) @ affine[:3, :3].T + affine[:3, 3]
        result = interface_residual_mm(self.mask, affine, location)
        self.assertLess(result['max_mm'], 1e-10)

    def test_volume_edge_half_voxel_interface(self):
        mask = np.zeros((3, 3, 3), dtype=bool)
        mask[0, 1, 1] = True
        result = interface_residual_mm(mask, self.affine, self.lps([[-0.5, 1.0, 1.0]]))
        self.assertAlmostEqual(result['max_mm'], 0.0)
        self.assertTrue(np.array_equal(self.mask, self.snapshot))

    def test_zero_gradient_is_reported_not_falsely_zeroed(self):
        result = interface_residual_mm(self.mask, self.affine, self.lps([[1.5, 1.5, 1.5]]))
        self.assertEqual(result['undefined_gradient_count'], 1)
        self.assertIsNone(result['mean_mm'])
        self.assertIsNone(result['max_mm'])

    def test_rejects_nonfinite_out_of_bounds_and_invalid_affine(self):
        with self.assertRaises(ValueError):
            interface_residual_mm(self.mask, self.affine, [[float('nan'), 0, 0]])
        with self.assertRaises(ValueError):
            interface_residual_mm(self.mask, self.affine, self.lps([[10, 1, 1]]))
        with self.assertRaises(ValueError):
            interface_residual_mm(self.mask, np.zeros((4, 4)), self.lps([[0.5, 1, 1]]))
        with self.assertRaises(ValueError):
            interface_residual_mm(np.zeros((4, 4, 4), dtype=np.uint16), self.affine, self.lps([[0.5, 1, 1]]))


if __name__ == '__main__':
    unittest.main()
