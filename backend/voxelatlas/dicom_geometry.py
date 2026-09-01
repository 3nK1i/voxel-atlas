from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, sqrt
from statistics import median
from typing import Iterable


VECTOR_EPSILON = 1e-9
ORIENTATION_COMPONENT_TOLERANCE = 1e-3
ORTHOGONAL_TOLERANCE = 1e-3
PIXEL_SPACING_TOLERANCE_MM = 1e-4
DUPLICATE_POSITION_TOLERANCE_MM = 1e-2
SLICE_SPACING_ABSOLUTE_TOLERANCE_MM = 5e-2
SLICE_SPACING_RELATIVE_TOLERANCE = 5e-2
SLICE_GAP_RATIO = 1.5


@dataclass(frozen=True)
class GeometryIssue:
    code: str
    message: str

    def public_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class GeometryInstance:
    stored_filename: str
    rows: int | None
    columns: int | None
    pixel_spacing: tuple[float, ...] | None
    image_position_patient: tuple[float, ...] | None
    image_orientation_patient: tuple[float, ...] | None
    instance_number: int | None = None
    number_of_frames: int | None = None


@dataclass(frozen=True)
class SeriesGeometryQualification:
    reconstruction_ready: bool
    orientation_label: str | None
    dimensions: tuple[int, int, int] | None
    spacing_mm: tuple[float, float, float] | None
    slice_spacing_mm: float | None
    origin_patient_mm: tuple[float, float, float] | None
    row_direction: tuple[float, float, float] | None
    column_direction: tuple[float, float, float] | None
    slice_normal: tuple[float, float, float] | None
    slice_position_range_mm: tuple[float, float] | None
    ordered_instance_filenames: tuple[str, ...]
    issues: tuple[GeometryIssue, ...]

    def manifest_dict(self) -> dict[str, object]:
        return asdict(self)

    def public_dict(self) -> dict[str, object]:
        return {
            "reconstruction_ready": self.reconstruction_ready,
            "orientation_label": self.orientation_label,
            "dimensions": list(self.dimensions) if self.dimensions else None,
            "spacing_mm": list(self.spacing_mm) if self.spacing_mm else None,
            "slice_spacing_mm": self.slice_spacing_mm,
            "origin_patient_mm": list(self.origin_patient_mm) if self.origin_patient_mm else None,
            "row_direction": list(self.row_direction) if self.row_direction else None,
            "column_direction": list(self.column_direction) if self.column_direction else None,
            "slice_normal": list(self.slice_normal) if self.slice_normal else None,
            "slice_position_range_mm": (
                list(self.slice_position_range_mm) if self.slice_position_range_mm else None
            ),
            "issues": [issue.public_dict() for issue in self.issues],
        }


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(value: tuple[float, float, float]) -> float:
    return sqrt(_dot(value, value))


def _normalized(
    value: tuple[float, float, float]
) -> tuple[float, float, float] | None:
    length = _norm(value)
    if length <= VECTOR_EPSILON:
        return None
    return tuple(component / length for component in value)  # type: ignore[return-value]


def _orientation_vectors(
    orientation: tuple[float, ...] | None,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
] | None:
    if orientation is None or len(orientation) != 6:
        return None
    row = _normalized((orientation[0], orientation[1], orientation[2]))
    column = _normalized((orientation[3], orientation[4], orientation[5]))
    if row is None or column is None:
        return None
    if abs(_dot(row, column)) > ORTHOGONAL_TOLERANCE:
        return None
    normal = _normalized(_cross(row, column))
    if normal is None:
        return None
    return row, column, normal


def _close_tuple(a: tuple[float, ...], b: tuple[float, ...], tolerance: float) -> bool:
    return len(a) == len(b) and all(abs(left - right) <= tolerance for left, right in zip(a, b))


