from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import BinaryIO, Callable, Iterable, Protocol
from uuid import uuid4

from .dicom_geometry import (
    GeometryInstance,
    SeriesGeometryQualification,
    qualify_series_geometry,
)


CHUNK_SIZE = 1024 * 1024
MAX_UPLOAD_FILES = 10000
MANIFEST_SCHEMA_VERSION = 2
SUPPORTED_MODALITIES = {"CT", "MR"}


class DicomIngestionError(ValueError):
    """Base class for safe, user-facing DICOM ingestion failures."""


class DicomDependencyUnavailable(DicomIngestionError):
    pass


class DicomUploadLimitExceeded(DicomIngestionError):
    pass


class DicomStudyValidationError(DicomIngestionError):
    pass


class UploadPart(Protocol):
    filename: str | None
    file: BinaryIO


@dataclass(frozen=True)
class DicomHeader:
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    modality: str
    sop_class_uid: str | None = None
    study_date: str | None = None
    study_description: str | None = None
    series_number: int | None = None
    series_description: str | None = None
    manufacturer: str | None = None
    manufacturer_model: str | None = None
    rows: int | None = None
    columns: int | None = None
    pixel_spacing: tuple[float, ...] | None = None
    slice_thickness: float | None = None
    spacing_between_slices: float | None = None
    instance_number: int | None = None
    image_position_patient: tuple[float, ...] | None = None
    image_orientation_patient: tuple[float, ...] | None = None
    number_of_frames: int | None = None


@dataclass(frozen=True)
class DicomInstanceDescriptor:
    stored_filename: str
    sop_instance_uid: str
    sha256: str
    size_bytes: int
    instance_number: int | None
    image_position_patient: tuple[float, ...] | None
    image_orientation_patient: tuple[float, ...] | None
    rows: int | None = None
    columns: int | None = None
    pixel_spacing: tuple[float, ...] | None = None
    number_of_frames: int | None = None


@dataclass(frozen=True)
class DicomSeriesDescriptor:
    series_instance_uid: str
    modality: str
    series_number: int | None
    series_description: str | None
    manufacturer: str | None
    manufacturer_model: str | None
    rows: int | None
    columns: int | None
    pixel_spacing: tuple[float, ...] | None
    slice_thickness: float | None
    spacing_between_slices: float | None
    instance_count: int
    instances: tuple[DicomInstanceDescriptor, ...]
    geometry: SeriesGeometryQualification | None = None

    def public_dict(self) -> dict[str, object]:
        return {
            "series_instance_uid": self.series_instance_uid,
            "modality": self.modality,
            "series_number": self.series_number,
            "series_description": self.series_description,
            "manufacturer": self.manufacturer,
            "manufacturer_model": self.manufacturer_model,
            "rows": self.rows,
            "columns": self.columns,
            "pixel_spacing": list(self.pixel_spacing) if self.pixel_spacing else None,
            "slice_thickness": self.slice_thickness,
            "spacing_between_slices": self.spacing_between_slices,
            "instance_count": self.instance_count,
            "geometry": self.geometry.public_dict() if self.geometry else None,
        }


@dataclass(frozen=True)
class DicomStudyDescriptor:
    schema_version: int
    study_id: str
    study_instance_uid: str
    created_at_utc: str
    study_date: str | None
    study_description: str | None
    modalities: tuple[str, ...]
    file_count: int
    skipped_file_count: int
    series_count: int
    primary_series_uid: str
    series: tuple[DicomSeriesDescriptor, ...]
    reconstruction_ready: bool = False
    reconstruction_series_uid: str | None = None

    def manifest_dict(self) -> dict[str, object]:
        return asdict(self)

    def public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "study_instance_uid": self.study_instance_uid,
            "created_at_utc": self.created_at_utc,
            "study_date": self.study_date,
            "study_description": self.study_description,
            "modalities": list(self.modalities),
            "file_count": self.file_count,
            "skipped_file_count": self.skipped_file_count,
            "series_count": self.series_count,
            "primary_series_uid": self.primary_series_uid,
            "reconstruction_ready": self.reconstruction_ready,
            "reconstruction_series_uid": self.reconstruction_series_uid,
            "series": [item.public_dict() for item in self.series],
        }


