"""Experimental B1B1 face association for *presentation* of an immutable CT isosurface.

This module does not identify anatomy, select a patient, remove geometry, change
provenance, or write to the canonical source. Every input triangle receives one
presentation label: 0 = unresolved, 1/2 = one of the two largest disjoint
broad-support regions. The full original index buffer remains authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np
from scipy.ndimage import label


@dataclass(frozen=True, slots=True)
class DirectCtTrianglePartition:
    triangle_regions: np.ndarray
    face_counts: tuple[int, int, int]
    body_region_count: int
    body_rank_voxels: tuple[int, int]
    classification: str = "not_anatomical"

    @property
    def has_multiple_ranked_regions(self) -> bool:
        return self.body_region_count >= 2 and self.face_counts[1] > 0 and self.face_counts[2] > 0


def partition_direct_ct_triangles(
    *,
    volume: np.ndarray,
    vertices: np.ndarray,
    faces: np.ndarray,
    isovalue: float,
    body_threshold: float = -500.0,
) -> DirectCtTrianglePartition:
    """Associate *existing* mesh faces with distinct broad-support regions.

    This conservative mapping does not reconstruct, reindex or drop triangles.
    Each isosurface vertex is checked against its adjacent array-index voxel
    corners. If its high-HU corners map to two regions, or no qualifying corner,
    it remains unresolved (0). A triangle is labeled only if all three of its
    vertices unambiguously map to the same ranked region. Other triangles are
    explicitly retained as unresolved for subsequent presentation logic.
    """
    if (
        not isinstance(volume, np.ndarray)
        or volume.ndim != 3
        or volume.dtype != np.float32
        or not all(dim >= 2 for dim in volume.shape)
        or not isinstance(vertices, np.ndarray)
        or vertices.ndim != 2
        or vertices.shape[1] != 3
        or len(vertices) == 0
        or not np.all(np.isfinite(vertices))
        or not isinstance(faces, np.ndarray)
        or faces.ndim != 2
        or faces.shape[1] != 3
        or len(faces) == 0
        or not np.issubdtype(faces.dtype, np.integer)
        or not isfinite(float(isovalue))
        or not isfinite(float(body_threshold))
        or not body_threshold < isovalue
        or not np.isfinite(np.float32(isovalue))
        or not np.isfinite(np.float32(body_threshold))
    ):
        raise ValueError("Direct-CT triangle region input is invalid")
    if (
        np.any(vertices < -1e-5)
        or np.any(vertices > np.asarray(volume.shape, dtype=np.float64) - 1 + 1e-5)
        or np.any(faces < 0)
        or np.any(faces >= len(vertices))
    ):
        raise ValueError("Direct-CT triangle region geometry is out of bounds")

    support_labels, support_count = label(
        volume >= np.float32(body_threshold),
        structure=np.ones((3, 3, 3), dtype=np.uint8),
    )
    counts = np.bincount(support_labels.ravel())
    ids = np.arange(1, support_count + 1, dtype=np.int64)
    order = ids[np.lexsort((ids, -counts[1:]))]
    # Do not classify any region as patient, table, anatomy, or artifact.
    ranks = np.zeros(support_count + 1, dtype=np.uint8)
    rank_voxels = [0, 0]
    for rank, component in enumerate(order[:2], start=1):
        ranks[int(component)] = rank
        rank_voxels[rank - 1] = int(counts[int(component)])

    # Marching-cubes vertices lie on grid edges. The up-to-eight neighboring
    # grid corners cover the edge's high-intensity endpoint(s), even at an
    # integer-coordinate crossing. Disagreement is never resolved by size.
    clipped = np.clip(vertices, 0, np.asarray(volume.shape) - 1)
    lower = np.floor(clipped).astype(np.int64)
    upper = np.ceil(clipped).astype(np.int64)
    vertex_ranks = np.zeros(len(vertices), dtype=np.uint8)
    conflicted = np.zeros(len(vertices), dtype=np.bool_)
    for z in (0, 1):
        iz = lower[:, 0] if z == 0 else upper[:, 0]
        for y in (0, 1):
            iy = lower[:, 1] if y == 0 else upper[:, 1]
            for x in (0, 1):
                ix = lower[:, 2] if x == 0 else upper[:, 2]
                high = volume[iz, iy, ix] >= np.float32(isovalue)
                candidates = np.where(high, ranks[support_labels[iz, iy, ix]], 0)
                conflicted |= (candidates != 0) & (vertex_ranks != 0) & (vertex_ranks != candidates)
                vertex_ranks = np.where((vertex_ranks == 0) & (candidates != 0), candidates, vertex_ranks)
    vertex_ranks[conflicted] = 0

    corners = vertex_ranks[faces]
    consistent = (corners[:, 0] != 0) & (corners[:, 0] == corners[:, 1]) & (corners[:, 1] == corners[:, 2])
    face_ranks = np.where(consistent, corners[:, 0], 0).astype(np.uint8)
    face_counts = tuple(int(item) for item in np.bincount(face_ranks, minlength=3)[:3])
    return DirectCtTrianglePartition(
        triangle_regions=face_ranks,
        face_counts=face_counts,  # type: ignore[arg-type]
        body_region_count=int(support_count),
        body_rank_voxels=(rank_voxels[0], rank_voxels[1]),
    )
