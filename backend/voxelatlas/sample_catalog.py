from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import Lock
from typing import BinaryIO

from .dicom_ingestion import DicomIngestionService


SAMPLE_CATALOG_SCHEMA_VERSION = 1
MAX_SAMPLE_STUDIES = 12
MAX_SAMPLE_FILES = 10000
MAX_SAMPLE_BYTES = 4 * 1024 * 1024 * 1024
_SAMPLE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SampleStudyCatalogError(ValueError):
    """Base class for safe sample-catalog failures."""


class SampleStudyNotFoundError(SampleStudyCatalogError):
    pass


class SampleStudyManifestError(SampleStudyCatalogError):
    pass


class SampleStudyIntegrityError(SampleStudyCatalogError):
    pass


@dataclass(frozen=True)
class _LocalUploadPart:
    filename: str
    file: BinaryIO


def _required_text(payload: dict[str, object], key: str, *, maximum: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise SampleStudyManifestError(f"Sample study manifest has invalid {key}")
    text = value.strip()
    if not text or len(text) > maximum or any(ord(character) < 32 for character in text):
        raise SampleStudyManifestError(f"Sample study manifest has invalid {key}")
    return text


def _https_url(payload: dict[str, object], key: str) -> str:
    value = _required_text(payload, key, maximum=2048)
    if not value.startswith("https://") or any(character.isspace() for character in value):
        raise SampleStudyManifestError(f"Sample study manifest has invalid {key}")
    return value


def _bounded_integer(
    payload: dict[str, object],
    key: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        raise SampleStudyManifestError(f"Sample study manifest has invalid {key}")
    try:
        integer = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise SampleStudyManifestError(f"Sample study manifest has invalid {key}") from exc
    if integer < minimum or integer > maximum:
        raise SampleStudyManifestError(f"Sample study manifest has invalid {key}")
    return integer


def _payload_files(dicom_root: Path) -> list[Path]:
    root = Path(dicom_root)
    if not root.is_dir() or root.is_symlink():
        raise SampleStudyIntegrityError("Sample study DICOM payload is unavailable")
    files: list[Path] = []
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise SampleStudyIntegrityError("Sample study payload must not contain symbolic links")
        if candidate.is_file():
            files.append(candidate)
    files.sort(key=lambda item: item.relative_to(root).as_posix())
    if not files:
        raise SampleStudyIntegrityError("Sample study DICOM payload is empty")
    if len(files) > MAX_SAMPLE_FILES:
        raise SampleStudyIntegrityError("Sample study payload contains too many files")
    return files


def compute_sample_payload_digest(dicom_root: Path) -> tuple[str, int, int]:
    root = Path(dicom_root)
    digest = sha256()
    total_bytes = 0
    files = _payload_files(root)
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        total_bytes += size
        if total_bytes > MAX_SAMPLE_BYTES:
            raise SampleStudyIntegrityError("Sample study payload exceeds the catalog size limit")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest(), len(files), total_bytes


@dataclass(frozen=True)
class SampleStudyRecord:
    root: Path
    sample_id: str
    title: str
    summary: str
    modality: str
    body_region: str
    source_label: str
    source_url: str
    license_label: str
    license_url: str
    payload_sha256: str
    file_count: int
    size_bytes: int
    order: int
    featured: bool
    installed_at_utc: str
    preview_path: Path | None

    @property
    def dicom_root(self) -> Path:
        return self.root / "dicom"

    def public_dict(self) -> dict[str, object]:
        preview_available = self.preview_path is not None
        return {
            "sample_id": self.sample_id,
            "title": self.title,
            "summary": self.summary,
            "modality": self.modality,
            "body_region": self.body_region,
            "source_label": self.source_label,
            "source_url": self.source_url,
            "license_label": self.license_label,
            "license_url": self.license_url,
            "file_count": self.file_count,
            "size_bytes": self.size_bytes,
            "featured": self.featured,
            "preview_available": preview_available,
            "preview_url": f"/api/sample-studies/{self.sample_id}/preview" if preview_available else None,
        }

    def origin_dict(self) -> dict[str, object]:
        return {
            "kind": "sample",
            "sample_id": self.sample_id,
            "title": self.title,
            "source_label": self.source_label,
            "source_url": self.source_url,
            "license_label": self.license_label,
            "license_url": self.license_url,
        }


def _load_record(root: Path) -> SampleStudyRecord:
    manifest_path = root / "sample.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise SampleStudyManifestError("Sample study manifest is unavailable")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SampleStudyManifestError("Sample study manifest is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SAMPLE_CATALOG_SCHEMA_VERSION:
        raise SampleStudyManifestError("Sample study manifest schema is unsupported")

    sample_id = _required_text(payload, "sample_id", maximum=64)
    if not _SAMPLE_ID.fullmatch(sample_id) or sample_id != root.name:
        raise SampleStudyManifestError("Sample study manifest has invalid sample_id")
    modality = _required_text(payload, "modality", maximum=2).upper()
    if modality not in {"CT", "MR"}:
        raise SampleStudyManifestError("Sample study manifest has invalid modality")
    payload_sha256 = _required_text(payload, "payload_sha256", maximum=64).lower()
    if not _SHA256.fullmatch(payload_sha256):
        raise SampleStudyManifestError("Sample study manifest has invalid payload_sha256")
    featured = payload.get("featured", False)
    if not isinstance(featured, bool):
        raise SampleStudyManifestError("Sample study manifest has invalid featured")
    preview = root / "preview.png"
    preview_path = None
    if preview.exists():
        if preview.is_symlink() or not preview.is_file():
            raise SampleStudyManifestError("Sample study preview is invalid")
        try:
            if preview.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise SampleStudyManifestError("Sample study preview is not a PNG image")
        except OSError as exc:
            raise SampleStudyManifestError("Sample study preview is unreadable") from exc
        preview_path = preview

    record = SampleStudyRecord(
        root=root,
        sample_id=sample_id,
        title=_required_text(payload, "title", maximum=80),
        summary=_required_text(payload, "summary", maximum=280),
        modality=modality,
        body_region=_required_text(payload, "body_region", maximum=80),
        source_label=_required_text(payload, "source_label", maximum=120),
        source_url=_https_url(payload, "source_url"),
        license_label=_required_text(payload, "license_label", maximum=120),
        license_url=_https_url(payload, "license_url"),
        payload_sha256=payload_sha256,
        file_count=_bounded_integer(payload, "file_count", minimum=1, maximum=MAX_SAMPLE_FILES),
        size_bytes=_bounded_integer(payload, "size_bytes", minimum=1, maximum=MAX_SAMPLE_BYTES),
        order=_bounded_integer(payload, "order", minimum=0, maximum=10000),
        featured=featured,
        installed_at_utc=_required_text(payload, "installed_at_utc", maximum=64),
        preview_path=preview_path,
    )
    if not record.dicom_root.is_dir() or record.dicom_root.is_symlink():
        raise SampleStudyManifestError("Sample study DICOM payload is unavailable")
    return record


class SampleStudyCatalogService:
    def __init__(self, *, data_dir: Path, dicom_service: DicomIngestionService):
        self.catalog_root = Path(data_dir) / "sample_studies"
        self.dicom_service = dicom_service
        self._load_lock = Lock()

    def _records(self) -> list[SampleStudyRecord]:
        if not self.catalog_root.is_dir() or self.catalog_root.is_symlink():
            return []
        records: list[SampleStudyRecord] = []
        for root in sorted(self.catalog_root.iterdir(), key=lambda item: item.name):
            if not root.is_dir() or root.is_symlink():
                continue
            try:
                records.append(_load_record(root))
            except SampleStudyManifestError:
                continue
            if len(records) >= MAX_SAMPLE_STUDIES:
                break
        return sorted(records, key=lambda item: (item.order, item.title.lower(), item.sample_id))

    def _record(self, sample_id: str) -> SampleStudyRecord:
        if not isinstance(sample_id, str) or not _SAMPLE_ID.fullmatch(sample_id):
            raise SampleStudyNotFoundError("Sample study is unavailable")
        root = self.catalog_root / sample_id
        if not root.is_dir() or root.is_symlink():
            raise SampleStudyNotFoundError("Sample study is unavailable")
        try:
            return _load_record(root)
        except SampleStudyManifestError as exc:
            raise SampleStudyNotFoundError("Sample study is unavailable") from exc

    def list_public(self) -> list[dict[str, object]]:
        return [record.public_dict() for record in self._records()]

    def preview_path(self, sample_id: str) -> Path:
        record = self._record(sample_id)
        if record.preview_path is None:
            raise SampleStudyNotFoundError("Sample study preview is unavailable")
        return record.preview_path

    def load_sample(self, sample_id: str) -> dict[str, object]:
        with self._load_lock:
            record = self._record(sample_id)
            digest, file_count, size_bytes = compute_sample_payload_digest(record.dicom_root)
            if digest != record.payload_sha256 or file_count != record.file_count or size_bytes != record.size_bytes:
                raise SampleStudyIntegrityError(
                    "Sample study integrity verification failed; reinstall this sample"
                )
            paths = _payload_files(record.dicom_root)
            with ExitStack() as stack:
                parts = [
                    _LocalUploadPart(
                        filename=path.relative_to(record.dicom_root).as_posix(),
                        file=stack.enter_context(path.open("rb")),
                    )
                    for path in paths
                ]
                descriptor = self.dicom_service.ingest(parts)
            origin = record.origin_dict()
            annotate = getattr(self.dicom_service, "annotate_study_origin", None)
            public_study = (
                annotate(descriptor.study_id, origin)
                if callable(annotate)
                else descriptor.public_dict() | {"origin": origin}
            )
            return {"study": public_study, "sample": record.public_dict()}
