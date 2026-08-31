#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REFERENCE_HASHES = {
    "logo.png": "5f0e33be6633795fc2133eff42d5ec97db668b1a2ed9f9d80936503661d0adfc",
    "login.png": "969fef1895309b7c607cada6ef172a63e199cd877affa067b1499f44105d3cf7",
    "ui.png": "10daf967f66988ec846c999375f03e6c0b643aad208482907f9891b9365a9975",
}


def load_config_module():
    path = ROOT / "backend/voxelatlas/config.py"
    spec = importlib.util.spec_from_file_location("voxelatlas_config_probe", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load backend configuration module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    print("===== PHASE 0C3 APPLICATION/SECURITY FOUNDATION =====")
    failures: list[str] = []

    for filename, expected_sha in EXPECTED_REFERENCE_HASHES.items():
        path = ROOT / "design/reference" / filename
        if not path.is_file():
            failures.append(f"missing visual reference: {path.relative_to(ROOT)}")
            continue
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            failures.append(f"visual reference hash mismatch: {filename}")
        else:
            print(f"PASS visual_reference={filename} sha256={actual_sha}")

    env_example = ROOT / ".env.example"
    if not env_example.is_file():
        failures.append("missing .env.example")
    else:
        secret_lines = [
            line for line in env_example.read_text(encoding="utf-8").splitlines()
            if line.startswith("VOXELATLAS_SESSION_SECRET=")
        ]
        if secret_lines != ["VOXELATLAS_SESSION_SECRET="]:
            failures.append(".env.example must keep VOXELATLAS_SESSION_SECRET blank")
        else:
            print("PASS env_example_secret_blank=YES")

    try:
        config = load_config_module()
        with mock.patch.dict(os.environ, {}, clear=True):
            development = config.load_settings()
        if development.environment != "development" or development.secure_cookies:
            failures.append("development configuration defaults are invalid")
        else:
            print("PASS development_config=local_safe_defaults")

        with mock.patch.dict(
            os.environ,
            {
                "VOXELATLAS_ENV": "production",
                "VOXELATLAS_SESSION_SECRET": "x" * 48,
            },
            clear=True,
        ):
            production = config.load_settings()
        if not production.secure_cookies:
            failures.append("production secure cookie default is invalid")
        else:
            print("PASS production_secure_cookies=YES")
    except Exception as exc:  # noqa: BLE001 - command-line validation should report all failures.
        failures.append(f"configuration probe failed: {exc}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print("PHASE0C3_FOUNDATION_OK=NO")
        return 1

    print("PHASE0C3_FOUNDATION_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
