#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE = "df6ceecc18242b22c8490d4b4fad5c096a2f86cf"

ALLOWED = {
    "docs/phase_history/PHASE6E_D_PRESENTATION_SKULL_CAVITY_POLISH.md",
    "scripts/check_phase6e_d_architecture.py",
    "scripts/check_phase6e_d_presentation_polish.mjs",
    "scripts/run_phase6e_d_checks.sh",
    "scripts/run_phase6e_d_previous_regression.py",
    "tests/test_phase6e_d_presentation_skull_cavity_polish.py",
    "web/index.html",
    "web/js/app.js",
    "web/js/reconstruction-surface-presentation.js",
    "web/js/segmentation-surface-viewer.js",
    "web/js/volume-surface-viewer.js",
}

FORBIDDEN = {
    "backend/voxelatlas/volume_surfaces.py",
    "backend/voxelatlas/segmentation_surfaces.py",
    "backend/voxelatlas/volume_rendering.py",
    "scripts/phase6d1_volume_surface_worker.py",
    "scripts/phase6a_surface_worker.py",
    "scripts/phase6b_surface_worker.py",
    "web/js/patient-volume-ray-marcher.js",
    "web/js/reconstruction-visualization-mode.js",
}


def changed_paths() -> set[str]:
    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
    ).splitlines()
    return {p for p in tracked + untracked if p}


def main() -> int:
    doc = (ROOT / "docs/phase_history/PHASE6E_D_PRESENTATION_SKULL_CAVITY_POLISH.md").read_text()
    shared = (ROOT / "web/js/reconstruction-surface-presentation.js").read_text()
    app = (ROOT / "web/js/app.js").read_text()

    assert EXPECTED_BASE in doc
    assert 'viewRelative: true' in shared
    assert 'syncToView(camera, focus)' in shared
    assert 'surfaceLightingRig.syncToView(camera, controls.target)' in app
    assert 'emissiveIntensity: 0.16' in shared
    assert 'emissiveIntensity: 0.08' in shared

    fidelity = shared[shared.index('  fidelity: Object.freeze({'):shared.index('  presentation: Object.freeze({')]
    assert 'sky: "#d8efff", ground: "#182332", intensity: 1.18' in fidelity
    assert 'color: "#e8e1d2"' in fidelity
    assert 'roughness: 0.62' in fidelity
    assert 'viewRelative: true' not in fidelity

    changed = changed_paths()
    unexpected = sorted(changed.difference(ALLOWED))
    assert not unexpected, f"6E-D contains unexpected changed paths: {unexpected}"
    touched = sorted(changed.intersection(FORBIDDEN))
    assert not touched, f"6E-D touched forbidden geometry/mode paths: {touched}"

    shared_lower = shared.lower()
    for token in ("fetch(", "/api/", "marching", "applymatrix4", "geometry.setattribute", "geometry.setindex"):
        assert token not in shared_lower, f"presentation module contains forbidden token: {token}"

    print("PHASE6E_D_ARCHITECTURE=PASS")
    print(f"EXPECTED_BASE={EXPECTED_BASE}")
    print("PRESENTATION_LIGHTING=VIEW_RELATIVE_KEY_FILL_RIM")
    print("PRESENTATION_SHADOW_LIFT=RESTRAINED_MATERIAL_ONLY")
    print("FIDELITY_REFERENCE=UNCHANGED")
    print("GEOMETRY_IMPLEMENTATION_TOUCHED=NO")
    print("RECONSTRUCTION_MODE_IMPLEMENTATION_TOUCHED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
