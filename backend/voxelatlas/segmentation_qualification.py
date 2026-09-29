from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Callable, Mapping, Sequence

from .dicom_mpr import CanonicalMprService
from .segmentation import SegmentationValidationError
from .segmentation_corrections import SegmentationCorrectionService
from .segmentation_label_maps import SegmentationLabelMapService
from .segmentation_overlays import SegmentationOverlayImage, SegmentationOverlayService
from .segmentation_surfaces import SegmentationSurface, SegmentationSurfaceService


PHASE5_QUALIFICATION_SCHEMA_VERSION = 1
_PLANES = ("axial", "coronal", "sagittal")


@dataclass(frozen=True)
class Phase5QualificationBudget:
    metadata_seconds: float = 10.0
    overlays_seconds: float = 30.0
    surface_seconds: float = 30.0

    def __post_init__(self) -> None:
        for value in (
            self.metadata_seconds,
            self.overlays_seconds,
            self.surface_seconds,
        ):
            if not isfinite(value) or value <= 0:
                raise ValueError("Phase 5 qualification budgets must be positive")


def _number(value: object, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise SegmentationValidationError(f"{field} is invalid") from exc
    if not isfinite(result):
        raise SegmentationValidationError(f"{field} is invalid")
    return result


def _patient_bounds(descriptor: Mapping[str, object]) -> tuple[float, ...]:
    raw = descriptor.get("patient_bounds_lps_mm")
    if not isinstance(raw, Mapping):
        raise SegmentationValidationError("MPR patient bounds are invalid")
    bounds: list[float] = []
    for axis in ("x", "y", "z"):
        interval = raw.get(axis)
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise SegmentationValidationError("MPR patient bounds are invalid")
        low = _number(interval[0], "MPR patient bounds")
        high = _number(interval[1], "MPR patient bounds")
        if low > high:
            raise SegmentationValidationError("MPR patient bounds are invalid")
        bounds.extend((low, high))
    return tuple(bounds)


def _canonical_affine_bounds(
    descriptor: Mapping[str, object], *, voxel_cells: bool
) -> tuple[float, float, float, float, float, float]:
    raw_shape = descriptor.get("shape")
    raw_affine = descriptor.get("array_index_to_patient_lps")
    if (
        not isinstance(raw_shape, (list, tuple))
        or len(raw_shape) != 3
        or any(
            isinstance(item, bool) or not isinstance(item, int) or item <= 0
            for item in raw_shape
        )
        or not isinstance(raw_affine, (list, tuple))
        or len(raw_affine) != 4
    ):
        raise SegmentationValidationError("Canonical label-map geometry is invalid")
    affine: list[list[float]] = []
    for row in raw_affine:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            raise SegmentationValidationError("Canonical label-map geometry is invalid")
        affine.append([_number(value, "Canonical label-map affine") for value in row])
    if any(abs(affine[3][index] - expected) > 1e-10 for index, expected in enumerate((0.0, 0.0, 0.0, 1.0))):
        raise SegmentationValidationError("Canonical label-map geometry is invalid")
    basis = [row[:3] for row in affine[:3]]
    determinant = (
        basis[0][0] * (basis[1][1] * basis[2][2] - basis[1][2] * basis[2][1])
        - basis[0][1] * (basis[1][0] * basis[2][2] - basis[1][2] * basis[2][0])
        + basis[0][2] * (basis[1][0] * basis[2][1] - basis[1][1] * basis[2][0])
    )
    if abs(determinant) <= 1e-12:
        raise SegmentationValidationError("Canonical label-map geometry is invalid")

    limits = [
        (-0.5, float(size) - 0.5) if voxel_cells else (0.0, float(size) - 1.0)
        for size in raw_shape
    ]
    points: list[tuple[float, float, float]] = []
    for first in limits[0]:
        for second in limits[1]:
            for third in limits[2]:
                index = (first, second, third)
                points.append(
                    tuple(
                        sum(basis[axis][column] * index[column] for column in range(3))
                        + affine[axis][3]
                        for axis in range(3)
                    )
                )
    minimum = tuple(min(point[axis] for point in points) for axis in range(3))
    maximum = tuple(max(point[axis] for point in points) for axis in range(3))
    return (*minimum, *maximum)


def _candidate_inventory(
    candidates: Sequence[Mapping[str, object]], *, study_id: str
) -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for candidate in candidates:
        if candidate.get("source_study_id") != study_id:
            raise SegmentationValidationError("Model comparison study identity is invalid")
        identity = tuple(
            str(candidate.get(field) or "")
            for field in (
                "provider_id",
                "provider_version",
                "model_id",
                "model_version",
                "label_map_id",
            )
        )
        if any(not value for value in identity):
            raise SegmentationValidationError("Model comparison identity is invalid")
        if identity in seen:
            continue
        seen.add(identity)
        labels = candidate.get("present_labels")
        if not isinstance(labels, list):
            raise SegmentationValidationError("Model comparison label inventory is invalid")
        inventory.append(
            {
                "provider_id": identity[0],
                "provider_version": identity[1],
                "model_id": identity[2],
                "model_version": identity[3],
                "label_map_id": identity[4],
                "present_label_count": len([item for item in labels if item != 0]),
                "nonzero_voxels": int(candidate.get("nonzero_voxels") or 0),
            }
        )
    inventory.sort(
        key=lambda item: (
            str(item["provider_id"]),
            str(item["model_id"]),
            str(item["model_version"]),
            str(item["label_map_id"]),
        )
    )
    if not inventory:
        raise SegmentationValidationError("No model comparison candidate is available")
    return inventory


def validate_phase5_closure(
    *,
    label_map: Mapping[str, object],
    overlay_descriptor: Mapping[str, object],
    mpr_descriptor: Mapping[str, object],
    overlay_images: Mapping[str, SegmentationOverlayImage],
    surface: SegmentationSurface,
    quality_report: Mapping[str, object],
    timings_seconds: Mapping[str, float],
    model_candidates: Sequence[Mapping[str, object]],
    budget: Phase5QualificationBudget = Phase5QualificationBudget(),
) -> dict[str, object]:
    """Validate the complete non-clinical Phase 5 presentation chain."""
    study_id = str(label_map.get("source_study_id") or "")
    label_map_id = str(label_map.get("label_map_id") or "")
    artifact_sha256 = str(label_map.get("artifact_sha256") or "")
    if not study_id or not label_map_id or len(artifact_sha256) != 64:
        raise SegmentationValidationError("Canonical label-map identity is invalid")
    if (
        label_map.get("source_modality") != "CT"
        or label_map.get("coordinate_system") != "patient_lps"
        or label_map.get("resampled") is not False
        or label_map.get("interpolation") != "none"
        or label_map.get("clinical_validation") != "not_claimed"
    ):
        raise SegmentationValidationError("Canonical label-map qualification contract is invalid")

    if (
        overlay_descriptor.get("ready") is not True
        or overlay_descriptor.get("source_study_id") != study_id
        or quality_report.get("source_study_id") != study_id
    ):
        raise SegmentationValidationError("Phase 5 study identity is inconsistent")
    if (
        overlay_descriptor.get("label_map_id") != label_map_id
        or quality_report.get("label_map_id") != label_map_id
        or surface.label_map_id != label_map_id
        or overlay_descriptor.get("label_map_sha256") != artifact_sha256
        or quality_report.get("label_map_sha256") != artifact_sha256
    ):
        raise SegmentationValidationError("Phase 5 label-map provenance is inconsistent")
    if (
        overlay_descriptor.get("coordinate_system") != "patient_lps"
        or overlay_descriptor.get("sampling") != "nearest_neighbor"
        or surface.coordinate_system != "patient_lps"
        or quality_report.get("source_label_map") != "immutable"
    ):
        raise SegmentationValidationError("Patient LPS presentation contract is invalid")
    if quality_report.get("clinical_validation") != "not_claimed":
        raise SegmentationValidationError("Clinical validation must not be claimed")

    raw_planes = mpr_descriptor.get("planes")
    if mpr_descriptor.get("ready") is not True or not isinstance(raw_planes, Mapping):
        raise SegmentationValidationError("MPR qualification descriptor is invalid")
    plane_evidence: list[dict[str, object]] = []
    for plane in _PLANES:
        plane_descriptor = raw_planes.get(plane)
        image = overlay_images.get(plane)
        if not isinstance(plane_descriptor, Mapping) or not isinstance(
            image, SegmentationOverlayImage
        ):
            raise SegmentationValidationError("Three-plane overlay evidence is incomplete")
        width = int(plane_descriptor.get("image_width") or 0)
        height = int(plane_descriptor.get("image_height") or 0)
        if image.plane != plane or image.width != width or image.height != height:
            raise SegmentationValidationError("Segmentation overlay dimensions are invalid")
        if image.label_map_id != label_map_id or len(image.pixels) != width * height * 4:
            raise SegmentationValidationError("Segmentation overlay artifact is invalid")
        plane_evidence.append(
            {
                "plane": plane,
                "index": image.index,
                "width": width,
                "height": height,
                "rgba_sha256": sha256(image.pixels).hexdigest(),
            }
        )

    bounds = _patient_bounds(mpr_descriptor)
    center_bounds = _canonical_affine_bounds(label_map, voxel_cells=False)
    for axis in range(3):
        if (
            abs(bounds[axis * 2] - center_bounds[axis]) > 1e-3
            or abs(bounds[axis * 2 + 1] - center_bounds[axis + 3]) > 1e-3
        ):
            raise SegmentationValidationError(
                "MPR center bounds do not match the canonical label map"
            )
    cell_bounds = _canonical_affine_bounds(label_map, voxel_cells=True)
    surface_bounds = tuple(_number(value, "Segmentation surface bounds") for value in surface.bounds_lps_mm)
    if len(surface_bounds) != 6:
        raise SegmentationValidationError("Segmentation surface bounds are invalid")
    volume_minimum = cell_bounds[:3]
    volume_maximum = cell_bounds[3:]
    for axis in range(3):
        if (
            surface_bounds[axis] < volume_minimum[axis] - 1e-3
            or surface_bounds[axis + 3] > volume_maximum[axis] + 1e-3
            or surface_bounds[axis] > surface_bounds[axis + 3]
        ):
            raise SegmentationValidationError("Segmentation surface bounds exceed the patient volume")
    if surface.vertex_count <= 0 or surface.triangle_count <= 0:
        raise SegmentationValidationError("Segmentation surface geometry is empty")

    limits = {
        "metadata": budget.metadata_seconds,
        "overlays": budget.overlays_seconds,
        "surface": budget.surface_seconds,
    }
    normalized_timings: dict[str, float] = {}
    for key, limit in limits.items():
        elapsed = _number(timings_seconds.get(key), f"{key} timing")
        if elapsed < 0 or elapsed > limit:
            raise SegmentationValidationError(f"Phase 5 {key} performance budget was exceeded")
        normalized_timings[key] = elapsed

    candidates = _candidate_inventory(model_candidates, study_id=study_id)
    return {
        "schema_version": PHASE5_QUALIFICATION_SCHEMA_VERSION,
        "status": "qualified",
        "source_study_id": study_id,
        "label_map_id": label_map_id,
        "label_map_sha256": artifact_sha256,
        "provider_id": label_map["provider_id"],
        "provider_version": label_map["provider_version"],
        "model_id": label_map["model_id"],
        "model_version": label_map["model_version"],
        "present_label_count": len([item for item in label_map["present_labels"] if item != 0]),
        "qualified_label_id": surface.label_id,
        "geometry_chain": "pass",
        "surface_containment": "canonical_voxel_cell_bounds",
        "overlay_plane_count": len(plane_evidence),
        "overlay_planes": plane_evidence,
        "surface_vertex_count": surface.vertex_count,
        "surface_triangle_count": surface.triangle_count,
        "surface_payload_sha256": surface.payload_sha256,
        "quality_warning_count": int(quality_report.get("warning_count") or 0),
        "timings_seconds": normalized_timings,
        "performance_budget": "pass",
        "model_comparison_candidate_count": len(candidates),
        "model_comparison_candidates": candidates,
        "model_comparison_ranking": "not_claimed",
        "source_label_map": "immutable",
        "clinical_validation": "not_claimed",
    }


class Phase5QualificationService:
    def __init__(
        self,
        *,
        data_dir: Path,
        budget: Phase5QualificationBudget = Phase5QualificationBudget(),
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.budget = budget
        self.clock = clock
        self.label_maps = SegmentationLabelMapService(data_dir=self.data_dir)
        self.mpr = CanonicalMprService(data_dir=self.data_dir)
        self.overlays = SegmentationOverlayService(
            data_dir=self.data_dir,
            mpr_service=self.mpr,
            label_map_service=self.label_maps,
        )
        self.surfaces = SegmentationSurfaceService(
            data_dir=self.data_dir,
            label_map_service=self.label_maps,
        )
        self.corrections = SegmentationCorrectionService(
            data_dir=self.data_dir,
            label_map_service=self.label_maps,
        )

    def qualify(
        self, *, label_map_id: str, label_id: int = 91, quality: str = "preview"
    ) -> dict[str, object]:
        started = self.clock()
        label_map = self.label_maps.get(label_map_id)
        overlay_descriptor = self.overlays.descriptor_latest(label_map_id=label_map_id)
        mpr_descriptor = self.mpr.descriptor_latest()
        candidates = self.label_maps.list(study_id=str(label_map["source_study_id"]))
        metadata_seconds = self.clock() - started

        raw_planes = mpr_descriptor.get("planes")
        if not isinstance(raw_planes, Mapping):
            raise SegmentationValidationError("MPR qualification descriptor is invalid")
        started = self.clock()
        images: dict[str, SegmentationOverlayImage] = {}
        for plane in _PLANES:
            descriptor = raw_planes.get(plane)
            if not isinstance(descriptor, Mapping):
                raise SegmentationValidationError("MPR qualification plane is invalid")
            index = int(descriptor["slice_count"]) // 2
            images[plane] = self.overlays.render_latest(
                plane, index=index, label_map_id=label_map_id
            )
        overlays_seconds = self.clock() - started

        started = self.clock()
        surface = self.surfaces.surface_latest(
            label_id=label_id,
            label_map_id=label_map_id,
            quality=quality,
        )
        quality_report = self.corrections.quality_report(
            label_map_id=label_map_id, label_id=label_id
        )
        surface_seconds = self.clock() - started
        return validate_phase5_closure(
            label_map=label_map,
            overlay_descriptor=overlay_descriptor,
            mpr_descriptor=mpr_descriptor,
            overlay_images=images,
            surface=surface,
            quality_report=quality_report,
            timings_seconds={
                "metadata": metadata_seconds,
                "overlays": overlays_seconds,
                "surface": surface_seconds,
            },
            model_candidates=candidates,
            budget=self.budget,
        )
