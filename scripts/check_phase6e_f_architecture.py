#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE = "40937d706a7b54f3f23f882c9195ab5ed4992dc8"

QUALIFICATION_ONLY_ALLOWED_PATHS = {
    "docs/phase_history/PHASE6E_F_FINAL_REAL_STUDY_QUALIFICATION_AND_CLOSURE.md",
    "scripts/check_phase6e_f_architecture.py",
    "scripts/qualify_phase6e_f_real_study.py",
    "scripts/run_phase6e_f_checks.sh",
    "scripts/run_phase6e_f_previous_regression.py",
    "tests/test_phase6e_f_final_real_study_qualification.py",
}

PROTECTED_PRODUCTION_PATHS = {
    "backend/voxelatlas/volume_rendering.py",
    "backend/voxelatlas/volume_surfaces.py",
    "backend/voxelatlas/segmentation_surfaces.py",
    "web/index.html",
    "web/js/app.js",
    "web/js/patient-volume-ray-marcher.js",
    "web/js/volume-surface-viewer.js",
    "web/js/segmentation-surface-viewer.js",
    "web/js/reconstruction-visualization-mode.js",
    "web/js/reconstruction-presentation-profile.js",
    "web/js/reconstruction-surface-presentation.js",
    "web/js/reconstruction-combined-presentation.js",
}


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def changed_paths() -> set[str]:
    commands = (
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    changed: set[str] = set()
    for command in commands:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return changed


def main() -> int:
    changed = changed_paths()
    if changed != QUALIFICATION_ONLY_ALLOWED_PATHS:
        unexpected = sorted(changed - QUALIFICATION_ONLY_ALLOWED_PATHS)
        missing = sorted(QUALIFICATION_ONLY_ALLOWED_PATHS - changed)
        raise SystemExit(
            "6E-F must be a qualification-only six-file delta; "
            f"unexpected={unexpected}; missing={missing}"
        )
    if changed & PROTECTED_PRODUCTION_PATHS:
        raise SystemExit("6E-F changed protected production rendering/geometry implementation")

    index = text("web/index.html")
    profile = text("web/js/reconstruction-presentation-profile.js")
    surface_policy = text("web/js/reconstruction-surface-presentation.js")
    combined = text("web/js/reconstruction-combined-presentation.js")
    app = text("web/js/app.js")

    if 'value="300"' not in index or "Bone baseline: 300 HU when in range" not in index:
        raise SystemExit("Locked Direct CT 300 HU baseline changed")
    if "fidelity" not in profile.lower() or "presentation" not in profile.lower():
        raise SystemExit("Fidelity/Presentation profile architecture is unavailable")
    if "applySegmentationSurfaceMaterialProfile" not in surface_policy:
        raise SystemExit("Shared segmentation material presentation policy is unavailable")
    for token in (
        "volumeOpacityMultiplier: 0.78",
        "directCtSurfaceOpacity: 0.84",
        "volumeOpacityMultiplier: 0.62",
        "directCtSurfaceOpacity: 0.72",
        "segmentationOpacityMultiplier: 1",
    ):
        if token not in combined:
            raise SystemExit(f"Qualified 6E-E combined composition changed: {token}")
    if "resolveCombinedPresentationBalance" not in app:
        raise SystemExit("Qualified 6E-E composition is not wired into the application")

    print("PHASE6E_F_ARCHITECTURE=PASS")
    print(f"EXPECTED_BASE={EXPECTED_BASE}")
    print("QUALIFICATION_ONLY_DELTA=YES")
    print("PRODUCTION_RENDERING_CHANGED=NO")
    print("GEOMETRY_IMPLEMENTATION_CHANGED=NO")
    print("DIRECT_CT_DEFAULT_HU=300")
    print("FIDELITY_PRESENTATION_ARCHITECTURE=PRESERVED")
    print("COMBINED_COMPOSITION_POLICY=PRESERVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
