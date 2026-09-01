#!/usr/bin/env python3
"""Verify retained baseline evidence and intentional prototype retirement."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRESERVED_FILES = {
    "web/assets/models/skull.glb": "23006cc79f7bb81539f9d3dd09e44901a9959f9094074ae74a12e6d364919ac4",
    "web/assets/models/skull_full.glb": "23006cc79f7bb81539f9d3dd09e44901a9959f9094074ae74a12e6d364919ac4",
    "design/reference/logo.png": "5f0e33be6633795fc2133eff42d5ec97db668b1a2ed9f9d80936503661d0adfc",
    "design/reference/login.png": "969fef1895309b7c607cada6ef172a63e199cd877affa067b1499f44105d3cf7",
    "design/reference/ui.png": "10daf967f66988ec846c999375f03e6c0b643aad208482907f9891b9365a9975",
}

RETIRED_PATHS = (
    "prototypes/v2b3a",
    "prototypes/v2b3b",
    "scripts/check_v2b3a_prototype.py",
    "scripts/check_v2b3b_prototype.py",
    "web/assets/models/skull_" + "open.glb",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_preserved_files() -> list[str]:
    errors: list[str] = []
    for relative_path, expected in PRESERVED_FILES.items():
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"missing preserved file: {relative_path}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(
                f"fingerprint mismatch: {relative_path}\n"
                f"  expected={expected}\n"
                f"  actual={actual}"
            )
    return errors


def verify_retired_paths() -> list[str]:
    return [relative for relative in RETIRED_PATHS if (ROOT / relative).exists()]


def main() -> int:
    print("===== PHASE 0C1 BASELINE INTEGRITY =====")
    errors = verify_preserved_files()
    retired_present = verify_retired_paths()

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
    if retired_present:
        for relative in retired_present:
            print(f"FAIL: retired path still present: {relative}")

    if errors or retired_present:
        print("PHASE0C1_BASELINE_INTEGRITY_OK=NO")
        return 1

    print(f"PASS preserved baseline files={len(PRESERVED_FILES)}")
    print(f"PASS retired prototype paths absent={len(RETIRED_PATHS)}")
    print("PHASE0C1_BASELINE_INTEGRITY_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
