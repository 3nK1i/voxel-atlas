from __future__ import annotations

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
from voxelatlas.passwords import hash_password, verify_password  # noqa: E402


def make_settings(
    *,
    secure_cookies: bool = False,
    username: str | None = "engineer",
    password_hash: str | None = None,
) -> config.AppSettings:
    if username is not None and password_hash is None:
        password_hash = hash_password("correct horse battery staple")
    return config.AppSettings(
        environment="test",
        session_secret="x" * 48,
        secure_cookies=secure_cookies,
        session_cookie_name="voxelatlas_session",
        allowed_hosts=("testserver", "127.0.0.1", "localhost"),
        data_dir=ROOT / "data",
        max_upload_mib=512,
        auth_username=username,
        auth_password_hash=password_hash,
        session_ttl_minutes=60,
    )


class Phase1BAuthenticationHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.password_hash = hash_password("correct horse battery staple")

    def client(self, *, secure_cookies: bool = False) -> TestClient:
        settings = make_settings(
            secure_cookies=secure_cookies,
            password_hash=self.password_hash,
        )
        return TestClient(create_app(settings=settings))

    def test_argon2id_hash_and_verifier_contract(self) -> None:
        self.assertTrue(self.password_hash.startswith("$argon2id$"))
        self.assertTrue(verify_password(self.password_hash, "correct horse battery staple"))
        self.assertFalse(verify_password(self.password_hash, "wrong password"))
        self.assertFalse(verify_password("not-an-argon2-hash", "anything"))

    def test_production_http_app_requires_login_credentials(self) -> None:
        settings = config.load_settings(
            {
                "VOXELATLAS_ENV": "production",
                "VOXELATLAS_SESSION_SECRET": "s" * 48,
                "VOXELATLAS_SECURE_COOKIES": "true",
                "VOXELATLAS_ALLOWED_HOSTS": "voxelatlas.example",
            }
        )
        with self.assertRaises(config.ConfigurationError):
            create_app(settings=settings)

    def test_login_sets_opaque_httponly_cookie_without_returning_token(self) -> None:
        with self.client() as client:
            response = client.post(
                "/api/auth/login",
                json={
                    "username": "engineer",
                    "password": "correct horse battery staple",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": True, "username": "engineer"})
        self.assertNotIn("token", response.text.lower())
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        cookie = response.headers.get("set-cookie", "")
        self.assertIn("voxelatlas_session=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertNotIn("Secure", cookie)

    def test_secure_cookie_flag_is_honored(self) -> None:
        with self.client(secure_cookies=True) as client:
            response = client.post(
                "/api/auth/login",
                json={
                    "username": "engineer",
                    "password": "correct horse battery staple",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Secure", response.headers.get("set-cookie", ""))

    def test_invalid_username_and_password_share_generic_http_failure(self) -> None:
        with self.client() as client:
            wrong_user = client.post(
                "/api/auth/login",
                json={
                    "username": "someone-else",
                    "password": "correct horse battery staple",
                },
            )
            wrong_password = client.post(
                "/api/auth/login",
                json={"username": "engineer", "password": "wrong"},
            )

        for response in (wrong_user, wrong_password):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Invalid credentials"})
            self.assertNotIn("set-cookie", response.headers)
            self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_session_and_protected_endpoint_use_server_side_cookie_session(self) -> None:
        with self.client() as client:
            initial = client.get("/api/auth/session")
            blocked = client.get("/api/protected/ping")
            login = client.post(
                "/api/auth/login",
                json={
                    "username": "engineer",
                    "password": "correct horse battery staple",
                },
            )
            current = client.get("/api/auth/session")
            protected = client.get("/api/protected/ping")

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.json(), {"authenticated": False})
        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(blocked.json(), {"detail": "Authentication required"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(current.json(), {"authenticated": True, "username": "engineer"})
        self.assertEqual(protected.json(), {"ok": True, "username": "engineer"})

    def test_logout_revokes_session_and_clears_cookie(self) -> None:
        with self.client() as client:
            client.post(
                "/api/auth/login",
                json={
                    "username": "engineer",
                    "password": "correct horse battery staple",
                },
            )
            logout = client.post("/api/auth/logout")
            current = client.get("/api/auth/session")
            protected = client.get("/api/protected/ping")

        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.json(), {"authenticated": False})
        cleared = logout.headers.get("set-cookie", "")
        self.assertIn("voxelatlas_session=", cleared)
        self.assertIn("Max-Age=0", cleared)
        self.assertEqual(current.json(), {"authenticated": False})
        self.assertEqual(protected.status_code, 401)

    def test_unconfigured_development_authentication_returns_service_unavailable(self) -> None:
        app = create_app(settings=make_settings(username=None, password_hash=None))
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/login",
                json={"username": "engineer", "password": "anything"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Authentication is not configured"})

    def test_health_endpoint_is_public_and_no_store_is_not_required(self) -> None:
        with self.client() as client:
            response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
