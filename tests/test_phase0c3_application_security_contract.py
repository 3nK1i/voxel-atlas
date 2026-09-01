from __future__ import annotations

import hashlib
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "backend/voxelatlas/config.py"
BACKEND_REQUIREMENTS = ROOT / "requirements/backend.txt"
REFERENCE_DIR = ROOT / "design/reference"

EXPECTED_REFERENCE_HASHES = {
    "logo.png": "5f0e33be6633795fc2133eff42d5ec97db668b1a2ed9f9d80936503661d0adfc",
    "login.png": "969fef1895309b7c607cada6ef172a63e199cd877affa067b1499f44105d3cf7",
    "ui.png": "10daf967f66988ec846c999375f03e6c0b643aad208482907f9891b9365a9975",
}

EXPECTED_BACKEND_REQUIREMENTS = {
    "fastapi",
    "uvicorn",
    "argon2-cffi",
    "python-multipart",
    "pydicom",
}


def load_config_module():
    spec = importlib.util.spec_from_file_location("voxelatlas_config", CONFIG_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load VoxelAtlas configuration module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def requirement_names(text: str) -> set[str]:
    names: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        name = line
        for marker in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
            name = name.split(marker, 1)[0]
        names.add(name.strip())
    return names


class Phase0C3ApplicationSecurityContractTests(unittest.TestCase):
    def test_authoritative_visual_references_match_supplied_assets(self) -> None:
        self.assertTrue(REFERENCE_DIR.is_dir())
        for filename, expected_sha in EXPECTED_REFERENCE_HASHES.items():
            path = REFERENCE_DIR / filename
            with self.subTest(filename=filename):
                self.assertTrue(path.is_file())
                actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(actual_sha, expected_sha)

    def test_visual_reference_contract_defines_usage(self) -> None:
        doc = (ROOT / "docs/design/VISUAL_REFERENCE_CONTRACT.md").read_text(encoding="utf-8")
        lowered = doc.lower()
        self.assertIn("logo.png", doc)
        self.assertIn("login.png", doc)
        self.assertIn("ui.png", doc)
        self.assertIn("authoritative", lowered)
        self.assertIn("product logo", lowered)
        self.assertIn("visual reference", lowered)

    def test_backend_manifest_declares_current_backend_foundation_without_pins(self) -> None:
        text = BACKEND_REQUIREMENTS.read_text(encoding="utf-8")
        self.assertEqual(requirement_names(text), EXPECTED_BACKEND_REQUIREMENTS)
        dependency_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        for line in dependency_lines:
            with self.subTest(line=line):
                self.assertNotIn("==", line)

    def test_development_defaults_are_local_and_non_secure_cookie_only(self) -> None:
        module = load_config_module()
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = module.load_settings()
        self.assertEqual(settings.environment, "development")
        self.assertFalse(settings.secure_cookies)
        self.assertEqual(settings.session_cookie_name, "voxelatlas_session")
        self.assertEqual(settings.allowed_hosts, ("127.0.0.1", "localhost"))
        self.assertIsNone(settings.session_secret)

    def test_production_requires_strong_session_secret_and_secure_cookies(self) -> None:
        module = load_config_module()
        with mock.patch.dict(
            os.environ,
            {
                "VOXELATLAS_ENV": "production",
                "VOXELATLAS_SESSION_SECRET": "short",
            },
            clear=True,
        ):
            with self.assertRaises(module.ConfigurationError):
                module.load_settings()

        with mock.patch.dict(
            os.environ,
            {
                "VOXELATLAS_ENV": "production",
                "VOXELATLAS_SESSION_SECRET": "x" * 48,
                "VOXELATLAS_SECURE_COOKIES": "false",
            },
            clear=True,
        ):
            with self.assertRaises(module.ConfigurationError):
                module.load_settings()

        with mock.patch.dict(
            os.environ,
            {
                "VOXELATLAS_ENV": "production",
                "VOXELATLAS_SESSION_SECRET": "x" * 48,
            },
            clear=True,
        ):
            settings = module.load_settings()
        self.assertTrue(settings.secure_cookies)
        self.assertEqual(settings.session_secret, "x" * 48)

    def test_data_directory_is_configurable_without_committing_patient_data(self) -> None:
        module = load_config_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                os.environ,
                {"VOXELATLAS_DATA_DIR": temp_dir},
                clear=True,
            ):
                settings = module.load_settings()
            self.assertEqual(settings.data_dir, Path(temp_dir).resolve())
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("data/", gitignore)

    def test_env_example_contains_names_but_no_real_secret(self) -> None:
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("VOXELATLAS_SESSION_SECRET=", env_example)
        secret_line = next(
            line for line in env_example.splitlines()
            if line.startswith("VOXELATLAS_SESSION_SECRET=")
        )
        self.assertEqual(secret_line, "VOXELATLAS_SESSION_SECRET=")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env.*", gitignore)
        self.assertIn("!.env.example", gitignore)

    def test_phase0c3_runner_chains_previous_foundation_regression(self) -> None:
        runner = (ROOT / "scripts/run_phase0c3_checks.sh").read_text(encoding="utf-8")
        self.assertIn("bash scripts/run_phase0c2_checks.sh", runner)
        self.assertIn("test_phase0c3_application_security_contract.py", runner)
        self.assertIn("check_phase0c3_foundation.py", runner)


if __name__ == "__main__":
    unittest.main()
