#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from voxelatlas.app import create_app  # noqa: E402
from voxelatlas.config import AppSettings  # noqa: E402
from voxelatlas.passwords import hash_password  # noqa: E402


def main() -> int:
    settings = AppSettings(
        environment="test",
        session_secret="s" * 48,
        secure_cookies=False,
        session_cookie_name="voxelatlas_session",
        allowed_hosts=("testserver",),
        data_dir=ROOT / "data",
        max_upload_mib=512,
        auth_username="engineer",
        auth_password_hash=hash_password("probe-password"),
        session_ttl_minutes=60,
    )

    with TestClient(create_app(settings=settings)) as client:
        unauthenticated = client.get("/api/protected/ping")
        invalid = client.post(
            "/api/auth/login",
            json={"username": "engineer", "password": "wrong"},
        )
        login = client.post(
            "/api/auth/login",
            json={"username": "engineer", "password": "probe-password"},
        )
        session = client.get("/api/auth/session")
        protected = client.get("/api/protected/ping")
        logout = client.post("/api/auth/logout")
        after_logout = client.get("/api/protected/ping")

    checks = (
        (unauthenticated.status_code == 401, "protected_unauthenticated=401"),
        (
            invalid.status_code == 401
            and invalid.json() == {"detail": "Invalid credentials"},
            "invalid_credentials=generic_401",
        ),
        (
            login.status_code == 200
            and login.json() == {"authenticated": True, "username": "engineer"}
            and "token" not in login.text.lower(),
            "login=opaque_cookie_no_token_body",
        ),
        (
            "HttpOnly" in login.headers.get("set-cookie", "")
            and "SameSite=lax" in login.headers.get("set-cookie", ""),
            "cookie=httponly_samesite_lax",
        ),
        (
            session.json() == {"authenticated": True, "username": "engineer"},
            "session=authenticated",
        ),
        (protected.status_code == 200, "protected_authenticated=200"),
        (logout.json() == {"authenticated": False}, "logout=revoked"),
        (after_logout.status_code == 401, "protected_after_logout=401"),
    )

    failed = False
    for ok, label in checks:
        if ok:
            print(f"PASS {label}")
        else:
            failed = True
            print(f"FAIL {label}")

    if failed:
        print("PHASE1B_AUTH_HTTP_OK=NO")
        return 1
    print("PHASE1B_AUTH_HTTP_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