def _orientation_label(normal: tuple[float, float, float]) -> str:
    components = [abs(normal[0]), abs(normal[1]), abs(normal[2])]
    dominant = max(range(3), key=components.__getitem__)
    if components[dominant] < 0.9:
        return "oblique"
    return ("sagittal", "coronal", "axial")[dominant]


def qualify_series_geometry(
    instances: Iterable[GeometryInstance],
) -> SeriesGeometryQualification:
    items = tuple(instances)
    issues: list[GeometryIssue] = []

    if len(items) < 2:
        issues.append(
            GeometryIssue(
                "insufficient_slices",
                "At least two image slices are required for volume reconstruction",
            )
        )

    if any((item.number_of_frames or 1) > 1 for item in items):
        issues.append(
            GeometryIssue(
                "multiframe_not_qualified",
                "Enhanced multi-frame DICOM geometry is not qualified in this phase",
            )
        )

    matrices = {(item.rows, item.columns) for item in items}
    if any(row is None or column is None or row <= 0 or column <= 0 for row, column in matrices):
        issues.append(GeometryIssue("missing_matrix", "Rows and Columns are required on every slice"))
    elif len(matrices) > 1:
        issues.append(
            GeometryIssue(
                "inconsistent_matrix",
                "Rows and Columns are not consistent across the DICOM series",
            )
        )

    spacing_values: list[tuple[float, float]] = []
    missing_spacing = False
    for item in items:
        spacing = item.pixel_spacing
        if spacing is None or len(spacing) < 2:
            missing_spacing = True
            continue
        pair = (float(spacing[0]), float(spacing[1]))
        if not all(isfinite(value) for value in pair) or pair[0] <= 0 or pair[1] <= 0:
            missing_spacing = True
            continue
        spacing_values.append(pair)
    if missing_spacing or len(spacing_values) != len(items):
        issues.append(
            GeometryIssue("missing_pixel_spacing", "Valid PixelSpacing is required on every slice")
        )
    elif any(
        not _close_tuple(spacing_values[0], value, PIXEL_SPACING_TOLERANCE_MM)
        for value in spacing_values[1:]
    ):
        issues.append(
            GeometryIssue(
                "inconsistent_pixel_spacing",
                "PixelSpacing is not consistent across the DICOM series",
            )
        )

    orientation_vectors = [_orientation_vectors(item.image_orientation_patient) for item in items]
    if any(value is None for value in orientation_vectors):
        issues.append(
            GeometryIssue(
                "missing_image_orientation",
                "Valid ImageOrientationPatient is required on every slice",
            )
        )
        reference_vectors = None
    else:
        reference_vectors = orientation_vectors[0]
        assert reference_vectors is not None
        reference_flat = reference_vectors[0] + reference_vectors[1]
        for value in orientation_vectors[1:]:
            assert value is not None
            candidate_flat = value[0] + value[1]
            # A global sign flip represents a different row/column direction and must not
            # silently enter a canonical volume stack.
            if not _close_tuple(
                reference_flat,
                candidate_flat,
                ORIENTATION_COMPONENT_TOLERANCE,
            ):
                issues.append(
                    GeometryIssue(
                        "inconsistent_orientation",
                        "ImageOrientationPatient is not consistent across the DICOM series",
                    )
                )
                break

    positions: list[tuple[float, float, float]] = []
    missing_position = False
    for item in items:
        raw = item.image_position_patient
        if raw is None or len(raw) != 3:
            missing_position = True
            continue
        position = (float(raw[0]), float(raw[1]), float(raw[2]))
        if not all(isfinite(value) for value in position):
            missing_position = True
            continue
        positions.append(position)
    if missing_position or len(positions) != len(items):
        issues.append(
            GeometryIssue(
                "missing_image_position",
                "ImagePositionPatient is required on every slice",
            )
        )

    ordered_names: tuple[str, ...] = tuple(
        item.stored_filename
        for item in sorted(
            items,
            key=lambda item: (
                item.instance_number is None,
                item.instance_number or 0,
                item.stored_filename,
            ),
        )
    )
    slice_spacing: float | None = None
    position_range: tuple[float, float] | None = None
    origin: tuple[float, float, float] | None = None
    row_direction = column_direction = normal = None
    orientation_label: str | None = None

    if reference_vectors is not None and not missing_position and len(positions) == len(items):
        row_direction, column_direction, normal = reference_vectors
        projected = [
            (_dot(position, normal), item.stored_filename, position)
            for item, position in zip(items, positions)
        ]
        projected.sort(key=lambda value: (value[0], value[1]))
        ordered_names = tuple(value[1] for value in projected)
        coordinates = [value[0] for value in projected]
        origin = projected[0][2] if projected else None
        if coordinates:
            position_range = (coordinates[0], coordinates[-1])
        orientation_label = _orientation_label(normal)

        if projected:
            base_position = projected[0][2]
            base_coordinate = projected[0][0]
            for coordinate, _, position in projected[1:]:
                delta = (
                    position[0] - base_position[0],
                    position[1] - base_position[1],
                    position[2] - base_position[2],
                )
                expected_along_normal = coordinate - base_coordinate
                residual = (
                    delta[0] - normal[0] * expected_along_normal,
                    delta[1] - normal[1] * expected_along_normal,
                    delta[2] - normal[2] * expected_along_normal,
                )
                if _norm(residual) > 0.1:
                    issues.append(
                        GeometryIssue(
                            "in_plane_slice_drift",
                            "Slice origins drift within the image plane; tilted/sheared "
                            "stacking requires resampling",
                        )
                    )
                    break

        differences = [
            coordinates[index + 1] - coordinates[index]
            for index in range(len(coordinates) - 1)
        ]
        if any(abs(value) <= DUPLICATE_POSITION_TOLERANCE_MM for value in differences):
            issues.append(
                GeometryIssue(
                    "duplicate_slice_position",
                    "Two or more slices occupy the same geometric patient position",
                )
            )
        positive_differences = [value for value in differences if value > DUPLICATE_POSITION_TOLERANCE_MM]
        if positive_differences:
            slice_spacing = float(median(positive_differences))
            tolerance = max(
                SLICE_SPACING_ABSOLUTE_TOLERANCE_MM,
                abs(slice_spacing) * SLICE_SPACING_RELATIVE_TOLERANCE,
            )
            if any(abs(value - slice_spacing) > tolerance for value in positive_differences):
                issues.append(
                    GeometryIssue(
                        "irregular_slice_spacing",
                        "Slice spacing is not sufficiently regular for canonical volume construction",
                    )
                )
            if len(positive_differences) >= 2 and max(positive_differences) > slice_spacing * SLICE_GAP_RATIO:
                issues.append(
                    GeometryIssue(
                        "slice_gap_detected",
                        "A probable gap was detected in the geometric slice stack",
                    )
                )

    rows: int | None = None
    columns: int | None = None
    if items and items[0].rows is not None and items[0].columns is not None:
        rows = int(items[0].rows)
        columns = int(items[0].columns)

    pixel_spacing: tuple[float, float] | None = spacing_values[0] if spacing_values else None
    dimensions = (rows, columns, len(items)) if rows and columns else None
    spacing_mm = (
        (pixel_spacing[0], pixel_spacing[1], slice_spacing)
        if pixel_spacing is not None and slice_spacing is not None
        else None
    )

    return SeriesGeometryQualification(
        reconstruction_ready=not issues,
        orientation_label=orientation_label,
        dimensions=dimensions,
        spacing_mm=spacing_mm,
        slice_spacing_mm=slice_spacing,
        origin_patient_mm=origin,
        row_direction=row_direction,
        column_direction=column_direction,
        slice_normal=normal,
        slice_position_range_mm=position_range,
        ordered_instance_filenames=ordered_names,
        issues=tuple(issues),
    )
