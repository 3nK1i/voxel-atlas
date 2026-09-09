from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
import subprocess
from typing import Callable


SURFACE_RUNTIME_PROBE_SCHEMA_VERSION = 1
MINIMUM_SURFACE_PYTHON = (3, 11)
SURFACE_RUNTIME_PROBE_TIMEOUT_SECONDS = 20.0
MAX_SURFACE_RUNTIME_PROBE_BYTES = 64 * 1024
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


class SegmentationSurfaceRuntimeError(ValueError):
    """Raised when the isolated Phase 6A surface runtime contract is invalid."""


@dataclass(frozen=True, slots=True)
class SegmentationSurfaceRuntimeReport:
    qualified: bool
    status_code: str
    message: str
    python_version: str | None = None
    numpy_version: str | None = None
    scikit_image_version: str | None = None
    runtime_fingerprint_sha256: str | None = None

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


ProbeRunner = Callable[..., object]


_PROBE_PROGRAM = r'''
import hashlib
import importlib
import importlib.metadata
import json
import platform

numpy_module = importlib.import_module("numpy")
skimage_module = importlib.import_module("skimage")
measure_module = importlib.import_module("skimage.measure")
marching_cubes = getattr(measure_module, "marching_cubes", None)
payload = {
    "schema_version": 1,
    "python_version": platform.python_version(),
    "numpy_version": importlib.metadata.version("numpy"),
    "scikit_image_version": importlib.metadata.version("scikit-image"),
    "numpy_available": numpy_module is not None,
    "skimage_available": skimage_module is not None,
    "marching_cubes_available": callable(marching_cubes),
}
identity = {
    "schema_version": payload["schema_version"],
    "python_version": payload["python_version"],
    "numpy_version": payload["numpy_version"],
    "scikit_image_version": payload["scikit_image_version"],
    "marching_cubes_available": payload["marching_cubes_available"],
}
payload["runtime_fingerprint_sha256"] = hashlib.sha256(
    json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
).hexdigest()
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
'''.strip()


def _failure(code: str, message: str) -> SegmentationSurfaceRuntimeReport:
    return SegmentationSurfaceRuntimeReport(False, code, message)


def _version(value: object, field: str) -> str:
    if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
        raise SegmentationSurfaceRuntimeError(f"{field} is invalid")
    return value


def _python_version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise SegmentationSurfaceRuntimeError("Python version is invalid")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _strict_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise SegmentationSurfaceRuntimeError(f"{field} is invalid")
    return value


def _fingerprint(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SegmentationSurfaceRuntimeError("runtime fingerprint is invalid")
    return value


def _parse_probe_payload(payload: object) -> SegmentationSurfaceRuntimeReport:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise SegmentationSurfaceRuntimeError("surface runtime probe schema is invalid")
    python_version = _version(payload.get("python_version"), "Python version")
    numpy_version = _version(payload.get("numpy_version"), "NumPy version")
    skimage_version = _version(payload.get("scikit_image_version"), "scikit-image version")
    numpy_available = _strict_bool(payload.get("numpy_available"), "NumPy availability")
    skimage_available = _strict_bool(payload.get("skimage_available"), "scikit-image availability")
    marching_cubes_available = _strict_bool(
        payload.get("marching_cubes_available"), "marching-cubes availability"
    )
    fingerprint = _fingerprint(payload.get("runtime_fingerprint_sha256"))
    identity = {
        "schema_version": 1,
        "python_version": python_version,
        "numpy_version": numpy_version,
        "scikit_image_version": skimage_version,
        "marching_cubes_available": marching_cubes_available,
    }
    expected_fingerprint = sha256(
        json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    if fingerprint != expected_fingerprint:
        raise SegmentationSurfaceRuntimeError("runtime fingerprint is inconsistent")
    common = {
        "python_version": python_version,
        "numpy_version": numpy_version,
        "scikit_image_version": skimage_version,
        "runtime_fingerprint_sha256": fingerprint,
    }
    if _python_version_tuple(python_version)[:2] < MINIMUM_SURFACE_PYTHON:
        return SegmentationSurfaceRuntimeReport(
            False,
            "python_version_unsupported",
            "Segmentation surface Python version is unsupported",
            **common,
        )
    if not numpy_available:
        return SegmentationSurfaceRuntimeReport(
            False, "numpy_unavailable", "NumPy is unavailable in the surface runtime", **common
        )
    if not skimage_available or not marching_cubes_available:
        return SegmentationSurfaceRuntimeReport(
            False,
            "marching_cubes_unavailable",
            "scikit-image marching_cubes is unavailable in the surface runtime",
            **common,
        )
    return SegmentationSurfaceRuntimeReport(
        True,
        "qualified",
        "Segmentation surface runtime contract is qualified",
        **common,
    )


class SegmentationSurfaceRuntimeQualifier:
    def __init__(
        self,
        *,
        runner: ProbeRunner = subprocess.run,
        timeout_seconds: float = SURFACE_RUNTIME_PROBE_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise SegmentationSurfaceRuntimeError("surface runtime probe timeout is invalid")
        self._runner = runner
        self._timeout_seconds = float(timeout_seconds)

    def qualify(self, python_executable: str | None) -> SegmentationSurfaceRuntimeReport:
        if (
            not isinstance(python_executable, str)
            or not python_executable.strip()
            or len(python_executable) > 4096
            or any(ord(character) < 32 for character in python_executable)
        ):
            return _failure(
                "runtime_unconfigured",
                "Accurate segmentation surface runtime is not configured",
            )
        command = [python_executable.strip(), "-I", "-c", _PROBE_PROGRAM]
        try:
            completed = self._runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                shell=False,
            )
        except FileNotFoundError:
            return _failure("runtime_unavailable", "Segmentation surface runtime is unavailable")
        except subprocess.TimeoutExpired:
            return _failure("probe_timeout", "Segmentation surface runtime probe timed out")
        except (OSError, subprocess.SubprocessError):
            return _failure("probe_failed", "Segmentation surface runtime probe failed")
        except Exception:
            return _failure("probe_failed", "Segmentation surface runtime probe failed")

        returncode = getattr(completed, "returncode", None)
        stdout = getattr(completed, "stdout", None)
        if returncode != 0:
            return _failure("probe_failed", "Segmentation surface runtime probe failed")
        if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_SURFACE_RUNTIME_PROBE_BYTES:
            return _failure("invalid_probe_report", "Segmentation surface runtime probe report is invalid")
        try:
            lines = [line for line in stdout.splitlines() if line.strip()]
            if not lines:
                raise SegmentationSurfaceRuntimeError("surface runtime probe report is empty")
            report = _parse_probe_payload(json.loads(lines[-1]))
        except (json.JSONDecodeError, SegmentationSurfaceRuntimeError, UnicodeError):
            return _failure("invalid_probe_report", "Segmentation surface runtime probe report is invalid")
        return report
