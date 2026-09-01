#!/usr/bin/env python3
"""Validate the locked Phase 2B V1 workspace target contract."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "design/reference/workspace_v1_target.png"
TARGET_SHA256 = "02994e3e1bd56e914d4da1c442c1037346699f67ddeffd6c47d962656af92c9d"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> int:
    print(f"FAIL {message}")
    print("PHASE2B_FINAL_WORKSPACE_OK=NO")
    return 1


def main() -> int:
    print("===== PHASE 2B FINAL V1 WORKSPACE TARGET =====")

    if not TARGET.is_file() or sha256(TARGET) != TARGET_SHA256:
        return fail("visual_target=fingerprint_mismatch")
    print("PASS visual_target=authoritative_fingerprint")

    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
    js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

    required_html = (
        'data-workspace="voxelatlas-v1"',
        'id="themeToggle"',
        'id="workflowData"',
        'id="workflowReconstruction"',
        'id="workflowVisualization"',
        'id="uploadDicomButton"',
        'id="studyPanel"',
        'id="reconstructionPanel"',
        'id="viewerStage"',
        'id="viewport"',
        'id="mprAxial"',
        'id="mprCoronal"',
        'id="mprSagittal"',
        'id="directionalCutPanel"',
        'id="anatomicalLayersPanel"',
        'id="opacitySlider"',
        'id="resetButton"',
        'id="autoRotateButton"',
        'id="logoutButton"',
    )
    if any(marker not in html for marker in required_html):
        return fail("workspace_shell=missing_target_region")
    print("PASS workspace_shell=locked_target_regions")

    visual_density_markers = (
        "--header-height: 72px;",
        "--left-width: clamp(250px, 17vw, 330px);",
        "--right-width: clamp(285px, 19vw, 360px);",
        "width: calc(100% - 16px);",
        "grid-template-rows: minmax(320px, 1fr) minmax(220px, 34%);",
    )
    if any(marker not in css for marker in visual_density_markers):
        return fail("visual_density=desktop_target_scale_missing")
    print("PASS visual_density=target_scaled_desktop")

    if '[data-theme="dark"]' not in css or '[data-theme="light"]' not in css:
        return fail("theme=missing_dark_or_light")
    if "voxelatlas-theme" not in js or "themeToggle" not in js:
        return fail("theme=missing_runtime_toggle")
    print("PASS theme=dark_light_runtime_toggle")

    if html.count('data-volume-state="empty"') != 3:
        return fail("mpr=empty_state_contract_missing")
    if "DICOM volume not loaded" not in html:
        return fail("mpr=truthful_placeholder_missing")
    if 'id="uploadDicomButton"' not in html or "Phase 3" not in html:
        return fail("dicom=planned_state_missing")
    print("PASS medical_data=truthful_pre_ingestion_states")

    for marker in (
        'data-layer="volume"',
        'data-layer="skull"',
        'data-layer="brain"',
        'data-layer="combined"',
        'data-future-layer="skin"',
        'data-future-layer="sinuses"',
        'data-future-layer="vessels"',
    ):
        if marker not in html:
            return fail(f"layers=missing_{marker}")
    if "layerRegistry" not in js or "registerLayer" not in js or "setLayerAvailability" not in js:
        return fail("layers=runtime_registry_missing")
    if "/assets/models/brain.glb" in js:
        return fail("layers=static_brain_dependency_present")
    print("PASS layers=extensible_truthful_registry")

    if "renderer.localClippingEnabled" not in js or "sectionPlane" not in js:
        return fail("directional_cut=runtime_missing")
    if any(marker not in html for marker in ('data-section-axis="y"', 'data-section-axis="z"', 'data-section-axis="x"')):
        return fail("directional_cut=axis_controls_missing")
    print("PASS directional_cut=only_v1_sectioning_control")

    retired_terms = (
        "cran" + "ial",
        "aper" + "ture",
        "cut" + "away",
        "opening" + "Slider",
        "opening" + "Value",
        "opening" + "Description",
        "skull_" + "open",
    )
    production = (html + "\n" + js).lower()
    if any(term.lower() in production for term in retired_terms):
        return fail("retirement=specialized_behavior_present")

    retired_paths = (
        ROOT / "prototypes/v2b3a",
        ROOT / "prototypes/v2b3b",
        ROOT / "scripts/check_v2b3a_prototype.py",
        ROOT / "scripts/check_v2b3b_prototype.py",
        ROOT / ("web/assets/models/skull_" + "open.glb"),
    )
    if any(path.exists() for path in retired_paths):
        return fail("retirement=legacy_path_present")
    print("PASS retirement=specialized_legacy_paths_absent")

    if any(marker.lower() in production for marker in ("view in ar", "premium xr", "holographic", "data-preset")):
        return fail("scope=non_v1_presentation_present")
    if "—" in html or "—" in js:
        return fail("copy=em_dash_present")
    print("PASS scope=clinical_only_plain_copy")

    toolbar_markers = (
        "fitViewButton.addEventListener",
        "zoomInButton.addEventListener",
        "zoomOutButton.addEventListener",
        "fullscreenButton.addEventListener",
        "requestFullscreen",
    )
    if any(marker not in js for marker in toolbar_markers):
        return fail("viewer_toolbar=handler_missing")
    print("PASS viewer_toolbar=real_controls")

    print("PHASE2B_FINAL_WORKSPACE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
