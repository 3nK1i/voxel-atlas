"""Phase 6G1: bounded, read-only, sampled bidirectional polygonal-interface distances.

This module measures exact point-to-triangle distances for explicitly sampled points,
NOT exact whole-surface Hausdorff distances, signed distances, clinical accuracy,
or agreement with independent ground-truth anatomy. It neither reads study files nor
modifies the supplied label mask, mesh arrays, or canonical artifacts.
"""
from __future__ import annotations

import numpy as np

MAX_6G1_MASK_VOXELS = 8_000_000
MAX_MESH_VERTICES = 2_500_000

MAX_REFERENCE_FACES = 750_000
MAX_CANDIDATE_FACES = 750_000
MAX_SAMPLES_PER_DIRECTION = 1024
MAX_CANDIDATE_TRIANGLES_PER_QUERY = 100_000
MAX_TRIANGLE_TESTS_PER_DIRECTION = 5_000_000


def _affine(value: np.ndarray) -> np.ndarray:
    try:
        matrix = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid Patient-LPS affine') from exc
    if (matrix.shape != (4, 4) or not np.all(np.isfinite(matrix))
            or not np.allclose(matrix[3], (0, 0, 0, 1), atol=1e-8, rtol=0)
            or abs(float(np.linalg.det(matrix[:3, :3]))) <= 1e-12):
        raise ValueError('Invalid Patient-LPS affine')
    return matrix


def _validated_mesh(vertices: np.ndarray, faces: np.ndarray, *, max_faces: int):
    try:
        v = np.asarray(vertices, dtype=np.float64)
        raw_f = np.asarray(faces)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid mesh') from exc
    if (v.ndim != 2 or v.shape[1] != 3 or not 3 <= len(v)
            or len(v) > MAX_MESH_VERTICES or not np.all(np.isfinite(v)) or raw_f.ndim != 2 or raw_f.shape[1] != 3
            or not 0 < len(raw_f) <= max_faces or raw_f.dtype.kind not in 'iu'):
        raise ValueError('Invalid bounded Patient-LPS mesh')
    if np.any(raw_f < 0) or np.any(raw_f >= len(v)):
        raise ValueError('Mesh references invalid vertices')
    f = np.asarray(raw_f, dtype=np.int64)
    tri = v[f]
    area_twice = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    if not np.all(np.isfinite(area_twice)) or np.any(area_twice <= 1e-12):
        raise ValueError('Mesh contains degenerate triangles')
    return v, f, tri, area_twice


