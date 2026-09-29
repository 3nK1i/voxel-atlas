from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import threading
from typing import Any

from .segmentation import (
    NON_TERMINAL_JOB_STATES,
    SegmentationConflictError,
    SegmentationError,
    SegmentationJobService,
    SegmentationUnavailableError,
    SegmentationValidationError,
)
from .segmentation_label_maps import SegmentationLabelMapService
from .mri_task_contract import model_for_source_modality
from .mri_source_qualification import qualify_mri_stored_source
from .mri_workflow_presentation import matching_mri_jobs, mri_read_only_snapshot
from .segmentation import CanonicalSegmentationSource


WORKFLOW_SCHEMA_VERSION = 1
FINALIZATION_FAILURE_CODE = "label_map_import_failed"


@dataclass(frozen=True, slots=True)
class SegmentationWorkflowStart:
    workflow: dict[str, object]
    background_job_id: str | None = None


class SegmentationWorkflowService:
    """On-demand bridge from a canonical patient volume to reusable segmentation presentation.

    The service never starts provider execution while merely inspecting status. Provider execution
    is created only through ``request_start``. Existing immutable canonical label maps are reusable
    without recomputation.
    """

    def __init__(
        self,
        *,
        data_dir: Path,
        job_service: SegmentationJobService,
        label_map_service: SegmentationLabelMapService,
        python_executable: str | None,
        import_worker_script: Path,
        provider_id: str = "totalsegmentator",
        model_id: str = "total",
        import_timeout_seconds: float = 30 * 60,
        mri_presentation_only: bool = True,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.job_service = job_service
        self.label_map_service = label_map_service
        self.python_executable = str(python_executable or "").strip() or None
        self.import_worker_script = Path(import_worker_script).resolve(strict=False)
        self.provider_id = str(provider_id).strip().lower()
        self.model_id = str(model_id).strip().lower()
        self.import_timeout_seconds = float(import_timeout_seconds)
        self.mri_presentation_only = bool(mri_presentation_only)
        if (
            not self.provider_id
            or not self.model_id
            or self.import_timeout_seconds <= 0
            or self.import_timeout_seconds > 6 * 60 * 60
            or not self.import_worker_script.is_absolute()
            or self.import_worker_script.is_symlink()
            or not self.import_worker_script.is_file()
        ):
            raise SegmentationValidationError("Segmentation workflow configuration is invalid")
        if self.python_executable is not None and any(
            ord(character) < 32 for character in self.python_executable
        ):
            raise SegmentationValidationError("Segmentation runtime path is invalid")
        self.workflow_root = self.data_dir / "segmentation" / "workflow-status"
        self._lock = threading.RLock()
        self._finalizing_jobs: set[str] = set()

    def _source(self):
        return self.job_service.sources.latest()

    def _matching_model(self, model_id: str | None = None) -> dict[str, object] | None:
        requested_model_id = self.model_id if model_id is None else model_id
        for model in self.job_service.list_models():
            if (
                model.get("provider_id") == self.provider_id
                and model.get("model_id") == requested_model_id
            ):
                return dict(model)
        return None

    def _jobs_for_study(self, study_id: str) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for job in self.job_service.list_jobs():
            provenance = job.get("provenance")
            if isinstance(provenance, dict) and provenance.get("source_study_id") == study_id:
                result.append(dict(job))
        return result

    def _failure_path(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not job_id.startswith("seg-") or len(job_id) != 36:
            raise SegmentationValidationError("Segmentation workflow job identity is invalid")
        return self.workflow_root / f"{job_id}.json"

    def _read_finalization_failure(self, job_id: str) -> bool:
        path = self._failure_path(job_id)
        if path.is_symlink() or not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        return bool(
            isinstance(payload, dict)
            and payload.get("schema_version") == WORKFLOW_SCHEMA_VERSION
            and payload.get("job_id") == job_id
            and payload.get("code") == FINALIZATION_FAILURE_CODE
        )

    def _write_finalization_failure(self, job_id: str) -> None:
        root = self.workflow_root
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            return
        temp: Path | None = None
        try:
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(root, 0o700)
            path = self._failure_path(job_id)
            temp = root / f".{job_id}.{secrets.token_hex(8)}.tmp"
            payload = {
                "schema_version": WORKFLOW_SCHEMA_VERSION,
                "job_id": job_id,
                "code": FINALIZATION_FAILURE_CODE,
            }
            with temp.open("x", encoding="utf-8") as handle:
                os.chmod(temp, 0o600)
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        except OSError:
            if temp is not None:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass

    def _clear_finalization_failure(self, job_id: str) -> None:
        try:
            self._failure_path(job_id).unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _job_progress(job: dict[str, object]) -> dict[str, object]:
        progress = job.get("progress")
        if not isinstance(progress, dict):
            return {"stage": "queued", "percent": 0.0, "message": "Segmentation queued"}
        percent = progress.get("percent")
        try:
            normalized_percent = float(percent)
        except (TypeError, ValueError):
            normalized_percent = 0.0
        return {
            "stage": str(progress.get("stage") or "queued"),
            "percent": max(0.0, min(100.0, normalized_percent)),
            "message": str(progress.get("message") or "Segmentation in progress"),
        }

    def _base_snapshot(self, source: Any, model: dict[str, object] | None, model_id: str) -> dict[str, object]:
        modality = str(source.modality).upper()
        supported = isinstance(model, dict) and modality in tuple(model.get("supported_modalities") or ())
        available = bool(model and model.get("available") is True and supported)
        reason = None
        if model is None:
            reason = ("MRI TotalSegmentator total_mr provider is not qualified for execution"
                      if modality == "MR" and model_id == "total_mr"
                      else "Segmentation provider is not registered")
        elif not supported:
            reason = f"The selected segmentation model does not support {modality} input"
        elif model.get("available") is not True:
            reason = str(model.get("availability_reason") or "Segmentation runtime is unavailable")
        return {
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "study_id": str(source.study_id),
            "modality": modality,
            "provider_id": self.provider_id,
            "model_id": model_id,
            "provider_available": available,
            "provider_reason": reason,
            "clinical_validation": "not_claimed",
        }

    def snapshot_latest(self) -> dict[str, object]:
        with self._lock:
            source = self._source()
            model_id = model_for_source_modality(
                provider_id=self.provider_id,
                default_model_id=self.model_id,
                modality=str(source.modality).upper(),
            )
            model = self._matching_model(model_id)
            base = self._base_snapshot(source, model, model_id)
            study_id = str(source.study_id)

            # The common stored source is used by sample activation and new
            # DICOM uploads. Keep CT and injected test sources unchanged.
            if (model_id == "total_mr" and str(source.modality).upper() == "MR"
                    and isinstance(source, CanonicalSegmentationSource)):
                source_ready, source_reason = qualify_mri_stored_source(source)
                base = base | {"source_qualified": source_ready,
                               "source_qualification_reason": source_reason}
                if getattr(self, "mri_presentation_only", False):
                    base = base | {"source_series_uid": str(source.source_series_uid),
                                   "presentation_only": True,
                                   "mri_execution_authorized": False,
                                   "mri_label_map_ready": False}
                if not source_ready:
                    return base | {
                        "state": "unsupported", "message": source_reason,
                        "can_start": False, "can_cancel": False,
                        "can_use": False, "label_map_id": None,
                        "present_label_count": 0, "job_id": None,
                        "progress": None,
                    }
                if getattr(self, "mri_presentation_only", False):
                    return mri_read_only_snapshot(
                        source,
                        base,
                        self._jobs_for_study(study_id),
                        self.label_map_service.list(study_id=study_id),
                    )

            maps = self.label_map_service.list(study_id=study_id)
            if maps:
                descriptor = maps[0]
                labels = descriptor.get("present_labels")
                present_count = max(0, len(labels) - (1 if isinstance(labels, list) and 0 in labels else 0)) if isinstance(labels, list) else 0
                return base | {
                    "state": "available",
                    "message": "Existing segmentation is ready to use",
                    "can_start": False,
                    "can_cancel": False,
                    "can_use": True,
                    "label_map_id": descriptor.get("label_map_id"),
                    "present_label_count": present_count,
                    "job_id": descriptor.get("segmentation_job_id"),
                    "progress": {"stage": "complete", "percent": 100.0, "message": "Segmentation ready"},
                }

            jobs = self._jobs_for_study(study_id)
            active = next((item for item in jobs if item.get("state") in NON_TERMINAL_JOB_STATES), None)
            if active is not None:
                state = str(active.get("state") or "queued")
                return base | {
                    "state": state,
                    "message": self._job_progress(active)["message"],
                    "can_start": False,
                    "can_cancel": state != "cancelling",
                    "can_use": False,
                    "label_map_id": None,
                    "present_label_count": 0,
                    "job_id": active.get("job_id"),
                    "progress": self._job_progress(active),
                }

            latest = jobs[0] if jobs else None
            if latest is not None and latest.get("state") == "succeeded":
                job_id = str(latest.get("job_id") or "")
                finalizing = job_id in self._finalizing_jobs
                failed = self._read_finalization_failure(job_id)
                state = "finalizing" if finalizing else ("failed" if failed else "output_ready")
                message = (
                    "Preparing segmentation for visualization"
                    if finalizing
                    else (
                        "Segmentation completed, but visualization preparation failed"
                        if failed
                        else "Segmentation output is ready to prepare"
                    )
                )
                return base | {
                    "state": state,
                    "message": message,
                    "can_start": not finalizing and self.python_executable is not None,
                    "can_cancel": False,
                    "can_use": False,
                    "label_map_id": None,
                    "present_label_count": 0,
                    "job_id": job_id,
                    "progress": {"stage": "finalizing", "percent": 100.0, "message": message},
                }

            if latest is not None and latest.get("state") in {"failed", "cancelled"}:
                state = str(latest.get("state"))
                return base | {
                    "state": state,
                    "message": "Segmentation failed. Retry when ready" if state == "failed" else "Segmentation cancelled",
                    "can_start": bool(base["provider_available"]),
                    "can_cancel": False,
                    "can_use": False,
                    "label_map_id": None,
                    "present_label_count": 0,
                    "job_id": latest.get("job_id"),
                    "progress": self._job_progress(latest),
                }

            if model is not None and str(source.modality).upper() not in tuple(model.get("supported_modalities") or ()):
                return base | {
                    "state": "unsupported",
                    "message": str(base["provider_reason"]),
                    "can_start": False,
                    "can_cancel": False,
                    "can_use": False,
                    "label_map_id": None,
                    "present_label_count": 0,
                    "job_id": None,
                    "progress": None,
                }
            if not bool(base["provider_available"]):
                return base | {
                    "state": "unavailable",
                    "message": str(base["provider_reason"]),
                    "can_start": False,
                    "can_cancel": False,
                    "can_use": False,
                    "label_map_id": None,
                    "present_label_count": 0,
                    "job_id": None,
                    "progress": None,
                }
            return base | {
                "state": "idle",
                "message": "Segmentation has not been started",
                "can_start": True,
                "can_cancel": False,
                "can_use": False,
                "label_map_id": None,
                "present_label_count": 0,
                "job_id": None,
                "progress": None,
            }

    def request_start(self) -> SegmentationWorkflowStart:
        with self._lock:
            snapshot = self.snapshot_latest()
            state = str(snapshot.get("state") or "")
            if snapshot.get("presentation_only") is True and snapshot.get("modality") == "MR":
                raise SegmentationUnavailableError("MRI model execution and label-map integration remain disabled")
            if state == "available":
                return SegmentationWorkflowStart(snapshot)
            if state in NON_TERMINAL_JOB_STATES or state == "finalizing":
                return SegmentationWorkflowStart(snapshot)
            if state in {"unsupported", "unavailable"}:
                raise SegmentationUnavailableError(str(snapshot.get("message") or "Segmentation is unavailable"))
            if state in {"output_ready", "failed"} and snapshot.get("job_id"):
                job_id = str(snapshot["job_id"])
                try:
                    job = self.job_service.get_job(job_id)
                except SegmentationError:
                    job = None
                if isinstance(job, dict) and job.get("state") == "succeeded":
                    if self.python_executable is None:
                        raise SegmentationUnavailableError("Segmentation import runtime is not configured")
                    self._clear_finalization_failure(job_id)
                    return SegmentationWorkflowStart(snapshot, job_id)
            source = self._source()
            if not bool(snapshot.get("provider_available")):
                raise SegmentationUnavailableError(str(snapshot.get("provider_reason") or "Segmentation is unavailable"))
            job = self.job_service.create_job(
                provider_id=self.provider_id,
                model_id=str(snapshot["model_id"]),
                device_request="auto",
                parameters={},
                source_study_id=str(source.study_id),
            )
            created = self.snapshot_latest()
            return SegmentationWorkflowStart(created, str(job["job_id"]))

    def execute_requested(self, job_id: str) -> None:
        try:
            job = self.job_service.get_job(job_id)
            if getattr(self, "mri_presentation_only", False):
                provenance = job.get("provenance")
                if isinstance(provenance, dict) and (provenance.get("model_id") == "total_mr"
                        or provenance.get("source_modality") == "MR"):
                    return  # C4C is presentation-only; not the MRI worker execution gate.
            if job.get("state") == "queued":
                job = self.job_service.run_job(job_id)
            if job.get("state") != "succeeded":
                return
            if self.python_executable is None:
                self._write_finalization_failure(job_id)
                return
            with self._lock:
                self._finalizing_jobs.add(job_id)
                self._clear_finalization_failure(job_id)
            try:
                self.label_map_service.import_succeeded_job(
                    job_id=job_id,
                    python_executable=self.python_executable,
                    worker_script=self.import_worker_script,
                    timeout_seconds=self.import_timeout_seconds,
                )
            except Exception:  # noqa: BLE001 - private artifact details must not reach workflow state.
                self._write_finalization_failure(job_id)
            else:
                self._clear_finalization_failure(job_id)
            finally:
                with self._lock:
                    self._finalizing_jobs.discard(job_id)
        except SegmentationError:
            return

    def cancel_latest(self) -> dict[str, object]:
        with self._lock:
            source = self._source()
            jobs = self._jobs_for_study(str(source.study_id))
            if getattr(self, "mri_presentation_only", False) and getattr(source, "modality", None) == "MR":
                jobs = matching_mri_jobs(source, jobs)
            for job in jobs:
                if job.get("state") in NON_TERMINAL_JOB_STATES:
                    self.job_service.cancel_job(str(job["job_id"]))
                    break
            return self.snapshot_latest()
