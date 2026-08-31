#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)
MIN_NODE_MAJOR = 20
MEDICAL_IMPORTS = {
    "numpy": "numpy",
    "scipy": "scipy",
    "scikit-image": "skimage",
    "SimpleITK": "SimpleITK",
    "trimesh": "trimesh",
    "pyvista": "pyvista",
    "matplotlib": "matplotlib",
}


def parse_node_major(version_text: str) -> int:
    match = re.fullmatch(r"v?(\d+)(?:\.\d+){1,2}", version_text.strip())
    if not match:
        raise ValueError(f"unrecognized Node.js version: {version_text!r}")
    return int(match.group(1))


def command_output(*command: str) -> str:
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()


def check_core() -> list[str]:
    failures: list[str] = []

    python_text = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info[:2] >= MIN_PYTHON:
        print(f"PASS python={python_text} minimum={MIN_PYTHON[0]}.{MIN_PYTHON[1]}")
    else:
        failures.append(
            f"python {python_text} is older than required "
            f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        )

    git = shutil.which("git")
    if git:
        try:
            print(f"PASS git={command_output(git, '--version')}")
        except (OSError, subprocess.CalledProcessError) as exc:
            failures.append(f"git probe failed: {exc}")
    else:
        failures.append("git executable not found")

    node = shutil.which("node")
    if node:
        try:
            node_version = command_output(node, "--version")
            node_major = parse_node_major(node_version)
            if node_major >= MIN_NODE_MAJOR:
                print(f"PASS node={node_version} minimum_major={MIN_NODE_MAJOR}")
            else:
                failures.append(
                    f"node {node_version} is older than required major {MIN_NODE_MAJOR}"
                )
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            failures.append(f"node probe failed: {exc}")
    else:
        failures.append("node executable not found")

    required_paths = (
        ROOT / "web/index.html",
        ROOT / "scripts/run_phase0c1_checks.sh",
        ROOT / "requirements/medical-processing.txt",
    )
    for path in required_paths:
        if path.is_file():
            print(f"PASS path={path.relative_to(ROOT)}")
        else:
            failures.append(f"required path missing: {path.relative_to(ROOT)}")

    return failures


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def check_medical() -> list[str]:
    failures: list[str] = []
    for distribution, module_name in MEDICAL_IMPORTS.items():
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # import failures may include native-library errors
            failures.append(f"{distribution}: import {module_name!r} failed: {exc}")
        else:
            print(
                f"PASS medical_dependency={distribution} "
                f"module={module_name} version={package_version(distribution)}"
            )
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the VoxelAtlas Phase 0C2 development/runtime environment."
    )
    parser.add_argument(
        "--profile",
        choices=("core", "medical"),
        default="core",
        help=(
            "core checks the tools needed for baseline development/validation; "
            "medical additionally imports the existing medical-processing dependencies"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("===== PHASE 0C2 ENVIRONMENT =====")
    print(f"PHASE0C2_PROFILE={args.profile}")

    failures = check_core()
    if args.profile == "medical":
        failures.extend(check_medical())

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print("PHASE0C2_ENVIRONMENT_OK=NO")
        return 1

    print("PHASE0C2_ENVIRONMENT_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
