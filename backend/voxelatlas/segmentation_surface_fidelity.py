"""Phase 6G0: read-only, non-clinical first-order mask-interface residual.

This is NOT a shortest distance from a mesh to a mask boundary or a clinical
accuracy score. A later 6G step must add bidirectional geometric distances and
MPR sampling before reporting real-study fidelity.
"""
from __future__ import annotations

import numpy as np

MAX_MASK_VOXELS = 64_000_000
MAX_SAMPLES = 1_500_000


def interface_residual_mm(mask: np.ndarray, array_index_to_patient_lps: np.ndarray,
                          positions_lps: np.ndarray) -> dict[str, object]:
    """Estimate local |occupancy-0.5| / physical occupancy gradient at sample points.

    The binary occupancy is trilinearly interpolated in index space with an
    explicit zero-valued exterior at the acquired-volume boundary. Only a
    binary mask and LPS points are accepted. This routine neither writes nor
    modifies the mask, and does not interpret anatomy or claim surface accuracy.

    The residual is *first-order*, not an exact nearest-interface distance; it
    is undefined where the physical interpolant gradient is zero. Never use it
    alone to qualify a patient's reconstruction or compare clinical models.
    """
    source = np.asarray(mask)
    if source.ndim != 3 or source.dtype != np.dtype('bool') or not all(source.shape):
        raise ValueError('Expected a nonempty 3D boolean mask')
    if source.size > MAX_MASK_VOXELS:
        raise ValueError('Mask exceeds the bounded analysis budget')
    affine = np.asarray(array_index_to_patient_lps, dtype=np.float64)
    if (affine.shape != (4, 4) or not np.all(np.isfinite(affine))
            or not np.allclose(affine[3], (0, 0, 0, 1), rtol=0, atol=1e-8)):
        raise ValueError('Invalid Patient-LPS affine')
    linear = affine[:3, :3]
    if abs(float(np.linalg.det(linear))) <= 1e-12:
        raise ValueError('Singular Patient-LPS affine')
    inverse = np.linalg.inv(linear)
    points = np.asarray(positions_lps, dtype=np.float64)
    if (points.ndim != 2 or points.shape[1] != 3 or not 0 < len(points) <= MAX_SAMPLES
            or not np.all(np.isfinite(points))):
        raise ValueError('Invalid bounded Patient-LPS sample array')
    index = (points - affine[:3, 3]) @ inverse.T
    bounds = np.asarray(source.shape, dtype=np.float64) - 0.5
    if np.any(index < -0.5 - 1e-6) or np.any(index > bounds + 1e-6):
        raise ValueError('Sample lies outside the acquired mask half-voxel domain')
    index = np.clip(index, -0.5, bounds)

    # Index 0 in the padded field is virtual exterior at original index -1.
    field = np.pad(source, 1, mode='constant', constant_values=False)
    q = index + 1.0
    lo = np.floor(q).astype(np.intp)
    t = q - lo
    value = np.zeros(len(points), dtype=np.float64)
    gradient_index = np.zeros((len(points), 3), dtype=np.float64)
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                dx, dy, dz = a, b, c
                v = field[lo[:, 0] + dx, lo[:, 1] + dy, lo[:, 2] + dz]
                w = [(t[:, axis] if bit else 1.0 - t[:, axis])
                     for axis, bit in enumerate((dx, dy, dz))]
                value += v * w[0] * w[1] * w[2]
                for axis, bit in enumerate((dx, dy, dz)):
                    gradient_index[:, axis] += (
                        v * (1 if bit else -1)
                        * w[(axis + 1) % 3] * w[(axis + 2) % 3]
                    )
    # Row-vector form of inverse-transpose gradient transform: ∇_LPS = ∇_idx @ A^-1.
    gradient_lps = gradient_index @ inverse
    length = np.linalg.norm(gradient_lps, axis=1)
    valid = length > 1e-12
    if np.any(~np.isfinite(length)):
        raise ValueError('Nonfinite physical interface gradient')
    residual = np.abs(value[valid] - 0.5) / length[valid]
    return {
        'metric': 'first_order_trilinear_interface_residual_mm',
        'coordinate_system': 'patient_lps',
        'units': 'mm',
        'sample_count': int(len(points)),
        'defined_count': int(valid.sum()),
        'undefined_gradient_count': int((~valid).sum()),
        'mean_mm': float(np.mean(residual)) if residual.size else None,
        'p95_mm': float(np.percentile(residual, 95)) if residual.size else None,
        'max_mm': float(np.max(residual)) if residual.size else None,
        'analysis_complete': bool(np.all(valid)),
        'clinical_validation': 'not_claimed',
        'distance_interpretation': 'first_order_local_proxy_not_shortest_boundary_distance',
    }
