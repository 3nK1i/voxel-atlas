"""Phase 6G2: bounded, read-only three-plane MPR *geometric* contour agreement.

Compares intersections of a candidate Patient-LPS mesh and the selected-label
padded-0.5 polygonal reference surface on the same three LPS MPR slice planes.
This is sampled contour agreement in millimeters, NOT pixel-overlay equivalence,
clinical validation, anatomical ground truth, or whole-surface Hausdorff.
"""
from __future__ import annotations

import numpy as np

from .segmentation_surface_distances import (
    MAX_6G1_MASK_VOXELS, MAX_CANDIDATE_FACES, MAX_REFERENCE_FACES,
    MAX_MESH_VERTICES, _affine, _validated_mesh,
)

_PLANES = {
    'axial': ('z', 'x', 'y', False),
    'coronal': ('y', 'x', 'z', True),
    'sagittal': ('x', 'y', 'z', True),
}
_AXES = {'x': 0, 'y': 1, 'z': 2}
MAX_INTERSECTED_FACES_PER_PLANE = 30_000
MAX_SEGMENTS_PER_CONTOUR = 30_000
MAX_SAMPLES_PER_CONTOUR = 256
MAX_SEGMENT_TESTS_PER_DIRECTION = 5_000_000
_PLANE_EPS_MM = 1e-8


def _finite_pair(value, *, increasing=False):
    try:
        pair = np.asarray(value, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid MPR coordinate interval') from exc
    if pair.shape != (2,) or not np.all(np.isfinite(pair)) or (increasing and pair[1] < pair[0]):
        raise ValueError('Invalid MPR coordinate interval')
    return pair


def _slice_info(name, descriptor, index):
    """Use the actual Phase 3D MPR descriptor's world-axis and pixel conventions."""
    n, h, v, reverse = _PLANES[name]
    if not isinstance(descriptor, dict) or isinstance(index, bool) or not isinstance(index, int):
        raise ValueError('Invalid MPR descriptor or selected slice index')
    if (descriptor.get('plane') != name or descriptor.get('normal_axis') != n
            or descriptor.get('horizontal_axis') != h or descriptor.get('vertical_axis') != v
            or descriptor.get('vertical_reverse') is not reverse):
        raise ValueError('MPR descriptor axes/orientation do not match the named plane')
    count, width, height = (descriptor.get(key) for key in ('slice_count', 'image_width', 'image_height'))
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 1 or x > 1024
           for x in (count, width, height)) or not 0 <= index < count:
        raise ValueError('MPR slice/dimension budget or index invalid')
    position_range = _finite_pair(descriptor.get('position_range_mm'), increasing=True)
    horizontal = _finite_pair(descriptor.get('horizontal_range_mm'), increasing=True)
    vertical = _finite_pair(descriptor.get('vertical_range_mm'), increasing=True)
    if (width > 1 and horizontal[1] <= horizontal[0]) or (height > 1 and vertical[1] <= vertical[0]):
        raise ValueError('MPR pixel coordinate range is invalid')
    try:
        spacing = float(descriptor['slice_spacing_mm'])
        pixels = np.asarray(descriptor['pixel_spacing_mm'], dtype=np.float64)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError('Invalid MPR spacing') from exc
    if (not np.isfinite(spacing) or spacing < 0 or pixels.shape != (2,)
            or not np.all(np.isfinite(pixels)) or np.any(pixels < 0)):
        raise ValueError('Invalid MPR spacing')
    if count > 1 and (spacing <= 0 or not np.isclose(
            position_range[0] + (count - 1) * spacing, position_range[1], atol=1e-5, rtol=1e-6)):
        raise ValueError('Inconsistent MPR slice coordinate interval')
    for size, bounds, physical_spacing in ((width, horizontal, pixels[1]), (height, vertical, pixels[0])):
        if size > 1 and (physical_spacing <= 0 or not np.isclose(
                (bounds[1] - bounds[0]) / (size - 1), physical_spacing, atol=1e-5, rtol=1e-6)):
            raise ValueError('Inconsistent MPR pixel spacing')
    return (_AXES[n], _AXES[h], _AXES[v], float(position_range[0] + spacing * index),
            horizontal, vertical, reverse)


