from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import secrets
from typing import Callable

import numpy as np

from .dicom_ingestion import DicomStudyRepository
from .segmentation import (
    SegmentationConflictError,
    SegmentationNotFoundError,
    SegmentationValidationError,
)
from .segmentation_label_maps import SegmentationLabelMapService


CORRECTION_SCHEMA_VERSION = 1
CORRECTION_SESSION_PATTERN = re.compile(r"^corr-[0-9a-f]{32}$")
ACTION_KINDS = frozenset({"include", "exclude", "review"})
PLANES = frozenset({"axial", "coronal", "sagittal"})
MIN_RADIUS_MM = 0.5
MAX_RADIUS_MM = 25.0

Clock = Callable[[], datetime]
TokenFactory = Callable[[], str]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SegmentationValidationError("Correction metadata is invalid") from exc


def _digest(value: object) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _file_digest(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SegmentationValidationError("Canonical label-map artifact is unreadable") from exc
    return digest.hexdigest()


def _timestamp(clock: Clock) -> str:
    value = clock()
    if not isinstance(value, datetime):
        raise SegmentationValidationError("Correction clock is invalid")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _safe_repository(root: Path) -> None:
    parent = root.parent
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise SegmentationValidationError("Segmentation repository is unsafe")
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise SegmentationValidationError("Correction repository is unsafe")


class SegmentationCorrectionService:
    """Durable, reversible correction drafts over immutable canonical labels."""

    def __init__(
        self,
        *,
        data_dir: Path,
        study_repository: object | None = None,
        label_map_service: SegmentationLabelMapService | None = None,
        clock: Clock = _utc_now,
        token_factory: TokenFactory = lambda: secrets.token_hex(16),
    ) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.root = self.data_dir / "segmentation" / "correction-sessions"
        self.repository = study_repository or DicomStudyRepository(self.data_dir)
        self.label_map_service = label_map_service or SegmentationLabelMapService(
            data_dir=self.data_dir
        )
        self._clock = clock
        self._token_factory = token_factory
        _safe_repository(self.root)

    def _ensure_root(self) -> None:
        _safe_repository(self.root)
        self.root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.mkdir(exist_ok=True, mode=0o700)
        os.chmod(self.root.parent, 0o700)
        os.chmod(self.root, 0o700)

    def _current_study_id(self) -> str:
        manifest = self.repository.latest_manifest()
        study_id = manifest.get("study_id") if isinstance(manifest, dict) else None
        if not isinstance(study_id, str) or re.fullmatch(r"[0-9a-f]{32}", study_id) is None:
            raise SegmentationValidationError("No stored DICOM study is available")
        return study_id

    def _resolve_map(self, label_map_id: str) -> dict[str, object]:
        descriptor = self.label_map_service.get(label_map_id)
        if descriptor.get("source_study_id") != self._current_study_id():
            raise SegmentationValidationError(
                "Canonical label map does not belong to the current study"
            )
        if (
            descriptor.get("state") != "ready"
            or descriptor.get("coordinate_system") != "patient_lps"
            or descriptor.get("artifact_format") != "npy"
            or descriptor.get("dtype") != "uint16"
            or not isinstance(descriptor.get("artifact_sha256"), str)
        ):
            raise SegmentationValidationError("Canonical label-map contract is invalid")
        return descriptor

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        value = str(session_id).strip().lower()
        if CORRECTION_SESSION_PATTERN.fullmatch(value) is None:
            raise SegmentationValidationError("Correction session identifier is invalid")
        return value

    @staticmethod
    def _public(manifest: dict[str, object]) -> dict[str, object]:
        actions = list(manifest["actions"])
        cursor = int(manifest["applied_action_count"])
        return {
            "schema_version": manifest["schema_version"],
            "session_id": manifest["session_id"],
            "state": manifest["state"],
            "created_at_utc": manifest["created_at_utc"],
            "updated_at_utc": manifest["updated_at_utc"],
            "source_study_id": manifest["source_study_id"],
            "label_map_id": manifest["label_map_id"],
            "label_map_sha256": manifest["label_map_sha256"],
            "coordinate_system": "patient_lps",
            "actions": actions,
            "action_count": len(actions),
            "applied_action_count": cursor,
            "can_undo": cursor > 0,
            "can_redo": cursor < len(actions),
            "revision_sha256": manifest["revision_sha256"],
            "source_label_map": "immutable",
            "materialization": "not_applied",
            "clinical_validation": "not_claimed",
        }

    def _path(self, session_id: str) -> Path:
        return self.root / self._validate_session_id(session_id) / "manifest.json"

    def _load(
        self,
        session_id: str,
        *,
        descriptor: dict[str, object] | None = None,
    ) -> dict[str, object]:
        path = self._path(session_id)
        root = path.parent
        if root.is_symlink() or not root.is_dir() or path.is_symlink() or not path.is_file():
            raise SegmentationNotFoundError("Correction session was not found")
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SegmentationValidationError("Correction session is unreadable") from exc
        revision = manifest.pop("revision_sha256", None) if isinstance(manifest, dict) else None
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != CORRECTION_SCHEMA_VERSION
            or manifest.get("session_id") != root.name
            or revision != _digest(manifest)
            or manifest.get("state") not in {"draft", "discarded"}
            or not isinstance(manifest.get("actions"), list)
            or not isinstance(manifest.get("applied_action_count"), int)
            or not 0 <= manifest["applied_action_count"] <= len(manifest["actions"])
        ):
            raise SegmentationValidationError("Correction session integrity check failed")
        manifest["revision_sha256"] = revision
        if descriptor is None:
            descriptor = self._resolve_map(str(manifest.get("label_map_id") or ""))
        if (
            manifest.get("source_study_id") != descriptor.get("source_study_id")
            or manifest.get("label_map_sha256") != descriptor.get("artifact_sha256")
        ):
            raise SegmentationValidationError("Correction source binding changed")
        return manifest

    def _write(self, manifest: dict[str, object]) -> dict[str, object]:
        session_id = self._validate_session_id(str(manifest["session_id"]))
        manifest = dict(manifest)
        manifest.pop("revision_sha256", None)
        manifest["revision_sha256"] = _digest(manifest)
        directory = self.root / session_id
        directory.mkdir(mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
        target = directory / "manifest.json"
        temporary = directory / f".manifest.{secrets.token_hex(8)}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                os.chmod(temporary, 0o600)
                handle.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return manifest

    def create(self, label_map_id: str) -> dict[str, object]:
        descriptor = self._resolve_map(label_map_id)
        self._ensure_root()
        token = str(self._token_factory()).strip().lower()
        if re.fullmatch(r"[0-9a-f]{32}", token) is None:
            raise SegmentationValidationError("Correction identity source is invalid")
        now = _timestamp(self._clock)
        manifest = {
            "schema_version": CORRECTION_SCHEMA_VERSION,
            "session_id": f"corr-{token}",
            "state": "draft",
            "created_at_utc": now,
            "updated_at_utc": now,
            "source_study_id": descriptor["source_study_id"],
            "label_map_id": descriptor["label_map_id"],
            "label_map_sha256": descriptor["artifact_sha256"],
            "actions": [],
            "applied_action_count": 0,
        }
        path = self.root / str(manifest["session_id"])
        if path.exists():
            raise SegmentationConflictError("Correction session identity already exists")
        return self._public(self._write(manifest))

    def get(self, session_id: str) -> dict[str, object]:
        return self._public(self._load(session_id))

    def list(self, *, label_map_id: str) -> list[dict[str, object]]:
        descriptor = self._resolve_map(label_map_id)
        _safe_repository(self.root)
        if not self.root.is_dir():
            return []
        sessions: list[dict[str, object]] = []
        for path in self.root.iterdir():
            if not path.is_dir() or CORRECTION_SESSION_PATTERN.fullmatch(path.name) is None:
                continue
            try:
                manifest = self._load(path.name, descriptor=descriptor)
            except (
                SegmentationConflictError,
                SegmentationNotFoundError,
                SegmentationValidationError,
            ):
                continue
            if (
                manifest["label_map_id"] == descriptor["label_map_id"]
                and manifest["source_study_id"] == descriptor["source_study_id"]
            ):
                sessions.append(self._public(manifest))
        sessions.sort(
            key=lambda item: (str(item["updated_at_utc"]), str(item["session_id"])),
            reverse=True,
        )
        return sessions[:100]

    def add_action(
        self,
        session_id: str,
        *,
        kind: str,
        label_id: int,
        center_lps_mm: object,
        radius_mm: float,
        plane: str,
    ) -> dict[str, object]:
        manifest = self._load(session_id)
        if manifest["state"] != "draft":
            raise SegmentationConflictError("Correction session is not editable")
        action_kind = str(kind).strip().lower()
        action_plane = str(plane).strip().lower()
        if action_kind not in ACTION_KINDS or action_plane not in PLANES:
            raise SegmentationValidationError("Correction action is invalid")
        if isinstance(label_id, bool) or not isinstance(label_id, int) or label_id <= 0:
            raise SegmentationValidationError("Correction label is invalid")
        descriptor = self._resolve_map(str(manifest["label_map_id"]))
        if label_id not in descriptor.get("present_labels", []):
            raise SegmentationValidationError("Correction label is not present in the source map")
        if not isinstance(center_lps_mm, (list, tuple)) or len(center_lps_mm) != 3:
            raise SegmentationValidationError("Correction center is invalid")
        try:
            center = [float(value) for value in center_lps_mm]
            radius = float(radius_mm)
        except (TypeError, ValueError) as exc:
            raise SegmentationValidationError("Correction geometry is invalid") from exc
        if not all(isfinite(value) for value in center) or not isfinite(radius):
            raise SegmentationValidationError("Correction geometry is invalid")
        if radius < MIN_RADIUS_MM or radius > MAX_RADIUS_MM:
            raise SegmentationValidationError("Correction radius is outside the supported range")
        affine = np.asarray(descriptor["array_index_to_patient_lps"], dtype=np.float64)
        shape = np.asarray(descriptor["shape"], dtype=np.float64)
        source = np.linalg.inv(affine) @ np.asarray([*center, 1.0])
        if not np.all(source[:3] >= -0.5) or not np.all(source[:3] <= shape - 0.5):
            raise SegmentationValidationError("Correction center is outside the source volume")
        actions = list(manifest["actions"][: int(manifest["applied_action_count"])])
        action_seed = {
            "session_id": manifest["session_id"],
            "sequence": len(actions) + 1,
            "kind": action_kind,
            "label_id": label_id,
            "center_lps_mm": center,
            "radius_mm": radius,
            "plane": action_plane,
        }
        action = action_seed | {
            "action_id": f"act-{_digest(action_seed)[:32]}",
            "created_at_utc": _timestamp(self._clock),
        }
        actions.append(action)
        manifest["actions"] = actions
        manifest["applied_action_count"] = len(actions)
        manifest["updated_at_utc"] = action["created_at_utc"]
        return self._public(self._write(manifest))

    def _move_cursor(self, session_id: str, delta: int) -> dict[str, object]:
        manifest = self._load(session_id)
        if manifest["state"] != "draft":
            raise SegmentationConflictError("Correction session is not editable")
        cursor = int(manifest["applied_action_count"])
        next_cursor = cursor + delta
        if next_cursor < 0 or next_cursor > len(manifest["actions"]):
            raise SegmentationConflictError("Correction history cannot move further")
        manifest["applied_action_count"] = next_cursor
        manifest["updated_at_utc"] = _timestamp(self._clock)
        return self._public(self._write(manifest))

    def undo(self, session_id: str) -> dict[str, object]:
        return self._move_cursor(session_id, -1)

    def redo(self, session_id: str) -> dict[str, object]:
        return self._move_cursor(session_id, 1)

    def discard(self, session_id: str) -> dict[str, object]:
        manifest = self._load(session_id)
        manifest["state"] = "discarded"
        manifest["updated_at_utc"] = _timestamp(self._clock)
        return self._public(self._write(manifest))

    def quality_report(self, *, label_map_id: str, label_id: int) -> dict[str, object]:
        descriptor = self._resolve_map(label_map_id)
        if isinstance(label_id, bool) or label_id not in descriptor.get("present_labels", []):
            raise SegmentationValidationError("Quality label is not present in the source map")
        path = self.data_dir / "segmentation" / "label-maps" / label_map_id / "labels.npy"
        if path.is_symlink() or not path.is_file():
            raise SegmentationValidationError("Canonical label-map artifact is unavailable")
        if _file_digest(path) != descriptor["artifact_sha256"]:
            raise SegmentationValidationError("Canonical label-map artifact seal changed")
        try:
            labels = np.load(path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise SegmentationValidationError("Canonical label-map artifact is unreadable") from exc
        if tuple(labels.shape) != tuple(descriptor["shape"]) or str(labels.dtype) != "uint16":
            raise SegmentationValidationError("Canonical label-map artifact changed")
        coordinates = np.argwhere(labels == label_id)
        if not coordinates.size:
            raise SegmentationValidationError("Quality label has no voxels")
        minimum = coordinates.min(axis=0)
        maximum = coordinates.max(axis=0)
        touches = [
            name
            for axis, name in enumerate(("slice", "row", "column"))
            if minimum[axis] == 0 or maximum[axis] == labels.shape[axis] - 1
        ]
        warnings = [
            {
                "code": "clinical_validation_not_claimed",
                "severity": "info",
                "message": "Segmentation output is for non-clinical visualization and review.",
            },
            {
                "code": "draft_not_materialized",
                "severity": "info",
                "message": "Correction actions are a reversible draft and do not change source labels.",
            },
            {
                "code": "preview_surface",
                "severity": "info",
                "message": "The 3D surface is a voxel-boundary preview; refinement is deferred to Phase 6.",
            },
        ]
        if touches:
            warnings.append(
                {
                    "code": "touches_volume_boundary",
                    "severity": "warning",
                    "message": "Selected structure reaches the acquired field-of-view boundary.",
                }
            )
        return {
            "schema_version": CORRECTION_SCHEMA_VERSION,
            "label_map_id": label_map_id,
            "label_map_sha256": descriptor["artifact_sha256"],
            "source_study_id": descriptor["source_study_id"],
            "label_id": label_id,
            "voxel_count": int(coordinates.shape[0]),
            "index_bounds": [int(value) for value in [*minimum, *maximum]],
            "touches_volume_boundary": bool(touches),
            "boundary_axes": touches,
            "warning_count": len(warnings),
            "warnings": warnings,
            "source_label_map": "immutable",
            "clinical_validation": "not_claimed",
        }
