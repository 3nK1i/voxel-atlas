"""Phase 6H-A: local real-study fidelity qualification, no production endpoint.

Canonical source artifacts are read/hashed, never edited.  The execute mode calls
existing 6A/6B surface services, which may use their normal temporary worker
scratch under data/segmentation/surface-tmp; this is NOT a directory-wide
read-only operation.  Preflight mode does not invoke the workers or write files.
No clinical/whole-mesh accuracy conclusion follows from this report.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

import numpy as np

from .segmentation_surface_distances import MAX_6G1_MASK_VOXELS
from .segmentation_surface_fidelity_report import (
    MAX_6G3_SOURCE_VOXELS, MAX_6G3_ARTIFACT_BYTES, _digest, _verify_mpr, bound_fidelity_report,
)
from .segmentation_surfaces import ACCURATE_SURFACE_QUALITY, REFINED_SURFACE_QUALITY

_MAP_ID = re.compile(r'map-[0-9a-f]{32}\Z')
_STUDY_ID = re.compile(r'[0-9a-f]{32}\Z')
_PLANES = ('axial', 'coronal', 'sagittal')


class RealStudyQualificationError(ValueError):
    """Non-identifying, bounded failure for local qualification."""


@dataclass(frozen=True)
class QualificationServices:
    volume: object
    labels: object
    mpr: object
    surfaces: object | None = None


def _latest_manifest(mpr: object, expected_path: Path) -> None:
    # MPR descriptors do not expose a source-study ID. Pin the
    # repository-selected manifest *path* before/after taking MPR snapshots.
    actual = mpr._latest_manifest_path()  # Existing MPR service contract.
    if actual.is_symlink() or actual.resolve(strict=True) != expected_path.resolve(strict=True):
        raise RealStudyQualificationError('MPR latest-study manifest differs from the source')


def _identity(source: object, descriptor: dict, label_id: int, expected_study_id: str | None):
    study_id = source.study_dir.name
    if (_STUDY_ID.fullmatch(study_id) is None
            or (expected_study_id is not None and study_id != expected_study_id)):
        raise RealStudyQualificationError('Selected source is not the expected latest study')
    if (source.modality != 'CT' or source.intensity_units != 'HU'
            or descriptor.get('source_study_id') != study_id
            or descriptor.get('source_modality') != 'CT'
            or descriptor.get('source_volume_descriptor_sha256') != source.source_descriptor_sha256
            or descriptor.get('clinical_validation') != 'not_claimed'):
        raise RealStudyQualificationError('Selected label map differs from the canonical CT source')
    if descriptor.get('source_volume_artifact_sha256') != _digest(source.volume_path):
        raise RealStudyQualificationError('Canonical volume seal differs from the label-map provenance')
    if (descriptor.get('shape') != list(source.shape)
            or not np.allclose(np.asarray(descriptor.get('array_index_to_patient_lps'), dtype=np.float64),
                               np.asarray(source.array_index_to_patient_lps, dtype=np.float64),
                               atol=1e-5, rtol=0)):
        raise RealStudyQualificationError('Label map shape/affine differs from the canonical CT source')
    if (isinstance(label_id, bool) or not isinstance(label_id, int)
            or not 0 < label_id <= 65535 or label_id not in descriptor.get('present_labels', [])):
        raise RealStudyQualificationError('Requested label is not present in the source label map')
    return study_id


def _roi_preflight(path: Path, descriptor: dict, label_id: int) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or path.suffix != '.npy':
        raise RealStudyQualificationError('Selected canonical label artifact is unavailable')
    if (not 0 < path.stat().st_size <= MAX_6G3_ARTIFACT_BYTES
            or path.stat().st_size != descriptor.get('artifact_bytes')
            or _digest(path) != descriptor.get('artifact_sha256')):
        raise RealStudyQualificationError('Canonical label artifact seal changed')
    shape = descriptor.get('shape')
    if (not isinstance(shape, list) or len(shape) != 3 or not all(type(n) is int and n > 0 for n in shape)
            or int(np.prod(shape, dtype=np.int64)) > MAX_6G3_SOURCE_VOXELS):
        raise RealStudyQualificationError('Canonical label shape exceeds the 6G3 source budget')
    labels = np.load(path, mmap_mode='r', allow_pickle=False)
    if list(labels.shape) != shape or labels.dtype != np.dtype('uint16'):
        raise RealStudyQualificationError('Canonical label artifact array contract changed')
    mask = labels == label_id
    axes = [np.flatnonzero(np.any(mask, axis=tuple(j for j in range(3) if j != axis))) for axis in range(3)]
    if any(not len(coords) for coords in axes):
        raise RealStudyQualificationError('Selected label has no voxels in its canonical artifact')
    start = [int(coords[0]) for coords in axes]
    roi_shape = [int(coords[-1] - coords[0] + 1) for coords in axes]
    roi_voxels = int(np.prod(roi_shape, dtype=np.int64))
    return {
        'roi_index_start': start,
        'roi_shape': roi_shape,
        'roi_voxels': roi_voxels,
        'roi_within_6g_budget': roi_voxels <= MAX_6G1_MASK_VOXELS,
        'acquisition_boundary_contact': any(a == 0 or a + b == n
                                            for a, b, n in zip(start, roi_shape, shape)),
    }


def _slice_selection(mpr_descriptor: dict, label_descriptor: dict, roi: dict) -> dict[str, int]:
    """Choose one physically central slice of the selected label's ROI per plane."""
    affine = np.asarray(label_descriptor['array_index_to_patient_lps'], dtype=np.float64)
    center_index = np.asarray(roi['roi_index_start'], dtype=np.float64) + (np.asarray(roi['roi_shape']) - 1) / 2
    world = affine[:3, :3] @ center_index + affine[:3, 3]
    indices = {}
    for name in _PLANES:
        plane = mpr_descriptor['planes'][name]
        coordinate = {'x': 0, 'y': 1, 'z': 2}[plane['normal_axis']]
        first = float(plane['position_range_mm'][0])
        spacing = float(plane['slice_spacing_mm'])
        count = plane['slice_count']
        index = 0 if count == 1 else int(np.clip(round((world[coordinate] - first) / spacing), 0, count - 1))
        indices[name] = index
    return indices


