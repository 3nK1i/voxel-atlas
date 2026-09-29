#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MARKERS = (
    "STATUS=QUALIFIED",
    "SOURCE_MODALITY=CT",
    "SOURCE_UNITS=HU",
    "DIRECT_CT_ISOVALUE_HU=300",
    "GEOMETRY_CHAIN=PATIENT_LPS",
    "SOURCE_VOLUME=IMMUTABLE",
    "SOURCE_LABEL_MAP=IMMUTABLE",
    "PHASE6E_F_REAL_STUDY_QUALIFICATION_OK=YES",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the read-only Phase 6F-F real-study source gate by reusing the qualified Phase 6E-F source qualifier."
    )
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--surface-python", required=True)
    parser.add_argument("--label-map-id", required=True)
    parser.add_argument("--label-id", type=int, default=91)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dependency = ROOT / "scripts/qualify_phase6e_f_real_study.py"
    if not dependency.is_file():
        print("PHASE6F_F_REAL_STUDY_SOURCE_GATE_OK=NO")
        print(f"ERROR=missing dependency: {dependency}")
        return 2

    surface_python = Path(args.surface_python).expanduser()
    if not surface_python.is_file():
        print("PHASE6F_F_REAL_STUDY_SOURCE_GATE_OK=NO")
        print(f"ERROR=surface runtime not found: {surface_python}")
        return 2

    command = [
        sys.executable,
        str(dependency),
        "--data-dir",
        str(Path(args.data_dir).expanduser()),
        "--surface-python",
        str(surface_python),
        "--label-map-id",
        args.label_map_id,
        "--label-id",
        str(args.label_id),
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)

    print("===== PHASE 6F-F REAL-STUDY INTERACTION SOURCE QUALIFICATION =====")
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)

    if completed.returncode != 0:
        print(f"PHASE6E_F_DELEGATE_RC={completed.returncode}")
        print("PHASE6F_F_REAL_STUDY_SOURCE_GATE_OK=NO")
        return completed.returncode

    output = completed.stdout
    missing = [marker for marker in REQUIRED_MARKERS if marker not in output]
    if missing:
        print("MISSING_REQUIRED_MARKERS=" + ",".join(missing))
        print("PHASE6F_F_REAL_STUDY_SOURCE_GATE_OK=NO")
        return 1

    print("PHASE6E_F_SOURCE_QUALIFIER=REUSED_READ_ONLY")
    print("PHASE6F_INTERACTION_STACK=READY_FOR_MANUAL_MATRIX")
    print("SHOW_HIDE_ISOLATE_RESTORE=MANUAL_REQUIRED")
    print("OPACITY_ROUNDTRIP=MANUAL_REQUIRED")
    print("DIRECTIONAL_CUT_PARTICIPATION=MANUAL_REQUIRED")
    print("EXPLODED_PRESENTATION=MANUAL_REQUIRED")
    print("MODE_PROFILE_ROUNDTRIP=MANUAL_REQUIRED")
    print("REFINED_TO_ACCURATE_FALLBACK=MANUAL_REQUIRED")
    print("DIRECT_CT_300_HU_SLAB_ISSUE=DEFERRED_POST_PHASE6F")
    print("PHASE6G_QUANTITATIVE_SURFACE_TO_MASK_FIDELITY=NOT_RUN")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6F_F_REAL_STUDY_SOURCE_GATE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
