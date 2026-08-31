from __future__ import annotations

import hashlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas import auth  # noqa: E402
from voxelatlas import config  # noqa: E402


class MutableClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, *, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


def verifier_for(expected_password: str):
    calls: list[tuple[str, str]] = []

    def verify(stored_hash: str, candidate_password: str) -> bool:
        calls.append((stored_hash, candidate_password))
        return stored_hash == "opaque-password-hash" and candidate_password == expected_password

    return verify, calls


class Phase1AAuthenticationCoreTests(unittest.TestCase):
    def test_config_accepts_blank_auth_pair_in_development(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {
                "VOXELATLAS_ENV": "development",
                "VOXELATLAS_AUTH_USERNAME": "",
                "VOXELATLAS_AUTH_PASSWORD_HASH": "",
            },
            clear=True,
        ):
            settings = config.load_settings()
        self.assertIsNone(settings.auth_username)
        self.assertIsNone(settings.auth_password_hash)
        self.assertEqual(settings.session_ttl_minutes, 60)

    def test_config_rejects_partial_auth_configuration(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"VOXELATLAS_AUTH_USERNAME": "engineer"},
            clear=True,
        ):
            with self.assertRaises(config.ConfigurationError):
                config.load_settings()

        with mock.patch.dict(
            "os.environ",
            {"VOXELATLAS_AUTH_PASSWORD_HASH": "opaque-password-hash"},
            clear=True,
        ):
            with self.assertRaises(config.ConfigurationError):
                config.load_settings()

    def test_config_bounds_session_ttl(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"VOXELATLAS_SESSION_TTL_MINUTES": "0"},
            clear=True,
        ):
            with self.assertRaises(config.ConfigurationError):
                config.load_settings()

        with mock.patch.dict(
            "os.environ",
            {"VOXELATLAS_SESSION_TTL_MINUTES": "1441"},
            clear=True,
        ):
            with self.assertRaises(config.ConfigurationError):
                config.load_settings()

    def test_successful_authentication_returns_opaque_session_token(self) -> None:
        clock = MutableClock()
        store = auth.InMemorySessionStore(clock=clock)
        verify, calls = verifier_for("correct horse battery staple")
        service = auth.AuthenticationService(
            username="engineer",
            password_hash="opaque-password-hash",
            password_verifier=verify,
            session_store=store,
            session_ttl=timedelta(minutes=60),
        )

        token = service.authenticate("engineer", "correct horse battery staple")

        self.assertIsInstance(token, str)
        self.assertGreaterEqual(len(token), 40)
        self.assertEqual(service.resolve_session(token), "engineer")
        self.assertEqual(calls, [("opaque-password-hash", "correct horse battery staple")])
        self.assertNotIn(token, store._records)
        self.assertIn(hashlib.sha256(token.encode("utf-8")).hexdigest(), store._records)

    def test_invalid_username_and_invalid_password_are_generic_failures(self) -> None:
        verify, calls = verifier_for("correct-password")
        service = auth.AuthenticationService(
            username="engineer",
            password_hash="opaque-password-hash",
            password_verifier=verify,
            session_store=auth.InMemorySessionStore(),
            session_ttl=timedelta(minutes=60),
        )

        wrong_user = service.authenticate("someone-else", "correct-password")
        wrong_password = service.authenticate("engineer", "wrong-password")

        self.assertIsNone(wrong_user)
        self.assertIsNone(wrong_password)
        self.assertEqual(len(calls), 2, "password verification must run for both generic failures")

    def test_session_expiry_invalidates_resolution(self) -> None:
        clock = MutableClock()
        store = auth.InMemorySessionStore(clock=clock)
        verify, _ = verifier_for("correct-password")
        service = auth.AuthenticationService(
            username="engineer",
            password_hash="opaque-password-hash",
            password_verifier=verify,
            session_store=store,
            session_ttl=timedelta(minutes=5),
        )

        token = service.authenticate("engineer", "correct-password")
        self.assertIsNotNone(token)
        clock.advance(seconds=301)

        self.assertIsNone(service.resolve_session(token))
        self.assertEqual(store.active_count(), 0)

    def test_logout_revokes_session_immediately_and_is_idempotent(self) -> None:
        verify, _ = verifier_for("correct-password")
        service = auth.AuthenticationService(
            username="engineer",
            password_hash="opaque-password-hash",
            password_verifier=verify,
            session_store=auth.InMemorySessionStore(),
            session_ttl=timedelta(minutes=60),
        )
        token = service.authenticate("engineer", "correct-password")
        self.assertIsNotNone(token)

        self.assertTrue(service.logout(token))
        self.assertIsNone(service.resolve_session(token))
        self.assertFalse(service.logout(token))

    def test_service_refuses_empty_configured_credentials(self) -> None:
        verify, _ = verifier_for("irrelevant")
        with self.assertRaises(ValueError):
            auth.AuthenticationService(
                username="",
                password_hash="opaque-password-hash",
                password_verifier=verify,
                session_store=auth.InMemorySessionStore(),
                session_ttl=timedelta(minutes=60),
            )
        with self.assertRaises(ValueError):
            auth.AuthenticationService(
                username="engineer",
                password_hash="",
                password_verifier=verify,
                session_store=auth.InMemorySessionStore(),
                session_ttl=timedelta(minutes=60),
            )


if __name__ == "__main__":
    unittest.main()
