#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from datetime import timedelta
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.auth import AuthenticationService, InMemorySessionStore  # noqa: E402
from voxelatlas.config import load_settings  # noqa: E402


def main() -> int:
    print("===== PHASE 1A AUTHENTICATION CORE =====")
    failures: list[str] = []

    with mock.patch.dict(
        "os.environ",
        {
            "VOXELATLAS_AUTH_USERNAME": "engineer",
            "VOXELATLAS_AUTH_PASSWORD_HASH": "opaque-password-hash",
            "VOXELATLAS_SESSION_TTL_MINUTES": "60",
        },
        clear=True,
    ):
        settings = load_settings()

    if settings.auth_username != "engineer" or settings.session_ttl_minutes != 60:
        failures.append("authentication configuration contract is invalid")
    else:
        print("PASS auth_config=paired_credentials ttl_minutes=60")

    def verifier(stored_hash: str, candidate: str) -> bool:
        return stored_hash == "opaque-password-hash" and candidate == "correct-password"

    store = InMemorySessionStore()
    service = AuthenticationService(
        username=settings.auth_username or "",
        password_hash=settings.auth_password_hash or "",
        password_verifier=verifier,
        session_store=store,
        session_ttl=timedelta(minutes=settings.session_ttl_minutes),
    )

    if service.authenticate("engineer", "wrong-password") is not None:
        failures.append("invalid credentials unexpectedly authenticated")
    else:
        print("PASS invalid_credentials=generic_failure")

    token = service.authenticate("engineer", "correct-password")
    if token is None:
        failures.append("valid credentials failed authentication")
    elif service.resolve_session(token) != "engineer":
        failures.append("created session cannot be resolved")
    elif token in store._records:
        failures.append("raw session token was retained server-side")
    elif hashlib.sha256(token.encode("utf-8")).hexdigest() not in store._records:
        failures.append("session token digest was not retained server-side")
    else:
        print("PASS valid_credentials=opaque_session_created")
        print("PASS session_storage=token_digest_only")

    if token is not None:
        service.logout(token)
        if service.resolve_session(token) is not None:
            failures.append("logout failed to revoke session")
        else:
            print("PASS logout=session_revoked")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print("PHASE1A_AUTHENTICATION_CORE_OK=NO")
        return 1

    print("PHASE1A_AUTHENTICATION_CORE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
