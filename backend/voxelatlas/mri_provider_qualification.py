"""MRI provider qualification and fail-closed model descriptors.

The historical unavailable descriptor remains the fallback. The executable descriptor
is constructed only from an already-qualified runtime and sealed MRI weights.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, TYPE_CHECKING

from .mri_runtime_qualification import MRIRuntimeQualifier, MRI_MAPPING_JSON_SHA256
from .mri_weights_qualification import (
    MRIAssetError, paths_for, qualify_installed_mri_mapping, verify_mri_weights,
)
from .segmentation import SegmentationExecutionRequirements, SegmentationModelDescriptor

if TYPE_CHECKING:
    from .segmentation import CanonicalSegmentationSource


@dataclass(frozen=True, slots=True)
class MRIProviderQualification:
    status_code: str
    reason: str
    runtime_qualified: bool = False
    weights_qualified: bool = False
    source_qualified: bool = False
    prerequisites_qualified: bool = False
    execution_authorized: bool = False


def qualify_mri_provider(
    *, data_dir: Path, python_executable: str | None,
    source: CanonicalSegmentationSource | None = None,
    runtime_qualifier: Callable[[str], object] | None = None,
    installed_mapping_check: Callable[[str], bool] = qualify_installed_mri_mapping,
    weights_check: Callable[[object], dict[str, object]] = verify_mri_weights,
    source_check: Callable[[object], tuple[bool, str]] | None = None,
) -> MRIProviderQualification:
    """Inspect prerequisites without starting or authorizing any model job.

    Source eligibility is study-specific, and cannot be claimed on registration
    alone. Dependency injection permits synthetic tests without GPU/weight data.
    Public reasons contain no paths, exception text, or patient information.
    """
    if python_executable is None or not isinstance(python_executable, str) or not python_executable.strip():
        return MRIProviderQualification("runtime_not_configured", "MRI runtime is not configured")
    try:
        executable = Path(python_executable).expanduser()
        if (not executable.is_absolute() or not executable.is_file()
                or not executable.stat().st_mode & 0o111):
            return MRIProviderQualification("runtime_unavailable", "MRI runtime is unavailable")
        qualifier = runtime_qualifier or MRIRuntimeQualifier().qualify
        runtime = qualifier(str(executable))
        if (getattr(runtime, "runtime_qualified", None) is not True
                or getattr(runtime, "execution_ready", None) is not False
                or getattr(runtime, "task", None) != "total_mr"
                or getattr(runtime, "task_modality", None) != "MR"
                or getattr(runtime, "task_class_count", None) != 50
                or getattr(runtime, "task_mapping_sha256", None) != MRI_MAPPING_JSON_SHA256
                or getattr(runtime, "totalsegmentator_version", None) != "2.18.0"):
            return MRIProviderQualification("runtime_unqualified", "MRI runtime is not qualified")
        if installed_mapping_check(str(executable)) is not True:
            return MRIProviderQualification("mapping_unqualified", "MRI model-task mapping is not qualified")
    except (OSError, ValueError, TypeError, RuntimeError):
        return MRIProviderQualification("runtime_unqualified", "MRI runtime is not qualified")
    try:
        weights = weights_check(paths_for(data_dir))
        if (type(weights) is not dict or weights.get("task") != "total_mr"
                or weights.get("mode_ids") != {"default": [850, 851], "fast": [852], "fastest": [853]}
                or not isinstance(weights.get("manifest_sha256"), str)
                or re.fullmatch(r"[a-f0-9]{64}", weights["manifest_sha256"]) is None):
            return MRIProviderQualification("weights_unqualified", "MRI model assets are not qualified",
                                            runtime_qualified=True)
    except (MRIAssetError, OSError, ValueError, TypeError, RuntimeError):
        return MRIProviderQualification("weights_unqualified", "MRI model assets are not qualified",
                                        runtime_qualified=True)
    if source is None:
        return MRIProviderQualification(
            "study_binding_pending", "MRI runtime and weights verified; study binding and execution are pending",
            runtime_qualified=True, weights_qualified=True)
    try:
        if source_check is None:
            from .mri_source_qualification import qualify_mri_stored_source
            source_check = qualify_mri_stored_source
        qualified, _ = source_check(source)
        if qualified is not True or getattr(source, "modality", None) != "MR":
            return MRIProviderQualification("source_unqualified", "The selected MRI source is not qualified",
                                            runtime_qualified=True, weights_qualified=True)
    except (OSError, ValueError, TypeError, RuntimeError):
        return MRIProviderQualification("source_unqualified", "The selected MRI source is not qualified",
                                        runtime_qualified=True, weights_qualified=True)
    return MRIProviderQualification(
        "prerequisites_qualified_execution_blocked",
        "MRI prerequisites verified; worker binding and real execution are not yet authorized",
        runtime_qualified=True, weights_qualified=True, source_qualified=True,
        prerequisites_qualified=True, execution_authorized=False,
    )


def build_mri_model_descriptor(*, data_dir: Path, python_executable: str | None,
                               qualification: MRIProviderQualification | None = None) -> SegmentationModelDescriptor:
    """Register descriptive MR identity, never an executable provider in C4A."""
    result = qualification if qualification is not None else qualify_mri_provider(
        data_dir=data_dir, python_executable=python_executable)
    if not isinstance(result, MRIProviderQualification) or result.execution_authorized:
        raise ValueError("C4A cannot register an executable MRI provider")
    return SegmentationModelDescriptor(
        provider_id="totalsegmentator", provider_version="2.18.0",
        model_id="total_mr", model_version="2.18.0",
        display_name="TotalSegmentator MRI total_mr task", task="multi_structure",
        capabilities=("anatomical_segmentation",), supported_modalities=("MR",),
        available=False, availability_reason=result.reason,
        execution=SegmentationExecutionRequirements(supported_devices=("cuda",),
                                                     minimum_cuda_memory_mib=0),
    )


def build_mri_execution_descriptor(
    *, qualification: MRIProviderQualification,
) -> SegmentationModelDescriptor:
    """Build the normal-app MRI descriptor only after runtime and sealed weights pass.

    Source/study qualification is intentionally not cached in this descriptor; the
    workflow and provider re-check the current immutable MR source before execution.
    """
    if (
        not isinstance(qualification, MRIProviderQualification)
        or qualification.runtime_qualified is not True
        or qualification.weights_qualified is not True
        or qualification.execution_authorized is not False
    ):
        raise ValueError("MRI execution descriptor requires qualified runtime and weights")
    return SegmentationModelDescriptor(
        provider_id="totalsegmentator", provider_version="2.18.0",
        model_id="total_mr", model_version="2.18.0",
        display_name="TotalSegmentator MRI total_mr task", task="multi_structure",
        capabilities=("anatomical_segmentation",), supported_modalities=("MR",),
        available=True, availability_reason=None,
        execution=SegmentationExecutionRequirements(
            supported_devices=("cuda",), minimum_cuda_memory_mib=0,
        ),
    )
