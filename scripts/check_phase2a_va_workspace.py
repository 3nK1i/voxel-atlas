#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VA_HASHES = {
    "prototypes/v2b3a/index.html": "cc7f063fb7304eea2af79b515ed497027ecaa9182871adfba022085fccb23240",
    "prototypes/v2b3a/styles.css": "fb97bf91d78810e7ba7d153dd638e07401d963c849fb24574af53cd05dd9b235",
    "prototypes/v2b3a/app.js": "3931d8e39cb830f97304a22231906b724525c126f77269901ef3283e58a138c5",
    "prototypes/v2b3a/assets/skull_full.glb": "23006cc79f7bb81539f9d3dd09e44901a9959f9094074ae74a12e6d364919ac4",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> int:
    print(f"FAIL {message}")
    print("PHASE2A_VA_WORKSPACE_OK=NO")
    return 1


def main() -> int:
    print("===== PHASE 2A VA WORKSPACE MIGRATION =====")

    for relative, expected in VA_HASHES.items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            return fail(f"va_reference={relative}")
    print("PASS va_reference=byte_preserved")

    if (ROOT / "prototypes/v2b3b").exists() or (ROOT / "scripts/check_v2b3b_prototype.py").exists():
        return fail("vb_retirement=incomplete")
    print("PASS vb_retirement=complete")

    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

    required_html = (
        'data-workspace="voxelatlas-va"',
        'id="openingSlider"',
        'id="sectionSlider"',
        'data-layer="skull"',
        'data-layer="brain" disabled',
        'data-layer="combined" disabled',
        'id="opacitySlider"',
        'id="logoutButton"',
        '>\n          Logout\n        </button>',
    )
    if any(marker not in html for marker in required_html):
        return fail("workspace_contract=missing_control")
    print("PASS workspace_contract=va_shell")

    forbidden = ("model-viewer", "View in AR", "Premium XR", "Holographic", "data-preset")
    if any(marker.lower() in html.lower() for marker in forbidden):
        return fail("workspace_contract=retired_feature_present")
    print("PASS workspace_contract=no_ar_no_presets")

    login_html = (ROOT / "web/login.html").read_text(encoding="utf-8")
    if '<h1 id="loginTitle">Login</h1>' not in login_html or "Welcome Back" in login_html:
        return fail("login_copy=not_concise")
    print("PASS login_copy=concise")

    if "<title>VoxelAtlas - Anatomy Workspace</title>" not in html:
        return fail("app_copy=workspace_title_not_normalized")
    if "<title>VoxelAtlas - Login</title>" not in login_html:
        return fail("app_copy=login_title_not_normalized")
    if "—" in html or "—" in login_html:
        return fail("app_copy=em_dash_present")
    print("PASS app_copy=plain_hyphens")

    camera_markers = (
        "radius * 1.30",
        "radius * 0.42",
        "radius * 2.55",
        "radius * 1.15",
        "radius * 8",
    )
    if any(marker not in js for marker in camera_markers):
        return fail("viewer_behavior=va_camera_framing_missing")
    if "radius * 0.84" in js or "radius * 1.50" in js:
        return fail("viewer_behavior=oversized_initial_framing_present")
    print("PASS viewer_behavior=va_initial_framing")

    for marker in ("uApertureCenter", "uApertureMaxRadii", "renderer.localClippingEnabled", "sectionPlane"):
        if marker not in js:
            return fail(f"viewer_behavior=missing_{marker}")
    print("PASS viewer_behavior=aperture_plus_directional_section")

    if any(marker in js for marker in ("AR_URL", "activateAR", "presetButtons", "applyPreset")):
        return fail("viewer_behavior=retired_code_present")
    print("PASS viewer_behavior=clinical_only")

    brain_readme = ROOT / "web/assets/models/README.md"
    if not brain_readme.is_file() or "brain.glb" not in brain_readme.read_text(encoding="utf-8"):
        return fail("anatomy_layers=brain_contract_missing")
    print("PASS anatomy_layers=skull_ready_brain_explicit")

    print("PHASE2A_VA_WORKSPACE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
