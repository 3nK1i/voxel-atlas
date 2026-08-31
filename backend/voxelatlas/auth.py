from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


SESSION_TOKEN_BYTES = 32
PasswordVerifier = Callable[[str, str], bool]
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SessionRecord:
    username: str
    created_at: datetime
    expires_at: datetime


class InMemorySessionStore:
    """Process-local opaque-session store for the Phase 1 authentication core.

    Only SHA-256 digests of browser-visible session tokens are retained. This store
    intentionally establishes the service contract before a persistent production
    session backend is selected.
    """

    def __init__(self, *, clock: Clock = _utc_now) -> None:
        self._clock = clock
        self._records: dict[str, SessionRecord] = {}
        self._lock = threading.RLock()

    def create(self, username: str, *, ttl: timedelta) -> str:
        if not username:
            raise ValueError("username must not be empty")
        if ttl <= timedelta(0):
            raise ValueError("session TTL must be positive")

        now = self._clock()
        expires_at = now + ttl
        with self._lock:
            self._prune_expired_locked(now)
            while True:
                token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
                digest = _token_digest(token)
                if digest not in self._records:
                    break
            self._records[digest] = SessionRecord(
                username=username,
                created_at=now,
                expires_at=expires_at,
            )
        return token

    def resolve(self, token: str | None) -> SessionRecord | None:
        if not token:
            return None
        digest = _token_digest(token)
        now = self._clock()
        with self._lock:
            record = self._records.get(digest)
            if record is None:
                return None
            if record.expires_at <= now:
                self._records.pop(digest, None)
                return None
            return record

    def revoke(self, token: str | None) -> bool:
        if not token:
            return False
        digest = _token_digest(token)
        with self._lock:
            return self._records.pop(digest, None) is not None

    def active_count(self) -> int:
        now = self._clock()
        with self._lock:
            self._prune_expired_locked(now)
            return len(self._records)

    def _prune_expired_locked(self, now: datetime) -> None:
        expired = [
            digest
            for digest, record in self._records.items()
            if record.expires_at <= now
        ]
        for digest in expired:
            self._records.pop(digest, None)


class AuthenticationService:
    """Credential verification plus opaque server-side session lifecycle."""

    def __init__(
        self,
        *,
        username: str,
        password_hash: str,
        password_verifier: PasswordVerifier,
        session_store: InMemorySessionStore,
        session_ttl: timedelta,
    ) -> None:
        if not username:
            raise ValueError("configured username must not be empty")
        if not password_hash:
            raise ValueError("configured password hash must not be empty")
        if session_ttl <= timedelta(0):
            raise ValueError("session TTL must be positive")

        self._username = username
        self._password_hash = password_hash
        self._password_verifier = password_verifier
        self._session_store = session_store
        self._session_ttl = session_ttl

    def authenticate(self, username: str, password: str) -> str | None:
        candidate_username = username if isinstance(username, str) else ""
        candidate_password = password if isinstance(password, str) else ""

        username_ok = hmac.compare_digest(
            candidate_username.encode("utf-8"),
            self._username.encode("utf-8"),
        )
        try:
            password_ok = bool(
                self._password_verifier(self._password_hash, candidate_password)
            )
        except Exception:  # noqa: BLE001 - verifier errors are generic auth failures.
            password_ok = False

        if not (username_ok and password_ok):
            return None

        return self._session_store.create(self._username, ttl=self._session_ttl)

    def resolve_session(self, token: str | None) -> str | None:
        record = self._session_store.resolve(token)
        return None if record is None else record.username

    def logout(self, token: str | None) -> bool:
        return self._session_store.revoke(token)