def _intersect_triangles(triangles, axis, position, horizontal_axis, vertical_axis):
    """Extract nonzero mesh/plane intersection segments in physical LPS millimeters.

    A fully coplanar face is ambiguous as an interior contour: fail closed, rather
    than silently count its triangulation diagonals as anatomical boundaries.
    """
    signed = triangles[:, :, axis] - position
    touched = np.flatnonzero((np.min(signed, axis=1) <= _PLANE_EPS_MM)
                                & (np.max(signed, axis=1) >= -_PLANE_EPS_MM))
    if len(touched) > MAX_INTERSECTED_FACES_PER_PLANE:
        raise ValueError('MPR plane intersected-face analysis budget exceeded')
    result = []
    for triangle, delta in zip(triangles[touched], signed[touched]):
        if np.all(np.abs(delta) <= _PLANE_EPS_MM):
            raise ValueError('Coplanar mesh face: ambiguous MPR contour')
        points = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            da, db = float(delta[a]), float(delta[b])
            za, zb = abs(da) <= _PLANE_EPS_MM, abs(db) <= _PLANE_EPS_MM
            if za:
                points.append(triangle[a])
            if zb:
                points.append(triangle[b])
            if not za and not zb and ((da < 0) != (db < 0)):
                points.append(triangle[a] + (da / (da - db)) * (triangle[b] - triangle[a]))
        unique = []
        for point in points:
            if not any(float(np.linalg.norm(point - other)) <= _PLANE_EPS_MM for other in unique):
                unique.append(point)
        if len(unique) < 2:
            continue  # Triangle touches plane at a vertex, no contour segment.
        coords = np.asarray(unique, dtype=np.float64)[:, [horizontal_axis, vertical_axis]]
        difference = coords[:, None, :] - coords[None, :, :]
        distance_sq = np.einsum('ijk,ijk->ij', difference, difference)
        i, j = np.unravel_index(np.argmax(distance_sq), distance_sq.shape)
        if distance_sq[i, j] > _PLANE_EPS_MM ** 2:
            result.append(np.stack((coords[i], coords[j])))
        if len(result) > MAX_SEGMENTS_PER_CONTOUR:
            raise ValueError('MPR contour segment budget exceeded')
    if not result:
        return np.empty((0, 2, 2), dtype=np.float64)
    return np.stack(result)


def _sample_segments(segments, limit):
    length = np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1)
    if len(segments) <= limit:
        chosen = np.arange(len(segments), dtype=np.intp)
    else:
        cumulative = np.cumsum(length)
        positions = ((np.arange(limit, dtype=np.float64) + 0.5) / limit) * cumulative[-1]
        chosen = np.unique(np.searchsorted(cumulative, positions, side='left'))
    return segments[chosen].mean(axis=1), int(len(chosen))


def _point_to_segments_mm(points, targets):
    total_tests = len(points) * len(targets)
    if total_tests > MAX_SEGMENT_TESTS_PER_DIRECTION:
        raise ValueError('MPR sampled contour exact-search budget exceeded')
    distances = np.full(len(points), np.inf, dtype=np.float64)
    # Blocked exact point-to-*segment* distances, including segment interiors.
    for start in range(0, len(targets), 256):
        block = targets[start:start + 256]
        a = block[:, 0]
        d = block[:, 1] - a
        t = np.clip(np.sum((points[:, None, :] - a) * d, axis=2)
                    / np.sum(d * d, axis=1)[None, :], 0, 1)
        difference = points[:, None, :] - (a + t[:, :, None] * d)
        distances = np.minimum(distances, np.sqrt(np.min(np.sum(difference * difference, axis=2), axis=1)))
    return distances, total_tests


def _direction(source, target, limit):
    points, sampled = _sample_segments(source, limit)
    distances, tests = _point_to_segments_mm(points, target)
    return {
        'source_segment_count': int(len(source)),
        'sample_count': sampled,
        'sampled_segment_fraction': float(sampled / len(source)),
        'mean_mm': float(np.mean(distances)),
        'p95_mm': float(np.percentile(distances, 95)),
        'max_sampled_mm': float(np.max(distances)),
        'exact_target_segment_distance_per_sample': True,
        'segment_distance_evaluations': tests,
    }


