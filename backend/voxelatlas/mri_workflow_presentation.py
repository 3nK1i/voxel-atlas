"""Read-only MRI job status bound to the current canonical source (Phase 6J-C4C).

No CT label maps or CT import workers are compatible with this presentation path.
Normal MRI model execution remains disabled until independent C5 acceptance.
"""
from __future__ import annotations

import math
from typing import Any


_ACTIVE = frozenset(("queued", "starting", "running", "cancelling"))
_TERMINAL = frozenset(("succeeded", "failed", "cancelled"))


def matching_mri_job(source: Any, job: object) -> bool:
    """Require the complete immutable source identity, not study ID alone."""
    if not isinstance(job, dict) or getattr(source, "modality", None) != "MR":
        return False
    provenance = job.get("provenance")
    if not isinstance(provenance, dict):
        return False
    expected = {
        "source_study_id": getattr(source, "study_id", None),
        "source_study_instance_uid": getattr(source, "study_instance_uid", None),
        "source_series_uid": getattr(source, "source_series_uid", None),
        "source_modality": "MR",
        "canonical_volume_created_at_utc": getattr(source, "volume_created_at_utc", None),
        "canonical_volume_descriptor_sha256": getattr(source, "descriptor_sha256", None),
        "canonical_volume_artifact_sha256": getattr(source, "artifact_sha256", None),
        "provider_id": "totalsegmentator",
        "model_id": "total_mr",
    }
    return all(isinstance(value, str) and bool(value) and provenance.get(key) == value
               for key, value in expected.items())


def matching_mri_jobs(source: Any, jobs: list[dict[str, object]]) -> list[dict[str, object]]:
    return [job for job in jobs if matching_mri_job(source, job)]


def mri_read_only_snapshot(
    source: Any, base: dict[str, object], jobs: list[dict[str, object]],
) -> dict[str, object]:
    """Report an existing bound MR job without granting model or label-map execution."""
    common = base | {
        "source_series_uid": str(source.source_series_uid),
        "presentation_only": True,
        "mri_execution_authorized": False,
        "mri_label_map_ready": False,
        "can_start": False,
        "can_cancel": False,
        "can_use": False,
        "label_map_id": None,
        "present_label_count": 0,
        "job_id": None,
        "progress": None,
    }
    matches = matching_mri_jobs(source, jobs)
    active = next((job for job in matches if job.get("state") in _ACTIVE), None)
    selected = active if active is not None else (matches[0] if matches else None)
    if selected is None:
        return common | {
            "state": "unavailable",
            "message": str(base.get("provider_reason") or "MRI model execution awaits qualification"),
        }

    state = selected.get("state")
    if state not in _ACTIVE | _TERMINAL:
        return common | {"state": "unavailable", "message": "MRI job status is unavailable"}
    percent: float = 0.0
    if isinstance(selected.get("progress"), dict):
        raw = selected["progress"].get("percent")
        if type(raw) in (int, float) and math.isfinite(raw):
            percent = max(0.0, min(100.0, float(raw)))
    message = {
        "queued": "MRI segmentation job queued for supervised execution",
        "starting": "MRI segmentation job starting",
        "running": "MRI segmentation job processing",
        "cancelling": "MRI segmentation job cancelling",
        "succeeded": "MRI output recorded; label-map integration and inference acceptance are pending",
        "failed": "MRI segmentation job failed; execution remains disabled",
        "cancelled": "MRI segmentation job cancelled; execution remains disabled",
    }[state]
    visible_state = "output_ready" if state == "succeeded" else state
    return common | {
        "state": visible_state,
        "message": message,
        "job_id": selected.get("job_id"),
        "can_cancel": state in _ACTIVE - {"cancelling"},
        "progress": {"stage": str(state), "percent": percent, "message": message},
    }
