#!/usr/bin/env python3
"""Controlled MRI-only weight acquisition, expressly opted in; never runs inference."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.mri_weights_qualification import (  # noqa: E402
    MRIAssetError, download_commands, mri_environment, paths_for,
    prepare_mri_root, require_mri_runtime_and_mapping, seal_mri_weights,
    verify_mri_weights,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="6J-C2 MRI-specific model asset qualification")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--python", required=True, help="Dedicated MRI TotalSegmentator interpreter")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true", help="Read-only local asset and manifest check")
    mode.add_argument("--accept-download", action="store_true", help="Authorize MRI model downloads and sealed asset manifest")
    parser.add_argument("--timeout-seconds", type=int, default=21600)
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 86400:
        parser.error("timeout must be 30..86400 seconds")
    print("===== PHASE 6J-C2 MRI MODEL ASSETS =====", flush=True)
    try:
        paths = paths_for(args.data_dir)
        require_mri_runtime_and_mapping(args.python)
        print("MRI_INSTALLED_TASK_AND_RUNTIME=PASS", flush=True)
        if args.inspect:
            try:
                manifest = verify_mri_weights(paths)
            except MRIAssetError:
                print("MRI_MODEL_ASSET_STATUS=UNQUALIFIED_OR_NOT_SEALED", flush=True)
                print("MRI_EXECUTION_ENABLED=NO", flush=True)
                return 0
        else:
            if paths.manifest.exists() or paths.manifest.is_symlink():
                manifest = verify_mri_weights(paths)
                print("MRI_MODEL_ASSET_STATUS=ALREADY_SEALED", flush=True)
            else:
                prepare_mri_root(paths)
                environment = mri_environment(paths)
                # Log internally, do not print paths, model-provider stderr or user data.
                log_path = paths.root / "acquisition.log"
                if log_path.is_symlink() or (log_path.exists() and not log_path.is_file()):
                    raise MRIAssetError("MRI acquisition log path is unsafe")
                descriptor = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
                with os.fdopen(descriptor, "ab") as log:
                    for command in download_commands(args.python):
                        print("MRI_WEIGHT_DOWNLOAD_IN_PROGRESS=YES", flush=True)
                        try:
                            result = subprocess.run(command, env=environment, cwd=paths.root,
                                                    stdout=log, stderr=subprocess.STDOUT,
                                                    timeout=args.timeout_seconds, shell=False,
                                                    check=False)
                        except (OSError, subprocess.SubprocessError) as exc:
                            raise MRIAssetError("MRI model download failed or timed out; see private acquisition log") from exc
                        if result.returncode != 0:
                            raise MRIAssetError("MRI model download failed; see private acquisition log")
                manifest = seal_mri_weights(paths)
                manifest = verify_mri_weights(paths)
        print("MRI_MODEL_ASSET_STATUS=SEALED_AND_VERIFIED")
        print("MRI_MODEL_DATASET_IDS=850,851,852,853")
        print("MRI_MODEL_FILE_COUNT=" + str(len(manifest["files"])))
        print("MRI_MODEL_TOTAL_BYTES=" + str(manifest["total_bytes"]))
        print("MRI_MODEL_MANIFEST_SHA256=" + str(manifest["manifest_sha256"]))
        print("MRI_EXECUTION_ENABLED=NO")
        print("REAL_MODEL_INFERENCE=NOT_RUN")
        return 0
    except MRIAssetError as exc:
        print("MRI_MODEL_ASSET_STATUS=NOT_QUALIFIED")
        print("MESSAGE=" + str(exc))
        print("MRI_EXECUTION_ENABLED=NO")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
