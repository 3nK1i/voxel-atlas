from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from voxelatlas import config  # noqa: E402
from voxelatlas.app import create_app  # noqa: E402
from voxelatlas.passwords import hash_password  # noqa: E402


def make_settings() -> config.AppSettings:
    return config.AppSettings(
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


class Phase1CLoginUIContractTests(unittest.TestCase):
    def test_runtime_logo_matches_authoritative_reference(self) -> None:
        runtime_logo = ROOT / "web" / "assets" / "logo.png"
        reference_logo = ROOT / "design" / "reference" / "logo.png"
        self.assertTrue(runtime_logo.is_file())
        self.assertEqual(
            hashlib.sha256(runtime_logo.read_bytes()).hexdigest(),
            hashlib.sha256(reference_logo.read_bytes()).hexdigest(),
        )

    def test_login_document_is_real_controls_not_reference_screenshot(self) -> None:
        text = (ROOT / "web" / "login.html").read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn('id="loginForm"', text)
        self.assertIn('name="username"', text)
        self.assertIn('name="password"', text)
        self.assertIn('type="submit"', text)
        self.assertIn('/assets/logo.png', text)
        self.assertNotIn('design/reference/login.png', lowered)
        self.assertNotIn('background-image', lowered)

    def test_login_javascript_uses_cookie_auth_without_browser_storage(self) -> None:
        text = (ROOT / "web" / "js" / "login.js").read_text(encoding="utf-8")
        self.assertIn('/api/auth/login', text)
        self.assertIn('/api/auth/session', text)
        self.assertIn('/workspace', text)
        self.assertIn('credentials: "same-origin"', text)
        self.assertNotIn('localStorage', text)
        self.assertNotIn('sessionStorage', text)

    def test_login_styles_define_reference_language_and_responsive_layout(self) -> None:
        text = (ROOT / "web" / "css" / "login.css").read_text(encoding="utf-8")
        self.assertIn('.login-card', text)
        self.assertIn('.login-brandmark', text)
        self.assertIn('.login-field', text)
        self.assertIn('.login-submit', text)
        self.assertIn('@media', text)
        self.assertNotIn('login.png', text)

    def test_login_styles_use_compact_ergonomic_desktop_scale(self) -> None:
        css = (ROOT / "web" / "css" / "login.css").read_text(encoding="utf-8")
        html = (ROOT / "web" / "login.html").read_text(encoding="utf-8")
        self.assertIn("width: min(480px, 100%);", css)
        self.assertIn("width: clamp(140px, 18vh, 176px);", css)
        self.assertIn("min-height: 52px;", css)
        self.assertIn("@media (max-height: 720px) and (min-width: 701px)", css)
        self.assertNotIn('class="login-product"', html)

    def test_asset_readme_defines_runtime_image_location_and_placeholder_behavior(self) -> None:
        text = (ROOT / "web" / "assets" / "README.md").read_text(encoding="utf-8")
        self.assertIn('logo.png', text)
        self.assertIn('runtime', text.lower())
        self.assertIn('placeholder', text.lower())
        self.assertIn('design/reference', text)

    def test_http_app_serves_login_and_protects_workspace(self) -> None:
        with TestClient(create_app(settings=make_settings())) as client:
            root = client.get("/", follow_redirects=False)
            login = client.get("/login")
            blocked_workspace = client.get("/workspace", follow_redirects=False)
            logo = client.get("/assets/logo.png")

        self.assertEqual(root.status_code, 302)
        self.assertEqual(root.headers["location"], "/login")
        self.assertEqual(login.status_code, 200)
        self.assertIn('<h1 id="loginTitle">Login</h1>', login.text)
        self.assertEqual(login.headers.get("cache-control"), "no-store")
        self.assertEqual(blocked_workspace.status_code, 302)
        self.assertEqual(blocked_workspace.headers["location"], "/login")
        self.assertEqual(logo.status_code, 200)
        self.assertTrue(logo.content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_authenticated_browser_flow_reaches_workspace(self) -> None:
        with TestClient(create_app(settings=make_settings())) as client:
            login = client.post(
                "/api/auth/login",
                json={
                    "username": "engineer",
                    "password": "correct horse battery staple",
                },
            )
            workspace = client.get("/workspace", follow_redirects=False)
            login_page = client.get("/login", follow_redirects=False)

        self.assertEqual(login.status_code, 200)
        self.assertEqual(workspace.status_code, 200)
        self.assertIn('data-workspace="voxelatlas-va"', workspace.text)
        self.assertEqual(login_page.status_code, 302)
        self.assertEqual(login_page.headers["location"], "/workspace")


if __name__ == "__main__":
    unittest.main()