def qualify_real_study(*, data_dir: Path, label_map_id: str, label_id: int,
                       services: QualificationServices, execute: bool = False,
                       expected_study_id: str | None = None,
                       mesh_sample_limit: int = 128, contour_sample_limit: int = 96) -> dict[str, object]:
    """Return an in-memory local report; never create patient artifacts or publish metrics.

    The caller is responsible for sourcing the services from the same data-dir.
    Refined failures are *not* silently converted to accurate: they propagate
    and require review or an explicit separate accurate-only invocation later.
    """
    if _MAP_ID.fullmatch(label_map_id) is None:
        raise RealStudyQualificationError('Invalid label-map identifier')
    if expected_study_id is not None and _STUDY_ID.fullmatch(expected_study_id) is None:
        raise RealStudyQualificationError('Invalid expected-study identifier')
    source = services.volume.source_latest()
    descriptor = services.labels.get(label_map_id)
    study_id = _identity(source, descriptor, label_id, expected_study_id)
    path = Path(data_dir) / 'segmentation' / 'label-maps' / label_map_id / 'labels.npy'
    if source.manifest_path.is_symlink() or source.volume_path.is_symlink():
        raise RealStudyQualificationError('Canonical source contains symlinked artifacts')
    before_manifest = _digest(source.manifest_path)
    before_volume = _digest(source.volume_path)
    before_label = _digest(path)
    _latest_manifest(services.mpr, source.manifest_path)
    mpr = services.mpr.descriptor_latest()
    _latest_manifest(services.mpr, source.manifest_path)
    if (mpr.get('ready') is not True or mpr.get('modality') != 'CT'
            or mpr.get('intensity_units') != 'HU' or set(mpr.get('planes', {})) != set(_PLANES)):
        raise RealStudyQualificationError('MPR descriptor is not the selected canonical CT study')
    roi = _roi_preflight(path, descriptor, label_id)
    indices = _slice_selection(mpr, descriptor, roi)
    # The real MPR service selected the same manifest; independently confirm
    # its slice-axis/world-bounds geometry against the canonical LPS volume.
    _verify_mpr(mpr['planes'], affine=np.asarray(source.array_index_to_patient_lps, dtype=np.float64),
                shape=source.shape, indices=indices)
    snapshot = {
        'status': 'preflight_ready' if roi['roi_within_6g_budget'] else 'analysis_budget_exceeded',
        'source': {'study_id': study_id, 'label_map_id': label_map_id,
                   'volume_sha256': before_volume, 'label_sha256': before_label,
                   'manifest_sha256': before_manifest},
        'source_binding': 'latest_manifest_canonical_descriptor_and_artifact_seals',
        'mpr_selection': indices,
        'roi': roi,
        'clinical_validation': 'not_claimed',
        'source_artifact_mutation': False,
    }
    if execute:
        if not roi['roi_within_6g_budget']:
            raise RealStudyQualificationError('Selected label ROI exceeds bounded 6G analysis budget')
        if services.surfaces is None:
            raise RealStudyQualificationError('6A/6B surface service is required to execute qualification')
        accurate = services.surfaces.surface_latest(
            label_id=label_id, label_map_id=label_map_id, quality=ACCURATE_SURFACE_QUALITY)
        refined = services.surfaces.surface_latest(
            label_id=label_id, label_map_id=label_map_id, quality=REFINED_SURFACE_QUALITY)
        report = bound_fidelity_report(
            source_study_id=study_id, mpr_study_id=study_id,
            label_map_descriptor=descriptor, label_artifact_path=path,
            label_id=label_id, surfaces={'accurate': accurate, 'refined': refined},
            mpr_descriptors=mpr['planes'], slice_indices=indices,
            mesh_sample_limit=mesh_sample_limit, contour_sample_limit=contour_sample_limit)
        snapshot['status'] = report['status']
        snapshot['fidelity'] = report
    # Services are not transactionally locked. Reject stale data observed
    # after the run; still no claim of a DB-atomic snapshot.
    _latest_manifest(services.mpr, source.manifest_path)
    if (services.volume.source_latest().study_dir.name != study_id
            or _digest(source.manifest_path) != before_manifest
            or _digest(source.volume_path) != before_volume
            or _digest(path) != before_label
            or services.labels.get(label_map_id)['identity_sha256'] != descriptor['identity_sha256']):
        raise RealStudyQualificationError('Canonical study/label source changed during local qualification')
    return snapshot