def _point_to_triangles_squared(point: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Exact Euclidean distance to each nondegenerate *filled triangle*, not vertices."""
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    u, v = b - a, c - a
    delta = point - a
    uu = np.einsum('ij,ij->i', u, u)
    uv = np.einsum('ij,ij->i', u, v)
    vv = np.einsum('ij,ij->i', v, v)
    du = np.einsum('ij,ij->i', delta, u)
    dv = np.einsum('ij,ij->i', delta, v)
    denom = uu * vv - uv * uv
    # Caller rejects degenerate triangles. Relative tolerance is only for
    # classifying a projected point lying on an edge; segment distances still win.
    s = (du * vv - dv * uv) / denom
    t = (dv * uu - du * uv) / denom
    projection = a + s[:, None] * u + t[:, None] * v
    inside = (s >= -1e-12) & (t >= -1e-12) & (s + t <= 1 + 1e-12)
    dplane = np.einsum('ij,ij->i', point - projection, point - projection)
    closest_sq = np.full(len(triangles), np.inf, dtype=np.float64)
    closest_sq[inside] = dplane[inside]
    for start, edge in ((a, b - a), (b, c - b), (c, a - c)):
        along = np.clip(
            np.einsum('ij,ij->i', point - start, edge)
            / np.einsum('ij,ij->i', edge, edge), 0.0, 1.0
        )
        offset = point - (start + along[:, None] * edge)
        closest_sq = np.minimum(closest_sq, np.einsum('ij,ij->i', offset, offset))
    return np.maximum(closest_sq, 0.0)


def _sample_triangle_interiors(triangles: np.ndarray, area_twice: np.ndarray,
                               sample_limit: int):
    """Deterministic face-area stratification: triangle centroids, never just vertices."""
    if isinstance(sample_limit, bool) or not isinstance(sample_limit, int) or not (1 <= sample_limit <= MAX_SAMPLES_PER_DIRECTION):
        raise ValueError('Invalid sample limit')
    n = len(triangles)
    if n <= sample_limit:
        selected = np.arange(n, dtype=np.intp)
    else:
        # Mid-quantile face selection is deterministic in source face order.
        # It is a sampling method, NOT exhaustive surface coverage; tiny faces
        # and even small disconnected components may be omitted.
        cumulative = np.cumsum(area_twice, dtype=np.float64)
        if not np.isfinite(cumulative[-1]) or cumulative[-1] <= 0:
            raise ValueError('Invalid mesh area')
        targets = ((np.arange(sample_limit, dtype=np.float64) + 0.5) / sample_limit) * cumulative[-1]
        selected = np.searchsorted(cumulative, targets, side='left')
        selected = np.unique(selected)
    return triangles[selected].mean(axis=1), int(len(selected)), n


def _sampled_to_surface(source_tri: np.ndarray, source_area: np.ndarray,
                        target_tri: np.ndarray, sample_limit: int) -> dict[str, object]:
    from scipy.spatial import cKDTree

    samples, sampled_faces, source_faces = _sample_triangle_interiors(source_tri, source_area, sample_limit)
    centroids = target_tri.mean(axis=1)
    radius = np.max(np.linalg.norm(target_tri - centroids[:, None, :], axis=2), axis=1)
    tree = cKDTree(centroids)
    maximum_radius = float(np.max(radius))
    distances = np.empty(len(samples), dtype=np.float64)
    triangle_tests = 0
    for i, point in enumerate(samples):
        # First get an upper bound from one genuine target triangle.
        _, seed_idx = tree.query(point, k=1)
        upper_sq = float(_point_to_triangles_squared(point, target_tri[int(seed_idx):int(seed_idx) + 1])[0])
        upper = float(np.sqrt(upper_sq))
        # For any triangle T: distance(point, T) >= distance(point, centroid(T)) - radius(T).
        # Therefore no discarded triangle can improve on the seed upper bound.
        ids = tree.query_ball_point(point, upper + maximum_radius + 1e-10)
        if len(ids) > MAX_CANDIDATE_TRIANGLES_PER_QUERY:
            raise ValueError('Exact triangle search exceeded per-query candidate budget')
        indices = np.asarray(ids, dtype=np.intp)
        center_dist = np.linalg.norm(centroids[indices] - point, axis=1)
        eligible = indices[center_dist <= (upper + radius[indices] + 1e-10)]
        triangle_tests += len(eligible)
        if triangle_tests > MAX_TRIANGLE_TESTS_PER_DIRECTION:
            raise ValueError('Exact triangle search exceeded direction budget')
        for block in np.array_split(eligible, max(1, (len(eligible) + 255) // 256)):
            if len(block):
                upper_sq = min(upper_sq, float(np.min(_point_to_triangles_squared(point, target_tri[block]))))
        distances[i] = np.sqrt(max(0.0, upper_sq))
    return {
        'sample_count': sampled_faces,
        'source_triangle_count': source_faces,
        'sampled_triangle_fraction': float(sampled_faces / source_faces),
        'sampling': 'deterministic_area_stratified_triangle_centroids',
        'mean_mm': float(np.mean(distances)),
        'p95_mm': float(np.percentile(distances, 95)),
        'max_sampled_mm': float(np.max(distances)),
        'exact_target_triangle_distance_for_each_sample': True,
        'triangle_distance_evaluations': triangle_tests,
    }


def sampled_bidirectional_mask_surface_mm(
    mask: np.ndarray,
    array_index_to_patient_lps: np.ndarray,
    candidate_positions_lps: np.ndarray,
    candidate_faces: np.ndarray,
    *,
    sample_limit: int = 512,
) -> dict[str, object]:
    """Compare candidate mesh against polygonal 0.5 marching-cubes mask interface.

    `mask` MUST be the full selected-label mask, or a tightly cropped ROI with
    its correctly translated ROI affine. Virtual zero exterior is introduced
    on all six ROI faces, matching the Phase 6A surface worker. The caller must
    bind the actual label-map artifact, label id and candidate mesh provenance
    externally; this pure helper does not authenticate patient artifacts.
    """
    from skimage.measure import marching_cubes

    if isinstance(sample_limit, bool) or not isinstance(sample_limit, int) or not (1 <= sample_limit <= MAX_SAMPLES_PER_DIRECTION):
        raise ValueError('Invalid sample limit')
    source = np.asarray(mask)
    if (source.ndim != 3 or source.dtype != np.dtype('bool') or not all(source.shape)
            or source.size > MAX_6G1_MASK_VOXELS or not np.any(source)):
        raise ValueError('Expected nonempty bounded 3D boolean selected-label mask')
    affine = _affine(array_index_to_patient_lps)
    _, _, candidate_tri, candidate_area = _validated_mesh(
        candidate_positions_lps, candidate_faces, max_faces=MAX_CANDIDATE_FACES
    )
    padded = np.pad(source.astype(np.uint8), 1, mode='constant', constant_values=0)
    ref_index, ref_faces, _, _ = marching_cubes(
        padded, level=0.5, spacing=(1.0, 1.0, 1.0),
        gradient_direction='descent', allow_degenerate=False, method='lewiner',
    )
    if len(ref_index) > MAX_MESH_VERTICES or len(ref_faces) > MAX_REFERENCE_FACES:
        raise ValueError('Polygonal mask interface exceeds analysis geometry budget')
    reference_lps = (np.asarray(ref_index, dtype=np.float64) - 1.0) @ affine[:3, :3].T + affine[:3, 3]
    _, _, reference_tri, reference_area = _validated_mesh(reference_lps, ref_faces, max_faces=MAX_REFERENCE_FACES)
    forward = _sampled_to_surface(candidate_tri, candidate_area, reference_tri, sample_limit)
    reverse = _sampled_to_surface(reference_tri, reference_area, candidate_tri, sample_limit)
    return {
        'metric': 'sampled_bidirectional_polygonal_mask_interface_to_mesh_mm',
        'units': 'mm',
        'coordinate_system': 'patient_lps',
        'mask_interface': 'padded_0.5_lewiner_marching_cubes_polygonal_surface',
        'candidate_to_mask': forward,
        'mask_to_candidate': reverse,
        'symmetric_max_sampled_mm': max(forward['max_sampled_mm'], reverse['max_sampled_mm']),
        'whole_surface_hausdorff': 'not_computed',
        'trilinear_implicit_interface_distance': 'not_computed',
        'clinical_validation': 'not_claimed',
        'source_mutation': False,
        'provenance_binding': 'caller_required',
    }
