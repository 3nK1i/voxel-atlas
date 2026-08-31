from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple


VALID_ENVIRONMENTS = {"development", "test", "production"}
MIN_SESSION_SECRET_LENGTH = 32
DEFAULT_SESSION_COOKIE_NAME = "voxelatlas_session"
DEFAULT_ALLOWED_HOSTS = ("127.0.0.1", "localhost")
DEFAULT_MAX_UPLOAD_MIB = 512
MAX_UPLOAD_MIB_LIMIT = 4096


class ConfigurationError(ValueError):
    """Raised when runtime configuration violates the VoxelAtlas contract."""


class AppSettings(NamedTuple):
    environment: str
    session_secret: str | None
    secure_cookies: bool
    session_cookie_name: str
    allowed_hosts: tuple[str, ...]
    data_dir: Path
    max_upload_mib: int


def _parse_bool(name: str, raw_value: str) -> bool:
    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean value")


def _parse_positive_int(name: str, raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


def _parse_allowed_hosts(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        return DEFAULT_ALLOWED_HOSTS
    hosts = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    if not hosts:
        raise ConfigurationError("VOXELATLAS_ALLOWED_HOSTS must contain at least one host")
    if "*" in hosts:
        raise ConfigurationError("VOXELATLAS_ALLOWED_HOSTS must not use a wildcard host")
    return hosts


def load_settings(environ: dict[str, str] | None = None) -> AppSettings:
    env = os.environ if environ is None else environ

    environment = env.get("VOXELATLAS_ENV", "development").strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        choices = ", ".join(sorted(VALID_ENVIRONMENTS))
        raise ConfigurationError(f"VOXELATLAS_ENV must be one of: {choices}")

    raw_secret = env.get("VOXELATLAS_SESSION_SECRET", "").strip()
    session_secret = raw_secret or None

    if session_secret is not None and len(session_secret) < MIN_SESSION_SECRET_LENGTH:
        raise ConfigurationError(
            f"VOXELATLAS_SESSION_SECRET must be at least {MIN_SESSION_SECRET_LENGTH} characters"
        )
    if session_secret is not None and session_secret.lower() in {
        "change-me",
        "changeme",
        "replace-me",
    }:
        raise ConfigurationError("VOXELATLAS_SESSION_SECRET must not use a placeholder value")

    if environment == "production" and session_secret is None:
        raise ConfigurationError("VOXELATLAS_SESSION_SECRET is required in production")

    raw_secure_cookies = env.get("VOXELATLAS_SECURE_COOKIES")
    if raw_secure_cookies is None:
        secure_cookies = environment == "production"
    else:
        secure_cookies = _parse_bool("VOXELATLAS_SECURE_COOKIES", raw_secure_cookies)

    if environment == "production" and not secure_cookies:
        raise ConfigurationError("secure cookies cannot be disabled in production")

    session_cookie_name = env.get(
        "VOXELATLAS_SESSION_COOKIE_NAME", DEFAULT_SESSION_COOKIE_NAME
    ).strip()
    if not session_cookie_name:
        raise ConfigurationError("VOXELATLAS_SESSION_COOKIE_NAME must not be empty")

    allowed_hosts = _parse_allowed_hosts(env.get("VOXELATLAS_ALLOWED_HOSTS"))

    data_dir = Path(env.get("VOXELATLAS_DATA_DIR", "data")).expanduser().resolve()

    max_upload_mib = _parse_positive_int(
        "VOXELATLAS_MAX_UPLOAD_MIB",
        env.get("VOXELATLAS_MAX_UPLOAD_MIB", str(DEFAULT_MAX_UPLOAD_MIB)),
    )
    if max_upload_mib > MAX_UPLOAD_MIB_LIMIT:
        raise ConfigurationError(
            f"VOXELATLAS_MAX_UPLOAD_MIB must not exceed {MAX_UPLOAD_MIB_LIMIT}"
        )

    return AppSettings(
        environment=environment,
        session_secret=session_secret,
        secure_cookies=secure_cookies,
        session_cookie_name=session_cookie_name,
        allowed_hosts=allowed_hosts,
        data_dir=data_dir,
        max_upload_mib=max_upload_mib,
    )
