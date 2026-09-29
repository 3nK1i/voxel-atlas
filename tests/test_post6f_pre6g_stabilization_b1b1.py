"""B1B1: qualify complete, reversible region-to-face association on synthetic CT only."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
from skimage.measure import marching_cubes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


class DirectCtRegionFaceContractTests(unittest.TestCase):
    @staticmethod
    def fixture():
        ct = np.full((18, 26, 26), -1000, dtype=np.float32)
        # Broad larger region with two separated high-HU structures.
        ct[2:16, 2:14, 2:14] = 0
        ct[4:13, 4:10, 4:10] = 650
        ct[12:14, 10:12, 10:12] = 650
        # Distinct broad-support region with a thin high-density sheet.
        ct[3:15, 19:23, 2:24] = 0
        ct[4:14, 20:22, 4:22] = 650
        return ct

    def test_complete_mesh_partition_preserves_original_geometry_and_source(self):
        from voxelatlas.direct_ct_surface_regions import partition_direct_ct_triangles
        ct = self.fixture()
        original = ct.copy()
        vertices, faces, _, _ = marching_cubes(ct, level=300, allow_degenerate=False)
        saved_faces = faces.copy()
        result = partition_direct_ct_triangles(
            volume=ct, vertices=vertices, faces=faces, isovalue=300, body_threshold=-500,
        )
        self.assertTrue(np.array_equal(ct, original))
        self.assertTrue(np.array_equal(faces, saved_faces))
        self.assertEqual(result.triangle_regions.dtype, np.uint8)
        self.assertEqual(len(result.triangle_regions), len(faces))
        self.assertEqual(sum(result.face_counts), len(faces))
        self.assertEqual(result.body_region_count, 2)
        self.assertGreater(result.face_counts[1], 0)
        self.assertGreater(result.face_counts[2], 0)
        self.assertTrue(set(np.unique(result.triangle_regions)) <= {0, 1, 2})
        self.assertEqual(result.classification, 'not_anatomical')

    def test_region_face_sets_cover_full_index_buffer_without_reindexing(self):
        from voxelatlas.direct_ct_surface_regions import partition_direct_ct_triangles
        ct = self.fixture()
        vertices, faces, _, _ = marching_cubes(ct, level=300, allow_degenerate=False)
        original_vertices = vertices.copy()
        result = partition_direct_ct_triangles(
            volume=ct, vertices=vertices, faces=faces, isovalue=300, body_threshold=-500,
        )
        indices = [np.flatnonzero(result.triangle_regions == label) for label in (0, 1, 2)]
        self.assertEqual(sorted(np.concatenate(indices).tolist()), list(range(len(faces))))
        self.assertTrue(np.array_equal(faces, np.vstack([faces[idx] for idx in indices])[
            np.argsort(np.concatenate(indices))
        ]))
        self.assertTrue(np.array_equal(vertices, original_vertices))

    def test_unassociated_faces_are_explicitly_preserved_not_discarded(self):
        from voxelatlas.direct_ct_surface_regions import partition_direct_ct_triangles
        ct = self.fixture()
        vertices, faces, _, _ = marching_cubes(ct, level=300, allow_degenerate=False)
        # A structurally valid triangle crossing two distinct regions is ambiguous.
        first = partition_direct_ct_triangles(
            volume=ct, vertices=vertices, faces=faces, isovalue=300, body_threshold=-500,
        )
        i = int(np.flatnonzero(first.triangle_regions == 1)[0])
        j = int(np.flatnonzero(first.triangle_regions == 2)[0])
        cross_region = faces[[i]].copy()
        cross_region[0, 2] = faces[j, 2]
        mixed = partition_direct_ct_triangles(
            volume=ct, vertices=vertices, faces=cross_region, isovalue=300, body_threshold=-500,
        )
        self.assertEqual(mixed.face_counts, (1, 0, 0))
        self.assertEqual(mixed.triangle_regions.tolist(), [0])

    def test_one_broad_region_does_not_claim_patient_or_offer_support_isolation(self):
        from voxelatlas.direct_ct_surface_regions import partition_direct_ct_triangles
        ct = np.full((8, 8, 8), -1000, dtype=np.float32)
        ct[2:6, 2:6, 2:6] = 800
        vertices, faces, _, _ = marching_cubes(ct, level=300, allow_degenerate=False)
        result = partition_direct_ct_triangles(
            volume=ct, vertices=vertices, faces=faces, isovalue=300, body_threshold=-500,
        )
        self.assertEqual(result.body_region_count, 1)
        self.assertFalse(result.has_multiple_ranked_regions)
        self.assertEqual(result.face_counts[2], 0)
        self.assertNotIn('patient', result.classification)

    def test_invalid_geometry_or_threshold_fails_closed(self):
        from voxelatlas.direct_ct_surface_regions import partition_direct_ct_triangles
        ct = self.fixture()
        vertices, faces, _, _ = marching_cubes(ct, level=300, allow_degenerate=False)
        for bad in ((300, 300), (float('nan'), -500), (300, 301)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                partition_direct_ct_triangles(volume=ct, vertices=vertices, faces=faces,
                                              isovalue=bad[0], body_threshold=bad[1])
        with self.assertRaises(ValueError):
            partition_direct_ct_triangles(volume=ct, vertices=vertices,
                                          faces=np.array([[0, 1, 9999999]]),
                                          isovalue=300, body_threshold=-500)


if __name__ == '__main__':
    unittest.main()