HeaderReader = Callable[[Path], DicomHeader | None]


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_int(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_float(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_float_tuple(value: object) -> tuple[float, ...] | None:
    if value is None:
        return None
    try:
        values = tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return values or None


def read_dicom_header(path: Path) -> DicomHeader | None:
    """Read metadata only. Pixel data is deliberately excluded in Phase 3A."""
    try:
        import pydicom
        from pydicom.errors import InvalidDicomError
    except ModuleNotFoundError as exc:
        raise DicomDependencyUnavailable(
            "DICOM ingestion requires the pydicom backend dependency"
        ) from exc

    wanted = [
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "SOPInstanceUID",
        "SOPClassUID",
        "Modality",
        "StudyDate",
        "StudyDescription",
        "SeriesNumber",
        "SeriesDescription",
        "Manufacturer",
        "ManufacturerModelName",
        "Rows",
        "Columns",
        "PixelSpacing",
        "SliceThickness",
        "SpacingBetweenSlices",
        "InstanceNumber",
        "ImagePositionPatient",
        "ImageOrientationPatient",
        "NumberOfFrames",
    ]

    try:
        dataset = pydicom.dcmread(
            str(path),
            stop_before_pixels=True,
            specific_tags=wanted,
            force=False,
        )
    except (InvalidDicomError, OSError, ValueError):
        return None

    study_uid = _clean_text(getattr(dataset, "StudyInstanceUID", None))
    series_uid = _clean_text(getattr(dataset, "SeriesInstanceUID", None))
    sop_uid = _clean_text(getattr(dataset, "SOPInstanceUID", None))
    modality = _clean_text(getattr(dataset, "Modality", None))

    # DICOMDIR and non-image objects may be valid DICOM but do not belong to
    # a reconstructable Study/Series instance. Ignore them safely.
    if not all((study_uid, series_uid, sop_uid, modality)):
        return None

    return DicomHeader(
        study_instance_uid=study_uid,
        series_instance_uid=series_uid,
        sop_instance_uid=sop_uid,
        modality=modality.upper(),
        sop_class_uid=_clean_text(getattr(dataset, "SOPClassUID", None)),
        study_date=_clean_text(getattr(dataset, "StudyDate", None)),
        study_description=_clean_text(getattr(dataset, "StudyDescription", None)),
        series_number=_clean_int(getattr(dataset, "SeriesNumber", None)),
        series_description=_clean_text(getattr(dataset, "SeriesDescription", None)),
        manufacturer=_clean_text(getattr(dataset, "Manufacturer", None)),
        manufacturer_model=_clean_text(getattr(dataset, "ManufacturerModelName", None)),
        rows=_clean_int(getattr(dataset, "Rows", None)),
        columns=_clean_int(getattr(dataset, "Columns", None)),
        pixel_spacing=_clean_float_tuple(getattr(dataset, "PixelSpacing", None)),
        slice_thickness=_clean_float(getattr(dataset, "SliceThickness", None)),
        spacing_between_slices=_clean_float(
            getattr(dataset, "SpacingBetweenSlices", None)
        ),
        instance_number=_clean_int(getattr(dataset, "InstanceNumber", None)),
        image_position_patient=_clean_float_tuple(
            getattr(dataset, "ImagePositionPatient", None)
        ),
        image_orientation_patient=_clean_float_tuple(
            getattr(dataset, "ImageOrientationPatient", None)
        ),
        number_of_frames=_clean_int(getattr(dataset, "NumberOfFrames", None)),
    )


class DicomStudyRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.studies_dir = self.data_dir / "studies"
        self.staging_dir = self.data_dir / ".staging"

    def ensure_directories(self) -> None:
        self.studies_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def latest_manifest(self) -> dict[str, object] | None:
        if not self.studies_dir.exists():
            return None
        manifests = list(self.studies_dir.glob("*/manifest.json"))
        if not manifests:
            return None
        latest = max(manifests, key=lambda item: item.stat().st_mtime_ns)
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return _manifest_to_public(payload)


def _tuple_floats(value: object) -> tuple[float, ...] | None:
    if not isinstance(value, (list, tuple)):
        return None
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _geometry_from_manifest_series(raw: dict[str, object]) -> SeriesGeometryQualification:
    stored_geometry = raw.get("geometry")
    if isinstance(stored_geometry, dict):
        issues_raw = stored_geometry.get("issues", [])
        from .dicom_geometry import GeometryIssue

        issues = tuple(
            GeometryIssue(str(item.get("code", "geometry_issue")), str(item.get("message", "Geometry issue")))
            for item in issues_raw
            if isinstance(item, dict)
        )
        def tuple3(key: str):
            value = _tuple_floats(stored_geometry.get(key))
            return tuple(value[:3]) if value and len(value) >= 3 else None
        dimensions_raw = stored_geometry.get("dimensions")
        dimensions = None
        if isinstance(dimensions_raw, (list, tuple)) and len(dimensions_raw) == 3:
            try:
                dimensions = tuple(int(item) for item in dimensions_raw)
            except (TypeError, ValueError):
                dimensions = None
        spacing_raw = _tuple_floats(stored_geometry.get("spacing_mm"))
        position_range_raw = _tuple_floats(stored_geometry.get("slice_position_range_mm"))
        ordered = stored_geometry.get("ordered_instance_filenames", [])
        return SeriesGeometryQualification(
            reconstruction_ready=bool(stored_geometry.get("reconstruction_ready")),
            orientation_label=_clean_text(stored_geometry.get("orientation_label")),
            dimensions=dimensions,
            spacing_mm=tuple(spacing_raw[:3]) if spacing_raw and len(spacing_raw) >= 3 else None,
            slice_spacing_mm=_clean_float(stored_geometry.get("slice_spacing_mm")),
            origin_patient_mm=tuple3("origin_patient_mm"),
            row_direction=tuple3("row_direction"),
            column_direction=tuple3("column_direction"),
            slice_normal=tuple3("slice_normal"),
            slice_position_range_mm=(
                tuple(position_range_raw[:2]) if position_range_raw and len(position_range_raw) >= 2 else None
            ),
            ordered_instance_filenames=(
                tuple(str(item) for item in ordered) if isinstance(ordered, list) else ()
            ),
            issues=issues,
        )

    rows = _int_or_none(raw.get("rows"))
    columns = _int_or_none(raw.get("columns"))
    series_spacing = _tuple_floats(raw.get("pixel_spacing"))
    instances: list[GeometryInstance] = []
    for instance in raw.get("instances", []):
        if not isinstance(instance, dict):
            continue
        instances.append(
            GeometryInstance(
                stored_filename=str(instance.get("stored_filename") or "unknown.dcm"),
                rows=_int_or_none(instance.get("rows")) or rows,
                columns=_int_or_none(instance.get("columns")) or columns,
                pixel_spacing=_tuple_floats(instance.get("pixel_spacing")) or series_spacing,
                image_position_patient=_tuple_floats(instance.get("image_position_patient")),
                image_orientation_patient=_tuple_floats(instance.get("image_orientation_patient")),
                instance_number=_int_or_none(instance.get("instance_number")),
                number_of_frames=_int_or_none(instance.get("number_of_frames")) or 1,
            )
        )
    return qualify_series_geometry(instances)


def _manifest_to_public(payload: dict[str, object]) -> dict[str, object]:
    public_series: list[dict[str, object]] = []
    ready_series: list[tuple[int, str]] = []
    for raw in payload.get("series", []):
        if not isinstance(raw, dict):
            continue
        geometry = _geometry_from_manifest_series(raw)
        series_uid = str(raw.get("series_instance_uid") or "")
        instance_count = _int_or_none(raw.get("instance_count")) or 0
        if geometry.reconstruction_ready and series_uid:
            ready_series.append((instance_count, series_uid))
        public_series.append(
            {
                key: raw.get(key)
                for key in (
                    "series_instance_uid",
                    "modality",
                    "series_number",
                    "series_description",
                    "manufacturer",
                    "manufacturer_model",
                    "rows",
                    "columns",
                    "pixel_spacing",
                    "slice_thickness",
                    "spacing_between_slices",
                    "instance_count",
                )
            }
            | {"geometry": geometry.public_dict()}
        )
    derived_reconstruction_uid = (
        max(ready_series, key=lambda item: (item[0], item[1]))[1]
        if ready_series
        else None
    )
    reconstruction_uid = _clean_text(payload.get("reconstruction_series_uid")) or derived_reconstruction_uid
    return {
        key: payload.get(key)
        for key in (
            "schema_version",
            "study_id",
            "study_instance_uid",
            "created_at_utc",
            "study_date",
            "study_description",
            "modalities",
            "file_count",
            "skipped_file_count",
            "series_count",
            "primary_series_uid",
        )
    } | {
        "reconstruction_ready": reconstruction_uid is not None,
        "reconstruction_series_uid": reconstruction_uid,
        "series": public_series,
    }


class DicomIngestionService:
    def __init__(
        self,
        *,
        data_dir: Path,
        max_upload_mib: int,
        header_reader: HeaderReader = read_dicom_header,
        max_files: int = MAX_UPLOAD_FILES,
    ):
        self.repository = DicomStudyRepository(data_dir)
        self.max_upload_bytes = max_upload_mib * 1024 * 1024
        self.header_reader = header_reader
        self.max_files = max_files

    def latest_public_study(self) -> dict[str, object] | None:
        return self.repository.latest_manifest()

    def ingest(self, parts: Iterable[UploadPart]) -> DicomStudyDescriptor:
        uploads = list(parts)
        if not uploads:
            raise DicomStudyValidationError("Select at least one DICOM file")
        if len(uploads) > self.max_files:
            raise DicomStudyValidationError(
                f"Too many files selected; limit is {self.max_files} files"
            )

        self.repository.ensure_directories()
        study_id = uuid4().hex
        stage = self.repository.staging_dir / study_id
        final_dir = self.repository.studies_dir / study_id
        stage.mkdir(parents=False, exist_ok=False)

        try:
            descriptor = self._ingest_into_stage(study_id, stage, uploads)
            manifest_path = stage / "manifest.json"
            manifest_tmp = stage / "manifest.json.tmp"
            manifest_tmp.write_text(
                json.dumps(descriptor.manifest_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            manifest_tmp.replace(manifest_path)
            stage.replace(final_dir)
            return descriptor
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    def _ingest_into_stage(
        self,
        study_id: str,
        stage: Path,
        uploads: list[UploadPart],
    ) -> DicomStudyDescriptor:
        total_bytes = 0
        skipped = 0
        records: list[tuple[DicomHeader, DicomInstanceDescriptor]] = []
        seen_sop_uids: set[str] = set()

        for index, upload in enumerate(uploads, start=1):
            candidate = stage / f"candidate-{index:06d}.dcm"
            digest = sha256()
            size_bytes = 0
            with candidate.open("wb") as output:
                while True:
                    chunk = upload.file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    total_bytes += len(chunk)
                    if total_bytes > self.max_upload_bytes:
                        raise DicomUploadLimitExceeded(
                            "Selected DICOM data exceeds the configured upload limit"
                        )
                    digest.update(chunk)
                    output.write(chunk)

            if size_bytes == 0:
                candidate.unlink(missing_ok=True)
                skipped += 1
                continue

            header = self.header_reader(candidate)
            if header is None or header.modality not in SUPPORTED_MODALITIES:
                candidate.unlink(missing_ok=True)
                skipped += 1
                continue

            if header.sop_instance_uid in seen_sop_uids:
                raise DicomStudyValidationError(
                    "Duplicate SOP Instance UID detected in the selected DICOM data"
                )
            seen_sop_uids.add(header.sop_instance_uid)

            stored_name = f"instance-{len(records) + 1:06d}.dcm"
            candidate.replace(stage / stored_name)
            records.append(
                (
                    header,
                    DicomInstanceDescriptor(
                        stored_filename=stored_name,
                        sop_instance_uid=header.sop_instance_uid,
                        sha256=digest.hexdigest(),
                        size_bytes=size_bytes,
                        instance_number=header.instance_number,
                        image_position_patient=header.image_position_patient,
                        image_orientation_patient=header.image_orientation_patient,
                        rows=header.rows,
                        columns=header.columns,
                        pixel_spacing=header.pixel_spacing,
                        number_of_frames=header.number_of_frames,
                    ),
                )
            )

        if not records:
            raise DicomStudyValidationError(
                "No reconstructable CT/MR DICOM image instances were found"
            )

        study_uids = {header.study_instance_uid for header, _ in records}
        if len(study_uids) != 1:
            raise DicomStudyValidationError(
                "The selected files contain more than one DICOM study"
            )
        study_uid = next(iter(study_uids))

        by_series: dict[str, list[tuple[DicomHeader, DicomInstanceDescriptor]]] = {}
        for record in records:
            by_series.setdefault(record[0].series_instance_uid, []).append(record)

        series_descriptors: list[DicomSeriesDescriptor] = []
        for series_uid, group in by_series.items():
            first = group[0][0]
            geometry = qualify_series_geometry(
                GeometryInstance(
                    stored_filename=descriptor.stored_filename,
                    rows=header.rows,
                    columns=header.columns,
                    pixel_spacing=header.pixel_spacing,
                    image_position_patient=header.image_position_patient,
                    image_orientation_patient=header.image_orientation_patient,
                    instance_number=header.instance_number,
                    number_of_frames=header.number_of_frames or 1,
                )
                for header, descriptor in group
            )
            descriptors_by_name = {descriptor.stored_filename: descriptor for _, descriptor in group}
            if geometry.reconstruction_ready:
                instances = tuple(
                    descriptors_by_name[name]
                    for name in geometry.ordered_instance_filenames
                )
            else:
                instances = tuple(
                    item[1]
                    for item in sorted(
                        group,
                        key=lambda item: (
                            item[0].instance_number is None,
                            item[0].instance_number or 0,
                            item[0].sop_instance_uid,
                        ),
                    )
                )
            series_descriptors.append(
                DicomSeriesDescriptor(
                    series_instance_uid=series_uid,
                    modality=first.modality,
                    series_number=first.series_number,
                    series_description=first.series_description,
                    manufacturer=first.manufacturer,
                    manufacturer_model=first.manufacturer_model,
                    rows=first.rows,
                    columns=first.columns,
                    pixel_spacing=first.pixel_spacing,
                    slice_thickness=first.slice_thickness,
                    spacing_between_slices=first.spacing_between_slices,
                    instance_count=len(instances),
                    instances=instances,
                    geometry=geometry,
                )
            )

        series_descriptors.sort(
            key=lambda item: (
                item.series_number is None,
                item.series_number or 0,
                item.series_instance_uid,
            )
        )
        reconstruction_candidates = [
            item for item in series_descriptors
            if item.geometry is not None and item.geometry.reconstruction_ready
        ]
        primary = max(
            reconstruction_candidates or series_descriptors,
            key=lambda item: (item.instance_count, item.series_instance_uid),
        )
        reconstruction_series_uid = (
            primary.series_instance_uid if reconstruction_candidates else None
        )
        first_header = records[0][0]
        modalities = tuple(sorted({item.modality for item in series_descriptors}))

        return DicomStudyDescriptor(
            schema_version=MANIFEST_SCHEMA_VERSION,
            study_id=study_id,
            study_instance_uid=study_uid,
            created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            study_date=first_header.study_date,
            study_description=first_header.study_description,
            modalities=modalities,
            file_count=len(records),
            skipped_file_count=skipped,
            series_count=len(series_descriptors),
            primary_series_uid=primary.series_instance_uid,
            series=tuple(series_descriptors),
            reconstruction_ready=reconstruction_series_uid is not None,
            reconstruction_series_uid=reconstruction_series_uid,
        )
