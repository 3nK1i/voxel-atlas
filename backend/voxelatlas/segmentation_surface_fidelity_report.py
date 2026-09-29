"""Phase 6G3: opt-in, source-bound, sampled surface/MPR fidelity evidence.

This module does not change canonical artifacts or the running application. Its
caller must obtain a *validated* label-map descriptor and attest the latest
study/MPR descriptor using the existing services. It independently rehashes
the provided label artifact and both v2 surface payloads before analysis.
No metric here is an exhaustive geometric bound or medical accuracy score.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re

import numpy as np

from .segmentation_surface_distances import (
    MAX_6G1_MASK_VOXELS,
    _affine,
    sampled_bidirectional_mask_surface_mm,
)
from .segmentation_surface_fidelity import interface_residual_mm
from .segmentation_surface_mpr_agreement import (
    _slice_info,
    three_plane_mpr_surface_agreement_mm,
)
from .segmentation_surfaces import (
    ACCURATE_SURFACE_EXTRACTION,
    ACCURATE_SURFACE_MEDIA_TYPE,
    ACCURATE_SURFACE_QUALITY,
    REFINED_SURFACE_QUALITY,
    REFINED_SURFACE_REFINEMENT,
    _decode_v2_payload_geometry,
)

MAX_6G3_SOURCE_VOXELS = 64_000_000
MAX_6G3_ARTIFACT_BYTES = 160 * 1024 * 1024
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')


def _digest(path: Path) -> str:
    h = sha256()
    with path.open('rb') as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _digest_field(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError('Invalid source or surface SHA256')
    return value


def _source_snapshot(*, descriptor: dict, artifact: Path, study_id: str, label_id: int):
    if (not isinstance(descriptor, dict) or not isinstance(study_id, str) or not study_id
            or isinstance(label_id, bool) or not isinstance(label_id, int) or not (0 < label_id <= 65535)):
        raise ValueError('Invalid source study/label binding')
    map_id = descriptor.get('label_map_id')
    if (not isinstance(map_id, str) or re.fullmatch(r'map-[0-9a-f]{32}', map_id) is None
            or descriptor.get('source_study_id') != study_id
            or descriptor.get('state') != 'ready'
            or descriptor.get('coordinate_system') != 'patient_lps'
            or descriptor.get('length_units') != 'mm'
            or descriptor.get('representation') != 'label_map'
            or descriptor.get('artifact_format') != 'npy'
            or descriptor.get('dtype') != 'uint16'
            or descriptor.get('axis_order') != ['slice', 'row', 'column']):
        raise ValueError('Source label map descriptor is not the expected canonical snapshot')
    artifact_digest = _digest_field(descriptor.get('artifact_sha256'))
    identity_digest = _digest_field(descriptor.get('identity_sha256'))
    provenance_digest = _digest_field(descriptor.get('provenance_sha256'))
    volume_descriptor_digest = _digest_field(descriptor.get('source_volume_descriptor_sha256'))
    volume_artifact_digest = _digest_field(descriptor.get('source_volume_artifact_sha256'))
    shape = descriptor.get('shape')
    if (not isinstance(shape, (list, tuple)) or len(shape) != 3
            or any(isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= 4096) for v in shape)
            or int(np.prod(shape, dtype=np.int64)) > MAX_6G3_SOURCE_VOXELS):
        raise ValueError('Invalid or over-budget source volume shape')
    present = descriptor.get('present_labels')
    if not isinstance(present, (list, tuple)) or label_id not in present:
        raise ValueError('Requested label is not in the bound source label map')
    affine = _affine(descriptor.get('array_index_to_patient_lps'))
    path = Path(artifact)
    if path.is_symlink() or not path.is_file() or path.suffix != '.npy':
        raise ValueError('Source label artifact must be a regular NPY file')
    size = path.stat().st_size
    if (size <= 0 or size > MAX_6G3_ARTIFACT_BYTES or size != descriptor.get('artifact_bytes')
            or _digest(path) != artifact_digest):
        raise ValueError('Source label artifact hash/size does not match validated descriptor')
    try:
        labels = np.load(path, mmap_mode='r', allow_pickle=False)
    except (ValueError, OSError) as exc:
        raise ValueError('Source label artifact is unreadable') from exc
    if labels.shape != tuple(shape) or labels.dtype != np.dtype('uint16'):
        raise ValueError('Source label artifact array contract changed')
    selected = labels == label_id
    if not np.any(selected):
        raise ValueError('Requested source label is absent')
    axes = [np.flatnonzero(np.any(selected, axis=tuple(j for j in range(3) if j != axis)))
            for axis in range(3)]
    start = np.array([int(coords[0]) for coords in axes], dtype=np.int64)
    stop = np.array([int(coords[-1]) + 1 for coords in axes], dtype=np.int64)
    roi_shape = stop - start
    if int(np.prod(roi_shape, dtype=np.int64)) > MAX_6G1_MASK_VOXELS:
        raise ValueError('Selected label ROI exceeds the 6G1/6G2 analysis budget')
    region = np.array(selected[tuple(slice(int(a), int(b)) for a, b in zip(start, stop))],
                      dtype=bool, copy=True)
    region.setflags(write=False)
    roi_affine = affine.copy()
    roi_affine[:3, 3] += affine[:3, :3] @ start.astype(np.float64)
    roi_affine.setflags(write=False)
    return region, roi_affine, affine, start, shape, {
        'label_map_id': map_id,
        'label_id': label_id,
        'source_study_id': study_id,
        'artifact_sha256': artifact_digest,
        'identity_sha256': identity_digest,
        'provenance_sha256': provenance_digest,
        'source_volume_descriptor_sha256': volume_descriptor_digest,
        'source_volume_artifact_sha256': volume_artifact_digest,
        'coordinate_system': 'patient_lps',
        'units': 'mm',
        'roi_index_start': start.tolist(),
        'roi_shape': roi_shape.tolist(),
        'roi_has_virtual_zero_exterior': True,
        'artifact_validation': 'artifact_bytes_sha256_and_canonical_array_contract',
    }


def _verify_mpr(descriptors: object, *, affine: np.ndarray, shape: tuple[int, int, int],
                indices: object):
    if (not isinstance(descriptors, dict) or not isinstance(indices, dict)
            or set(descriptors) != {'axial', 'coronal', 'sagittal'}
            or set(indices) != set(descriptors)):
        raise ValueError('Three source-bound MPR planes and indices are required')
    corners = np.array([[a, b, c] for a in (0, shape[0] - 1)
                        for b in (0, shape[1] - 1) for c in (0, shape[2] - 1)],
                       dtype=np.float64)
    world = corners @ affine[:3, :3].T + affine[:3, 3]
    bounds = [(float(world[:, axis].min()), float(world[:, axis].max())) for axis in range(3)]
    for plane in ('axial', 'coronal', 'sagittal'):
        n, h, v, _position, horizontal, vertical, _reverse = _slice_info(
            plane, descriptors[plane], indices[plane]
        )
        for axis, observed in ((n, descriptors[plane]['position_range_mm']),
                               (h, horizontal), (v, vertical)):
            if not np.allclose(observed, bounds[axis], rtol=0, atol=1e-3):
                raise ValueError('MPR plane bounds differ from bound label source geometry')


def _surface_arrays(*, quality: str, surface: object, reference: object,
                    map_id: str, label_id: int):
    if (getattr(surface, 'label_map_id', None) != map_id
            or getattr(surface, 'label_id', None) != label_id
            or getattr(surface, 'quality', None) != quality
            or getattr(surface, 'coordinate_system', None) != 'patient_lps'
            or getattr(surface, 'extraction', None) != ACCURATE_SURFACE_EXTRACTION
            or getattr(surface, 'media_type', None) != ACCURATE_SURFACE_MEDIA_TYPE
            or getattr(surface, 'schema_version', None) != 2
            or getattr(surface, 'stride', None) != 1):
        raise ValueError('Surface provenance/quality does not match label map')
    if (not isinstance(getattr(surface, 'surface_id', None), str)
            or re.fullmatch(r'surf-[0-9a-f]{32}', surface.surface_id) is None):
        raise ValueError('Invalid surface identity')
    _digest_field(getattr(surface, 'provenance_sha256', None))
    digest = _digest_field(getattr(surface, 'payload_sha256', None))
    payload = getattr(surface, 'payload', None)
    if not isinstance(payload, bytes) or sha256(payload).hexdigest() != digest:
        raise ValueError('Surface payload hash does not match bound surface descriptor')
    if quality == REFINED_SURFACE_QUALITY:
        if (getattr(surface, 'refinement', None) != REFINED_SURFACE_REFINEMENT
                or surface.reference_surface_id != reference.surface_id
                or surface.reference_payload_sha256 != reference.payload_sha256):
            raise ValueError('Refined surface is not derived from the bound accurate reference')
    positions, _normals, indices, bounds = _decode_v2_payload_geometry(
        payload, label_id=label_id, error_prefix='Phase 6G3'
    )
    if (surface.vertex_count != len(positions) or surface.triangle_count * 3 != len(indices)
            or surface.normal_count != len(positions)
            or not np.allclose(surface.bounds_lps_mm, bounds, atol=1e-4, rtol=0)):
        raise ValueError('Surface counts differ from decoded payload')
    return positions.astype(np.float64), indices.reshape(-1, 3).astype(np.int64)


def bound_fidelity_report(*, source_study_id: str, mpr_study_id: str,
                          label_map_descriptor: dict, label_artifact_path: Path,
                          label_id: int, surfaces: dict,
                          mpr_descriptors: dict, slice_indices: dict,
                          mesh_sample_limit: int = 256,
                          contour_sample_limit: int = 128) -> dict[str, object]:
    """Evaluate already service-selected, immutable source/surface/MPR snapshots.

    Caller must fetch latest-study identity, validated label descriptor, both
    surface objects, and MPR descriptor from the authoritative services. This
    function hashes the NPY and v2 payloads and validates geometry independently;
    it cannot authenticate a caller-supplied MPR study ID against the repository.
    """
    if not isinstance(mpr_study_id, str) or mpr_study_id != source_study_id:
        raise ValueError('MPR study binding differs from selected label source study')
    if not isinstance(surfaces, dict) or set(surfaces) not in (
            {ACCURATE_SURFACE_QUALITY}, {ACCURATE_SURFACE_QUALITY, REFINED_SURFACE_QUALITY}):
        raise ValueError('Accurate reference is required; refined is optional')
    mask, affine, full_affine, start, shape, source = _source_snapshot(
        descriptor=label_map_descriptor, artifact=label_artifact_path,
        study_id=source_study_id, label_id=label_id
    )
    _verify_mpr(mpr_descriptors, affine=full_affine, shape=shape, indices=slice_indices)
    geometry = {}
    for quality in (ACCURATE_SURFACE_QUALITY, REFINED_SURFACE_QUALITY):
        if quality in surfaces:
            geometry[quality] = _surface_arrays(
                quality=quality, surface=surfaces[quality],
                reference=surfaces[ACCURATE_SURFACE_QUALITY],
                map_id=source['label_map_id'], label_id=label_id
            )
    reports = {}
    for quality, (positions, faces) in geometry.items():
        surface_distances = sampled_bidirectional_mask_surface_mm(
            mask, affine, positions, faces, sample_limit=mesh_sample_limit
        )
        mpr = three_plane_mpr_surface_agreement_mm(
            mask, affine, positions, faces, mpr_descriptors, slice_indices,
            sample_limit=contour_sample_limit
        )
        sample_points = positions[np.linspace(0, len(positions) - 1,
                                             min(128, len(positions)), dtype=np.intp)]
        try:
            proxy = interface_residual_mm(mask, affine, sample_points)
        except ValueError as exc:
            if 'outside the acquired mask half-voxel domain' not in str(exc):
                raise
            proxy = {
                'status': 'not_evaluated_outside_half_voxel_domain',
                'distance_interpretation': 'first_order_proxy_not_shortest_boundary_distance',
            }
        reports[quality] = {
            'status': 'sampled_evidence_only' if mpr['all_planes_have_contours'] else 'needs_review',
            'surface_id': surfaces[quality].surface_id,
            'surface_payload_sha256': surfaces[quality].payload_sha256,
            'surface_provenance_sha256': surfaces[quality].provenance_sha256,
            'interface_residual_proxy': proxy,
            'surface_distances': surface_distances,
            'mpr': mpr,
        }
    if REFINED_SURFACE_QUALITY not in geometry:
        reports[REFINED_SURFACE_QUALITY] = {'status': 'not_available', 'reason': 'no_refined_surface_supplied'}
    if _digest(Path(label_artifact_path)) != source['artifact_sha256']:
        raise ValueError('Source label artifact changed during fidelity analysis')
    if any(sha256(surfaces[q].payload).hexdigest() != surfaces[q].payload_sha256 for q in geometry):
        raise ValueError('Source surface payload changed during fidelity analysis')
    status = ('sampled_evidence_only'
              if all(report['status'] == 'sampled_evidence_only' for report in reports.values())
              else 'needs_review')
    return {
        'metric': 'phase6g3_source_bound_sampled_mask_surface_and_mpr_evidence',
        'status': status,
        'source': source,
        'mpr_source_binding': 'caller_attested_same_latest_study_plus_canonical_world_bounds',
        'sampled_mpr_indices_zero_based': dict(slice_indices),
        'surfaces': reports,
        'sampling_claim': 'sampled_not_exhaustive',
        'whole_surface_hausdorff': 'not_computed',
        'raster_overlay_equivalence': 'not_evaluated',
        'source_artifact_mutation': False,
        'clinical_validation': 'not_claimed',
        'real_study_qualification': 'not_evaluated_by_this_pure_helper',
    }
