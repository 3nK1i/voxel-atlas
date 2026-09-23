"""6J-B2A: read-only canonical MR source and series qualification.

Both sample activation and DICOM upload flow through the same stored study
manifest. This is *not* MR-sequence fitness or model-runtime qualification.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .mri_task_contract import qualify_mri_canonical_descriptor

if TYPE_CHECKING:
    from .segmentation import CanonicalSegmentationSource


MAX_STUDY_MANIFEST_BYTES = 64 * 1024 * 1024


def qualify_mri_study_manifest(
    manifest: Mapping[str, object], *, study_id: str, series_uid: str
) -> tuple[bool, str]:
    """Qualify the active stored MR series without reading DICOM/patient pixels."""
    volume = manifest.get("volume")
    if manifest.get("study_id") != study_id or not isinstance(volume, dict):
        return False, "The active MRI study has no matching canonical volume"
    valid, reason = qualify_mri_canonical_descriptor(volume)
    if not valid:
        return False, reason
    if volume.get("source_series_uid") != series_uid:
        return False, "The canonical MRI volume does not match the active series"
    if manifest.get("reconstruction_series_uid") != series_uid:
        return False, "The selected MRI series is not reconstruction-qualified"
    series = manifest.get("series")
    if not isinstance(series, list):
        return False, "The MRI series inventory is unavailable"
    matches = [entry for entry in series if isinstance(entry, dict)
               and entry.get("series_instance_uid") == series_uid]
    if len(matches) != 1 or matches[0].get("modality") != "MR":
        return False, "The active MRI series identity or modality is invalid"
    chosen = matches[0]
    geometry = chosen.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("reconstruction_ready") is not True:
        return False, "The selected MRI series lacks qualified 3D DICOM geometry"
    shape = volume["shape"]
    dimensions = geometry.get("dimensions")
    if not isinstance(dimensions, (list, tuple)) or list(dimensions) != [shape[1], shape[2], shape[0]]:
        return False, "The MRI series dimensions disagree with the canonical volume"
    instance_count = chosen.get("instance_count")
    source_count = volume.get("source_instance_count")
    if (isinstance(instance_count, bool) or not isinstance(instance_count, int)
            or instance_count != shape[0] or source_count != instance_count):
        return False, "The MRI volume and source series have inconsistent slice counts"
    return True, "Canonical MRI source and 3D series geometry are eligible for model qualification"


def qualify_mri_stored_source(source: CanonicalSegmentationSource) -> tuple[bool, str]:
    """Read the immutable source's existing study manifest; do not modify it."""
    path: Path = source.manifest_path
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_STUDY_MANIFEST_BYTES:
            return False, "The stored MRI source manifest is unavailable"
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "The stored MRI source manifest is unreadable"
    if not isinstance(manifest, dict):
        return False, "The stored MRI source manifest is invalid"
    if source.modality != "MR":
        return False, "The active source is not an MRI volume"
    return qualify_mri_study_manifest(manifest, study_id=source.study_id,
                                      series_uid=source.source_series_uid)
