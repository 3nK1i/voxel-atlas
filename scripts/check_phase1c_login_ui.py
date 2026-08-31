#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from voxelatlas import config  # noqa: E402
from voxelatlas.app import create_app  # noqa: E402
from voxelatlas.passwords import hash_password  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    runtime_logo = ROOT / "web" / "assets" / "logo.png"
    reference_logo = ROOT / "design" / "reference" / "logo.png"
    if sha256(runtime_logo) != sha256(reference_logo):
        print("FAIL runtime_logo=authoritative_mismatch")
        return 1
    print(f"PASS runtime_logo=authoritative sha256={sha256(runtime_logo)}")

    settings = config.AppSettings(
        environment="test",
        session_secret="x" * 48,
        secure_cookies=False,
        session_cookie_name="voxelatlas_session",
        allowed_hosts=("testserver", "127.0.0.1", "localhost"),
        data_dir=ROOT / "data",
        max_upload_mib=512,
        auth_username="engineer",
        auth_password_hash=hash_password("correct horse battery staple"),
        session_ttl_minutes=60,
    )

    with TestClient(create_app(settings=settings)) as client:
        root = client.get("/", follow_redirects=False)
        login_page = client.get("/login")
        blocked = client.get("/workspace", follow_redirects=False)
        auth = client.post(
            "/api/auth/login",
            json={
                "username": "engineer",
                "password": "correct horse battery staple",
            },
        )
        workspace = client.get("/workspace", follow_redirects=False)

    checks = [
        (root.status_code == 302 and root.headers.get("location") == "/login", "anonymous_root=login_redirect"),
        (login_page.status_code == 200 and '<h1 id="loginTitle">Login</h1>' in login_page.text, "login_page=real_html_controls"),
        (blocked.status_code == 302 and blocked.headers.get("location") == "/login", "workspace_anonymous=blocked"),
        (auth.status_code == 200, "login_api=authenticated"),
        (workspace.status_code == 200 and 'data-workspace="voxelatlas-va"' in workspace.text, "workspace_authenticated=served"),
    ]
    for ok, label in checks:
        print(("PASS " if ok else "FAIL ") + label)
        if not ok:
            return 1

    login_js = (ROOT / "web" / "js" / "login.js").read_text(encoding="utf-8")
    if "localStorage" in login_js or "sessionStorage" in login_js:
        print("FAIL browser_auth_storage=forbidden")
        return 1
    print("PASS browser_auth_storage=cookie_only")

    print("PHASE1C_LOGIN_UI_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
