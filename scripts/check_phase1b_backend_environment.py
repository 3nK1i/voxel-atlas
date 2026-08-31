#!/usr/bin/env python3
from __future__ import annotations

from importlib import metadata


REQUIRED_PACKAGES = (
    ("fastapi", "fastapi"),
    ("starlette", "starlette"),
    ("argon2-cffi", "argon2"),
    ("httpx", "httpx"),
)


def main() -> int:
    print("===== PHASE 1B BACKEND ENVIRONMENT =====")
    failures: list[str] = []
    for distribution, module_name in REQUIRED_PACKAGES:
        try:
            __import__(module_name)
            version = metadata.version(distribution)
        except Exception as exc:  # noqa: BLE001 - human-readable qualification probe.
            failures.append(f"{distribution}: {exc}")
            print(f"FAIL backend_dependency={distribution} module={module_name}: {exc}")
        else:
            print(
                f"PASS backend_dependency={distribution} "
                f"module={module_name} version={version}"
            )

    if failures:
        print("PHASE1B_BACKEND_ENVIRONMENT_OK=NO")
        return 1
    print("PHASE1B_BACKEND_ENVIRONMENT_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
