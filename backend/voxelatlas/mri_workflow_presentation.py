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


def _matching_mri_label_map(
    source: Any, jobs: list[dict[str, object]], descriptor: object,
) -> bool:
    """Accept only a persisted MRI map bound to this exact source and succeeded job."""
    if not isinstance(descriptor, dict) or descriptor.get("state") != "ready":
        return False
    matching_jobs_by_id = {
        str(job.get("job_id")): job
        for job in matching_mri_jobs(source, jobs)
        if job.get("state") == "succeeded" and isinstance(job.get("job_id"), str)
    }
    job = matching_jobs_by_id.get(str(descriptor.get("segmentation_job_id") or ""))
    if job is None:
        return False
    expected = {
        "source_study_id": getattr(source, "study_id", None),
        "source_study_instance_uid": getattr(source, "study_instance_uid", None),
        "source_series_uid": getattr(source, "source_series_uid", None),
        "source_modality": "MR",
        "source_volume_descriptor_sha256": getattr(source, "descriptor_sha256", None),
        "source_volume_artifact_sha256": getattr(source, "artifact_sha256", None),
        "segmentation_terminal_provenance_sha256": job.get("terminal_provenance_sha256"),
        "provider_id": "totalsegmentator",
        "model_id": "total_mr",
        "task": "total_mr",
        "class_count": 50,
        "clinical_validation": "not_claimed",
    }
    if not all(descriptor.get(key) == value for key, value in expected.items()):
        return False
    labels = descriptor.get("present_labels")
    return bool(
        isinstance(labels, list)
        and labels
        and labels == sorted(set(labels))
        and labels[0] == 0
        and all(type(label) is int and 0 <= label <= 50 for label in labels)
    )


def mri_read_only_snapshot(
    source: Any, base: dict[str, object], jobs: list[dict[str, object]],
    label_maps: list[dict[str, object]] | None = None,
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
    if active is not None:
        selected = active
    else:
        presentation = next(
            (descriptor for descriptor in (label_maps or [])
             if _matching_mri_label_map(source, matches, descriptor)),
            None,
        )
        if presentation is not None:
            labels = presentation.get("present_labels")
            assert isinstance(labels, list)
            return common | {
                "state": "available",
                "message": "Existing MRI segmentation is ready to use",
                "mri_label_map_ready": True,
                "can_use": True,
                "label_map_id": presentation.get("label_map_id"),
                "present_label_count": max(0, len(labels) - (1 if 0 in labels else 0)),
                "job_id": presentation.get("segmentation_job_id"),
                "progress": {
                    "stage": "complete",
                    "percent": 100.0,
                    "message": "MRI segmentation ready for visualization",
                },
            }
        selected = matches[0] if matches else None
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
