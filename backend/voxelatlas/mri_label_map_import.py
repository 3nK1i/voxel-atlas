"""Phase 6J-D2: separately gated import of an already completed MRI job.

No MRI inference, UI registration, or CT import-policy changes are performed here.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Callable

from .mri_runtime_qualification import MRI_MAPPING_JSON_SHA256
from .mri_source_qualification import qualify_mri_stored_source
from .mri_task_contract import MRI_TASK_SOURCE_MAPPING_SHA256
from .mri_workflow_presentation import matching_mri_job
from .mri_worker_execution import _read_report, _valid_provider
from .segmentation import (
    CanonicalSegmentationSource, CanonicalSegmentationSourceRepository,
    SegmentationJobService, SegmentationValidationError,
)
from .segmentation_label_maps import SegmentationLabelMapService, _load_source_metadata

MASK_RELATIVE = "provider/totalsegmentator-mri/output/labels.nii.gz"
INPUT_RELATIVE = "provider/totalsegmentator-mri/input/canonical-mri.nii.gz"
REPORT_RELATIVE = "provider/totalsegmentator-mri/output/provider-report.json"


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_inside(root: Path, relative: str) -> Path:
    path = root / relative
    if (root.is_symlink() or not root.is_dir() or path.is_symlink()
            or not path.is_file() or path.stat().st_size <= 0
            or path.resolve(strict=True) != path
            or root.resolve(strict=True) not in path.parents):
        raise SegmentationValidationError("MRI job artifact is unavailable or unsafe")
    cursor = path.parent
    while cursor != root:
        if cursor.is_symlink() or not cursor.is_dir():
            raise SegmentationValidationError("MRI job artifact parent is unsafe")
        cursor = cursor.parent
    return path


class QualifiedMRIResultImporter:
    """Validate a current source-bound MRI job before any label-map creation.

    The job service must be constructed only when there are no live jobs:
    its constructor recovers interrupted jobs. The standalone D2 entrypoint
    checks this separately before constructing this service.
    """

    def __init__(
        self, *, data_dir: Path,
        jobs: SegmentationJobService,
        label_maps: SegmentationLabelMapService,
        provider_report_check: Callable[[Path, Path, Path], None] | None = None,
    ) -> None:
        if (not isinstance(data_dir, Path) or not data_dir.is_absolute()
                or not data_dir.is_dir() or data_dir.is_symlink()
                or data_dir.resolve(strict=True) != data_dir
                or not isinstance(jobs, SegmentationJobService)
                or jobs.data_dir != data_dir
                or not isinstance(label_maps, SegmentationLabelMapService)
                or label_maps.data_dir != data_dir):
            raise SegmentationValidationError("MRI import repository configuration is invalid")
        self.data_dir = data_dir
        self.jobs = jobs
        self.maps = label_maps
        self.report_check = provider_report_check or self._check_provider_report

    @staticmethod
    def _check_provider_report(path: Path, input_path: Path, mask: Path) -> None:
        _valid_provider(_read_report(path), input_path, mask, "fastest")

    def qualify(self) -> tuple[CanonicalSegmentationSource, dict[str, object]]:
        """Read-only qualification; never scan for a different study as a fallback."""
        source = CanonicalSegmentationSourceRepository(self.data_dir).latest()
        if source.modality != "MR" or qualify_mri_stored_source(source)[0] is not True:
            raise SegmentationValidationError("Current canonical MRI source is not qualified")
        if (source.volume_path.is_symlink() or source.metadata_path.is_symlink()
                or source.manifest_path.is_symlink() or source.study_dir.is_symlink()
                or _hash_file(source.volume_path) != source.artifact_sha256):
            raise SegmentationValidationError("Current MRI source changed")
        _load_source_metadata(source)

        # Deliberately require exactly one matching successful job. Never pick
        # a different study, a CT job, or an ambiguous earlier MRI result.
        matches = [job for job in self.jobs.list_jobs()
                   if matching_mri_job(source, job) and job.get("state") == "succeeded"]
        if len(matches) != 1:
            raise SegmentationValidationError("Current MRI source has no unique accepted job")
        job = self.jobs.get_job(str(matches[0]["job_id"]))  # checks full terminal seal
        provenance = job["provenance"]
        outcome = job["outcome"]
        if not isinstance(provenance, dict) or not isinstance(outcome, dict):
            raise SegmentationValidationError("MRI job provenance is incomplete")
        device = provenance.get("selected_device")
        provider = outcome.get("provider")
        labels = outcome.get("present_labels")
        if (not matching_mri_job(source, job)
                or provenance.get("parameters") != {"mode": "fastest"}
                or provenance.get("provider_version") != "2.18.0"
                or provenance.get("model_version") != "2.18.0"
                or not isinstance(device, dict)
                or device.get("selector") != "cuda:0" or type(device.get("index")) is not int
                or device["index"] != 0
                or outcome.get("code") != "qualified_execution"
                or outcome.get("mode") != "fastest"
                or outcome.get("clinical_validation") != "not_claimed"
                or outcome.get("model_mapping_sha256") != MRI_MAPPING_JSON_SHA256
                or outcome.get("mask_artifact") != MASK_RELATIVE
                or not isinstance(provider, dict)
                or provider.get("task") != "total_mr"
                or provider.get("model_version") != "2.18.0"
                or type(provider.get("class_count")) is not int
                or provider["class_count"] != 50
                or provider.get("task_definition_sha256") != MRI_TASK_SOURCE_MAPPING_SHA256
                or type(outcome.get("nonzero_voxels")) is not int
                or outcome["nonzero_voxels"] <= 0
                or type(labels) is not list or not labels or labels[0] != 0
                or labels != sorted(set(labels))
                or any(type(label) is not int or label < 0 or label > 50 for label in labels)):
            raise SegmentationValidationError("MRI job identity or label contract changed")
        job_root = self.data_dir / "segmentation" / "jobs" / str(job["job_id"])
        mask = _regular_inside(job_root, MASK_RELATIVE)
        input_path = _regular_inside(job_root, INPUT_RELATIVE)
        report_path = _regular_inside(job_root, REPORT_RELATIVE)
        if (_hash_file(source.volume_path) != source.artifact_sha256
                or _hash_file(mask) != outcome.get("mask_nifti_sha256")
                or _hash_file(input_path) != outcome.get("input_nifti_sha256")):
            raise SegmentationValidationError("MRI source or provider artifact digest changed")
        self.report_check(report_path, input_path, mask)
        return source, job

    def import_current(self, *, python_executable: str, worker_script: Path) -> dict[str, object]:
        source, job = self.qualify()
        descriptor = self.maps.import_succeeded_job(
            job_id=str(job["job_id"]), python_executable=python_executable,
            worker_script=worker_script,
            expected_nonzero_voxels=int(job["outcome"]["nonzero_voxels"]),
        )
        # Requalify persisted provenance after canonicalization (not just the
        # generic worker's successful exit); do not silently promote a stale map.
        current, accepted = self.qualify()
        outcome = accepted["outcome"]
        if (current != source or accepted["job_id"] != job["job_id"]
                or descriptor.get("source_modality") != "MR"
                or descriptor.get("source_study_id") != source.study_id
                or descriptor.get("source_study_instance_uid") != source.study_instance_uid
                or descriptor.get("source_series_uid") != source.source_series_uid
                or descriptor.get("source_volume_descriptor_sha256") != source.descriptor_sha256
                or descriptor.get("source_volume_artifact_sha256") != source.artifact_sha256
                or descriptor.get("segmentation_job_id") != job["job_id"]
                or descriptor.get("segmentation_terminal_provenance_sha256") != job["terminal_provenance_sha256"]
                or descriptor.get("provider_id") != "totalsegmentator"
                or descriptor.get("model_id") != "total_mr"
                or descriptor.get("task") != "total_mr"
                or descriptor.get("task_definition_sha256") != MRI_TASK_SOURCE_MAPPING_SHA256
                or descriptor.get("class_count") != 50
                or descriptor.get("provider_mask_sha256") != outcome.get("mask_nifti_sha256")
                or descriptor.get("present_labels") != outcome.get("present_labels")
                or descriptor.get("nonzero_voxels") != outcome.get("nonzero_voxels")
                or descriptor.get("dtype") != "uint16"
                or descriptor.get("coordinate_system") != "patient_lps"
                or descriptor.get("resampled") is not False
                or descriptor.get("interpolation") != "none"
                or descriptor.get("clinical_validation") != "not_claimed"):
            raise SegmentationValidationError("Imported MRI label-map acceptance failed")
        return self.maps.get(str(descriptor["label_map_id"]))
