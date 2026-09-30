"""Study/series-bound MRI provider adapter.

Normal-app registration is permitted only after independent runtime/weight qualification,
and every invocation still requires an explicit execution-permission check.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Callable

from .mri_source_qualification import qualify_mri_stored_source
from .mri_task_contract import MRI_TASK_SOURCE_MAPPING_SHA256
from .mri_runtime_qualification import MRI_MAPPING_JSON_SHA256
from .mri_worker_execution import MRIWorkerExecutor, MRIWorkerRequest, MRIWorkerError
from .segmentation import (
    CanonicalSegmentationSource, SegmentationCancellationRequested,
    SegmentationConflictError, SegmentationExecutionContext, SegmentationJobService,
    SegmentationModelDescriptor, SegmentationProviderError, SegmentationProviderResult,
    SegmentationUnavailableError, SegmentationValidationError,
)

_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ARTIFACT = "provider/totalsegmentator-mri/output/labels.nii.gz"


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


class MRIStudyBoundProvider:
    """MRI-only job-service adapter; app/registry wiring remains intentionally absent.

    A callable permission is checked per invocation, never cached at startup.
    An unconfigured permission blocks model execution before reading patient data.
    C4B tests may inject an entirely synthetic executor; real GPU qualification is C5.
    """

    def __init__(self, *, data_dir: Path, job_service: SegmentationJobService,
                 descriptor: SegmentationModelDescriptor, executor: MRIWorkerExecutor,
                 execution_permission: Callable[[], bool] | None = None,
                 source_check: Callable[[CanonicalSegmentationSource], tuple[bool, str]] = qualify_mri_stored_source) -> None:
        if (not isinstance(data_dir, Path) or not data_dir.is_absolute()
                or data_dir.is_symlink() or not data_dir.is_dir()
                or not isinstance(job_service, SegmentationJobService)
                or job_service.data_dir != data_dir
                or not isinstance(descriptor, SegmentationModelDescriptor)
                or descriptor.identity != ("totalsegmentator", "total_mr")
                or descriptor.supported_modalities != ("MR",)
                or descriptor.available is not True
                or not isinstance(executor, MRIWorkerExecutor)
                or not callable(source_check)
                or (execution_permission is not None and not callable(execution_permission))):
            raise SegmentationValidationError("MRI job binding configuration is invalid")
        self.data_dir = data_dir
        self.jobs = job_service
        self.descriptor = descriptor
        self.executor = executor
        self.execution_permission = execution_permission or (lambda: False)
        self.source_check = source_check

    def validate_parameters(self, parameters: dict[str, object]) -> dict[str, object]:
        if (type(parameters) is not dict or set(parameters) - {"mode"}
                or parameters.get("mode", "fastest") not in ("default", "fast", "fastest")):
            raise SegmentationValidationError("MRI segmentation mode is invalid")
        return {"mode": parameters.get("mode", "fastest")}

    def _source_and_request(self, context: SegmentationExecutionContext) -> MRIWorkerRequest:
        if (not isinstance(context, SegmentationExecutionContext)
                or context.model.descriptor_sha256 != self.descriptor.descriptor_sha256
                or context.model.identity != ("totalsegmentator", "total_mr")
                or not isinstance(context.source, CanonicalSegmentationSource)
                or context.source.modality != "MR"
                or context.device.kind != "cuda"
                or type(context.device.index) is not int
                or context.device.selector != f"cuda:{context.device.index}"):
            raise SegmentationConflictError("MRI job provider, source, or device binding changed")
        mode = self.validate_parameters(context.parameters)["mode"]
        if context.device.total_memory_mib is not None and context.device.total_memory_mib <= 8192 and mode != "fastest":
            raise SegmentationUnavailableError("MRI low-memory GPU requires the 6 mm trial mode")
        # Read the sealed job via the existing job-service manifest validator.
        job = self.jobs.get_job(context.job_id)
        provenance = job.get("provenance")
        if not isinstance(provenance, dict) or job.get("state") != "running":
            raise SegmentationConflictError("MRI job is not in the bound running state")
        bound = self.jobs.sources.load(context.source.study_id)
        original = context.source
        identity_fields = ("study_id", "study_instance_uid", "source_series_uid", "modality",
                           "volume_created_at_utc", "descriptor_sha256", "artifact_sha256",
                           "manifest_path", "study_dir", "volume_path", "metadata_path")
        if any(getattr(bound, field) != getattr(original, field) for field in identity_fields):
            raise SegmentationConflictError("MRI source identity changed after job creation")
        checks = {
            "source_study_id": bound.study_id,
            "source_study_instance_uid": bound.study_instance_uid,
            "source_series_uid": bound.source_series_uid,
            "source_modality": "MR",
            "canonical_volume_created_at_utc": bound.volume_created_at_utc,
            "canonical_volume_descriptor_sha256": bound.descriptor_sha256,
            "canonical_volume_artifact_sha256": bound.artifact_sha256,
            "provider_id": "totalsegmentator",
            "model_id": "total_mr",
            "model_descriptor_sha256": self.descriptor.descriptor_sha256,
            "parameters": {"mode": mode},
        }
        if (any(provenance.get(key) != value for key, value in checks.items())
                or not isinstance(provenance.get("selected_device"), dict)
                or provenance["selected_device"].get("selector") != context.device.selector
                or provenance["selected_device"].get("index") != context.device.index):
            raise SegmentationConflictError("MRI job provenance binding changed")
        source_ready, _ = self.source_check(bound)
        if source_ready is not True:
            raise SegmentationUnavailableError("MRI source and series are no longer qualified")
        if (not bound.volume_path.is_relative_to(self.data_dir)
                or not bound.metadata_path.is_relative_to(self.data_dir)
                or not bound.manifest_path.is_relative_to(self.data_dir)
                or any(p.is_symlink() for p in (bound.study_dir, bound.volume_path, bound.metadata_path, bound.manifest_path))
                or _digest(bound.volume_path) != bound.artifact_sha256):
            raise SegmentationConflictError("MRI source artifact changed after job creation")
        return MRIWorkerRequest(
            data_dir=self.data_dir, job_id=context.job_id,
            source_npy=bound.volume_path, source_descriptor=bound.metadata_path,
            source_sha256=bound.artifact_sha256, descriptor_sha256=bound.descriptor_sha256,
            device_index=context.device.index, mode=mode,
        )

    def run(self, context: SegmentationExecutionContext) -> SegmentationProviderResult:
        context.raise_if_cancelled()
        # Strictly before any MRI worker call; even a configured runtime cannot enable it.
        if self.execution_permission() is not True:
            raise SegmentationUnavailableError("MRI model execution is not authorized")
        try:
            request = self._source_and_request(context)
            context.raise_if_cancelled()
            context.report_progress(stage="preparing", percent=5., message="Checking MRI study binding")
            report = self.executor.execute(
                request, cancellation_check=lambda: context.cancellation_requested,
                explicit_model_authorization=True,
            )
            context.raise_if_cancelled()
            mask = self.data_dir / "segmentation" / "jobs" / request.job_id / _ARTIFACT
            labels = report.get("present_labels") if type(report) is dict else None
            if (type(report) is not dict or report.get("schema") != 1
                    or report.get("task") != "total_mr" or report.get("modality") != "MR"
                    or report.get("mode") != request.mode
                    or report.get("model_version") != "2.18.0"
                    or report.get("model_mapping_sha256") != MRI_MAPPING_JSON_SHA256
                    or not isinstance(report.get("weights_manifest_sha256"), str)
                    or not _SHA.fullmatch(report["weights_manifest_sha256"])
                    or report.get("mask_artifact") != _ARTIFACT
                    or report.get("clinical_validation") != "not_claimed"
                    or type(report.get("nonzero_voxels")) is not int or report["nonzero_voxels"] <= 0
                    or type(labels) is not list or not labels or labels != sorted(set(labels))
                    or any(type(n) is not int or n < 0 or n > 50 for n in labels)
                    or not isinstance(report.get("cuda"), dict)
                    or report["cuda"].get("selected_index") != request.device_index
                    or not isinstance(report.get("mask_nifti_sha256"), str)
                    or not _SHA.fullmatch(report["mask_nifti_sha256"])
                    or not isinstance(report.get("input_nifti_sha256"), str)
                    or not _SHA.fullmatch(report["input_nifti_sha256"])
                    or any(parent.is_symlink() for parent in (mask.parent, mask.parent.parent, mask.parent.parent.parent))
                    or mask.is_symlink() or not mask.is_file() or _digest(mask) != report["mask_nifti_sha256"]
                    or _digest(request.source_npy) != request.source_sha256
                    or self.jobs.sources.load(context.source.study_id) != context.source
                    or self.source_check(context.source)[0] is not True):
                raise SegmentationProviderError("MRI job output or source binding is invalid")
            # A study switch does not reassign this job; its immutable study/series
            # provenance is retained by SegmentationJobService. Cancellation wins.
            context.raise_if_cancelled()
            context.report_progress(stage="finalizing", percent=98., message="Recording MRI job provenance")
            return SegmentationProviderResult(outcome={
                "code": "qualified_execution", "message": "MRI segmentation output generated; not clinically validated",
                "provider": {"task": "total_mr", "model_version": "2.18.0", "class_count": 50,
                             "task_definition_sha256": MRI_TASK_SOURCE_MAPPING_SHA256},
                "weights_manifest_sha256": report["weights_manifest_sha256"],
                "mode": request.mode, "model_mapping_sha256": report["model_mapping_sha256"],
                "input_nifti_sha256": report["input_nifti_sha256"],
                "mask_nifti_sha256": report["mask_nifti_sha256"],
                "mask_artifact": _ARTIFACT, "nonzero_voxels": report["nonzero_voxels"],
                "present_labels": labels, "clinical_validation": "not_claimed",
            })
        except SegmentationCancellationRequested:
            raise
        except (MRIWorkerError, OSError, ValueError, TypeError) as exc:
            if context.cancellation_requested:
                raise SegmentationCancellationRequested("MRI job cancelled") from exc
            raise SegmentationProviderError("MRI supervised job execution failed") from exc
