#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE = "51d276b903ada7eac904b9f73f17881673d45918"


def changed_paths() -> set[str]:
    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
    ).splitlines()
    return {p for p in tracked + untracked if p}


def main() -> int:
    doc = (ROOT / "docs/phase_history/PHASE6E_C_FIDELITY_PROFILE_QUALIFICATION.md").read_text()
    css = (ROOT / "web/css/styles.css").read_text()
    index = (ROOT / "web/index.html").read_text()
    profile = (ROOT / "web/js/reconstruction-presentation-profile.js").read_text()
    shared = (ROOT / "web/js/reconstruction-surface-presentation.js").read_text()

    assert EXPECTED_BASE in doc
    assert "Phase 6E-C — reconstruction-card border consistency" in css
    assert 'data-state="ready"]:not([data-active="true"])' in css
    assert 'data-capability="ready"]:not([data-active="true"])' in css
    assert "phase6e-c-r1" in index
    assert "Neutral reference rendering for clear geometry-first inspection." in profile
    assert 'id: "fidelity"' in shared
    assert 'color: "#e8e1d2"' in shared
    assert 'roughness: 0.62' in shared

    forbidden = {
        "backend/voxelatlas/volume_surfaces.py",
        "backend/voxelatlas/segmentation_surfaces.py",
        "backend/voxelatlas/volume_rendering.py",
        "scripts/phase6d1_volume_surface_worker.py",
        "scripts/phase6a_surface_worker.py",
        "scripts/phase6b_surface_worker.py",
        "web/js/patient-volume-ray-marcher.js",
        "web/js/reconstruction-visualization-mode.js",
    }
    changed = changed_paths()
    touched = sorted(changed.intersection(forbidden))
    assert not touched, f"6E-C touched forbidden geometry/mode paths: {touched}"

    print("PHASE6E_C_ARCHITECTURE=PASS")
    print(f"EXPECTED_BASE={EXPECTED_BASE}")
    print("FIDELITY_REFERENCE=DETERMINISTIC_NEUTRAL_PRE_6E_BASELINE")
    print("RECONSTRUCTION_CARD_NONACTIVE_BORDER=UNIFORM_NEUTRAL")
    print("ACTIVE_MODE_INDICATOR=ACTIVE_EMPHASIS_PLUS_SINGLE_GREEN_CHECK")
    print("GEOMETRY_IMPLEMENTATION_TOUCHED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
