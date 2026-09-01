#!/usr/bin/env python3
"""Regression probe for the Three.js workspace foundation after Phase 2B evolution."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> int:
    print(f"FAIL {message}")
    print("PHASE2A_WORKSPACE_OK=NO")
    return 1


def main() -> int:
    print("===== PHASE 2A WORKSPACE FOUNDATION REGRESSION =====")

    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
    login_html = (ROOT / "web/login.html").read_text(encoding="utf-8")

    required_html = (
        'data-workspace="voxelatlas-v1"',
        'id="viewport"',
        'id="sectionSlider"',
        'data-section-axis="y"',
        'data-section-axis="z"',
        'data-section-axis="x"',
        'data-layer="skull"',
        'id="opacitySlider"',
        'id="logoutButton"',
    )
    if any(marker not in html for marker in required_html):
        return fail("workspace_contract=missing_foundation")
    print("PASS workspace_contract=threejs_foundation")

    retired_ui = ("model-viewer", "View in AR", "Premium XR", "Holographic", "data-preset")
    if any(marker.lower() in html.lower() for marker in retired_ui):
        return fail("workspace_contract=retired_presentation_present")
    print("PASS workspace_contract=focused_clinical_ui")

    specialized_markers = (
        "cran" + "ial",
        "aper" + "ture",
        "cut" + "away",
        "opening" + "Slider",
        "opening" + "Value",
        "opening" + "Description",
        "skull_" + "open",
    )
    combined = (html + "\n" + js).lower()
    if any(marker.lower() in combined for marker in specialized_markers):
        return fail("workspace_contract=retired_specialized_cut_present")
    print("PASS workspace_contract=directional_cut_only")

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
        return fail("viewer_behavior=camera_framing_missing")
    print("PASS viewer_behavior=ergonomic_initial_framing")

    for marker in ("renderer.localClippingEnabled", "sectionPlane", "MeshPhysicalMaterial", "0xe8e1d6"):
        if marker not in js:
            return fail(f"viewer_behavior=missing_{marker}")
    print("PASS viewer_behavior=directional_section_clinical_rendering")

    if any(marker in js for marker in ("AR_URL", "activateAR", "presetButtons", "applyPreset")):
        return fail("viewer_behavior=retired_code_present")
    print("PASS viewer_behavior=no_ar_no_presets")

    retired_paths = (
        ROOT / "prototypes/v2b3a",
        ROOT / "prototypes/v2b3b",
        ROOT / ("web/assets/models/skull_" + "open.glb"),
    )
    if any(path.exists() for path in retired_paths):
        return fail("retirement=incomplete")
    print("PASS retirement=legacy_specialized_paths_absent")

    print("PHASE2A_WORKSPACE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