def three_plane_mpr_surface_agreement_mm(mask, array_index_to_patient_lps,
                                          candidate_positions_lps, candidate_faces,
                                          mpr_descriptors, slice_indices, *, sample_limit=128):
    """Compare candidate/reference contour geometry at selected axial/coronal/sagittal MPR slices.

    Uses the *same* LPS planes and horizontal/vertical ranges from existing MPR
    descriptors. The reference is the selected-label padded 0.5 polygonal surface,
    not independent anatomical truth or the nearest-neighbor raster overlay.
    Caller must bind actual source artifacts, label, study, and mesh provenance.
    """
    from skimage.measure import marching_cubes

    if isinstance(sample_limit, bool) or not isinstance(sample_limit, int) or not 1 <= sample_limit <= MAX_SAMPLES_PER_CONTOUR:
        raise ValueError('Invalid MPR contour sample budget')
    source = np.asarray(mask)
    if (source.ndim != 3 or source.dtype != np.dtype('bool') or not all(source.shape)
            or source.size > MAX_6G1_MASK_VOXELS or not np.any(source)):
        raise ValueError('Expected nonempty bounded selected-label 3D mask')
    affine = _affine(array_index_to_patient_lps)
    if (not isinstance(mpr_descriptors, dict) or set(mpr_descriptors) != set(_PLANES)
            or not isinstance(slice_indices, dict) or set(slice_indices) != set(_PLANES)):
        raise ValueError('All three MPR planes and selected indices are required')
    plane_data = {name: _slice_info(name, mpr_descriptors[name], slice_indices[name])
                  for name in _PLANES}
    _, _, candidate_tri, _ = _validated_mesh(candidate_positions_lps, candidate_faces,
                                            max_faces=MAX_CANDIDATE_FACES)
    ref_index, ref_faces, _, _ = marching_cubes(
        np.pad(source.astype(np.uint8), 1), level=0.5,
        gradient_direction='descent', allow_degenerate=False, method='lewiner',
    )
    if len(ref_index) > MAX_MESH_VERTICES or len(ref_faces) > MAX_REFERENCE_FACES:
        raise ValueError('MPR reference polygonal-interface budget exceeded')
    reference_lps = (np.asarray(ref_index, dtype=np.float64) - 1.0) @ affine[:3, :3].T + affine[:3, 3]
    _, _, reference_tri, _ = _validated_mesh(reference_lps, ref_faces, max_faces=MAX_REFERENCE_FACES)

    reports = {}
    for name, (n, h, v, position, horizontal, vertical, reverse) in plane_data.items():
        candidate = _intersect_triangles(candidate_tri, n, position, h, v)
        reference = _intersect_triangles(reference_tri, n, position, h, v)
        report = {
            'slice_index_zero_based': slice_indices[name],
            'plane_position_lps_mm': position,
            'reference_segment_count': int(len(reference)),
            'candidate_segment_count': int(len(candidate)),
            'mpr_vertical_reversed': reverse,
            'horizontal_lps_range_mm': horizontal.tolist(),
            'vertical_lps_range_mm': vertical.tolist(),
        }
        if not len(reference) and not len(candidate):
            report.update(status='no_contours_at_selected_slice', qualified=False)
        elif not len(reference) or not len(candidate):
            report.update(status='missing_contour_on_one_side', qualified=False)
        else:
            ref_points = reference.reshape(-1, 2)
            cand_points = candidate.reshape(-1, 2)
            def outside(points):
                return int(np.count_nonzero((points[:, 0] < horizontal[0] - _PLANE_EPS_MM)
                       | (points[:, 0] > horizontal[1] + _PLANE_EPS_MM)
                       | (points[:, 1] < vertical[0] - _PLANE_EPS_MM)
                       | (points[:, 1] > vertical[1] + _PLANE_EPS_MM)))
            report.update(
                status='sampled_contour_agreement',
                qualified=False,  # This is geometric evidence, never clinical qualification.
                candidate_out_of_mpr_field_endpoints=outside(cand_points),
                reference_out_of_mpr_field_endpoints=outside(ref_points),
                candidate_to_reference=_direction(candidate, reference, sample_limit),
                reference_to_candidate=_direction(reference, candidate, sample_limit),
            )
            report['symmetric_max_sampled_mm'] = max(
                report['candidate_to_reference']['max_sampled_mm'],
                report['reference_to_candidate']['max_sampled_mm'],
            )
        reports[name] = report
    return {
        'metric': 'three_plane_sampled_polygonal_mask_mesh_contour_agreement',
        'units': 'mm', 'coordinate_system': 'patient_lps',
        'reference': 'padded_0.5_mask_marching_cubes_intersections',
        'planes': reports,
        'all_planes_have_contours': all(p['status'] == 'sampled_contour_agreement' for p in reports.values()),
        'raster_mpr_overlay_equivalence': 'not_computed',
        'whole_contour_hausdorff': 'not_computed',
        'clinical_validation': 'not_claimed', 'provenance_binding': 'caller_required',
        'source_mutation': False,
    }
