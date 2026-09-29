#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def changed_paths() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def main() -> int:
    app = text("web/js/app.js")
    balance = text("web/js/reconstruction-combined-presentation.js")
    volume_surface = text("web/js/volume-surface-viewer.js")
    protected = {
        "backend/voxelatlas/volume_surfaces.py",
        "backend/voxelatlas/segmentation_surfaces.py",
        "backend/voxelatlas/volume_rendering.py",
        "scripts/phase6d1_volume_surface_worker.py",
        "scripts/phase6a_surface_worker.py",
        "scripts/phase6b_surface_worker.py",
        "web/js/patient-volume-ray-marcher.js",
        "web/js/reconstruction-visualization-mode.js",
        "web/js/segmentation-surface-viewer.js",
        "web/js/reconstruction-surface-presentation.js",
    }
    if changed_paths() & protected:
        raise SystemExit("6E-E changed protected geometry/profile/segmentation implementation")
    for forbidden in ("fetch(", "/api/", "marching", "geometry.", "applyMatrix4", "setAttribute"):
        if forbidden in balance:
            raise SystemExit(f"6E-E balance policy contains forbidden operation: {forbidden}")
    if "resolveCombinedPresentationBalance" not in app:
        raise SystemExit("6E-E balance policy is not wired into the application")
    if "setPresentationOpacity(opacity)" not in volume_surface:
        raise SystemExit("Direct CT layer lacks non-destructive presentation opacity")
    print("PHASE6E_E_ARCHITECTURE=PASS")
    print("GEOMETRY_IMPLEMENTATION_CHANGED=NO")
    print("SEGMENTATION_SURFACE_IMPLEMENTATION_CHANGED=NO")
    print("FIDELITY_PRESENTATION_MATERIAL_POLICY_CHANGED=NO")
    print("COMBINED_BALANCE_SCOPE=VOLUME_ALPHA_PLUS_DIRECT_CT_ALPHA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
