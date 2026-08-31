#!/usr/bin/env python3
"""Verify immutable prototype evidence from the verified VoxelAtlas handoff."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PRESERVED_FILES = {
    "prototypes/v2b3a/index.html": "cc7f063fb7304eea2af79b515ed497027ecaa9182871adfba022085fccb23240",
    "prototypes/v2b3a/styles.css": "fb97bf91d78810e7ba7d153dd638e07401d963c849fb24574af53cd05dd9b235",
    "prototypes/v2b3a/app.js": "3931d8e39cb830f97304a22231906b724525c126f77269901ef3283e58a138c5",
    "prototypes/v2b3a/assets/skull_full.glb": "23006cc79f7bb81539f9d3dd09e44901a9959f9094074ae74a12e6d364919ac4",
    "prototypes/v2b3b/index.html": "c7e64f2ded316b3677757316e280fe07c55e4898944f8c5d55321991e1b682a7",
    "prototypes/v2b3b/styles.css": "f13056a8f16f5150b341d75ba7864b5425c54c1f415b84eb3deeca9b4022792c",
    "prototypes/v2b3b/app.js": "a1efd8c927ce09371dda0001c775187d14d797a0cb45c8f1a50b11994516cb78",
    "prototypes/v2b3b/assets/skull_full.glb": "23006cc79f7bb81539f9d3dd09e44901a9959f9094074ae74a12e6d364919ac4",
}


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


def main() -> int:
    print("===== PHASE 0C1 PRESERVED BASELINE INTEGRITY =====")
    errors = verify_preserved_files()

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"PHASE0C1_BASELINE_INTEGRITY_OK=NO failures={len(errors)}")
        return 1

    print(f"PASS preserved prototype files={len(PRESERVED_FILES)}")
    print("PHASE0C1_BASELINE_INTEGRITY_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
