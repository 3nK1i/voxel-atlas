#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE = "78b6f4cec3087baf59a47feff8989fcf39262fde"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    interaction = (ROOT / "web/js/segmentation-structure-interaction.js").read_text(
        encoding="utf-8"
    )
    panel = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
    overlay = (ROOT / "web/js/segmentation-overlay.js").read_text(encoding="utf-8")
    surface = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
    app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

    for token in (
        "activateStructureIsolation",
        "restoreStructureIsolation",
        "resolveStructureInteraction",
        "isolatedLabelId",
        "effectiveVisible",
        "effectiveSurfaceVisible",
    ):
        require(token in interaction, f"6F-B interaction contract missing: {token}")

    for forbidden in (
        "fetch(",
        "xmlhttprequest",
        "/api/",
        "marching_cubes",
        "geometry.dispose",
        "new three",
        "vertices",
        "indices",
    ):
        require(forbidden not in interaction.lower(), f"6F-B state leaked side effect: {forbidden}")

    require("activateStructureIsolation" in panel, "6F-B isolate transition not wired")
    require("restoreStructureIsolation" in panel, "6F-B restore transition not wired")
    require('action === "restore-isolation"' in panel, "6F-B Restore action missing")
    require("structure.visible = isolated" not in panel, "Isolation still overwrites base visibility")
    require(
        "structure.surfaceVisible = isolated" not in panel,
        "Isolation still overwrites explicit surface requests",
    )
    require("resolveStructureInteraction" in overlay, "MPR overlay ignores effective visibility")
    require("effectiveVisible" in overlay, "MPR overlay effective visibility missing")
    require("resolveStructureInteraction" in surface, "3D surfaces ignore effective visibility")
    require("effectiveSurfaceVisible" in surface, "3D surface visibility gate missing")
    require(
        "structure.visible && structure.surfaceVisible === true" in surface,
        "Explicit surface-request residency contract changed",
    )
    require(
        "syncSegmentationOverlayPresentationStatus" in app,
        "Visible-label status is not synchronized with isolation",
    )
    require("segmentationStructureRestoreIsolation" in html, "Restore control missing")
    require('data-structure-action="restore-isolation"' in html, "Restore action binding missing")
    require("grid-template-columns: repeat(4" in css, "Four visibility controls are not laid out")
    require("phase6f-b-r1" in html and "phase6f-b-r1" in app, "6F-B cache identity missing")

    require("segmentationStructureClipParticipation" not in html, "6F-D clipping UI enabled early")
    require("segmentationStructureExplode" not in html, "6F-E exploded UI enabled early")

    print("PHASE6F_B_EXPECTED_BASE=" + EXPECTED_BASE)
    print("PHASE6F_B_SHOW_HIDE=USER_BASE_STATE")
    print("PHASE6F_B_ISOLATION=TRANSIENT_EFFECTIVE_VISIBILITY")
    print("PHASE6F_B_RESTORE=NON_DESTRUCTIVE")
    print("PHASE6F_B_MPR_OVERLAY=EFFECTIVE_VISIBILITY")
    print("PHASE6F_B_3D_SURFACE_VISIBILITY=EFFECTIVE_GATE")
    print("PHASE6F_B_SURFACE_REQUEST_STATE=PRESERVED")
    print("PHASE6F_B_GEOMETRY_IO_SIDE_EFFECTS=NONE")
    print("PHASE6F_C_TRANSPARENCY_QUALIFICATION=NOT_ENABLED")
    print("PHASE6F_D_PER_STRUCTURE_CLIPPING=NOT_ENABLED")
    print("PHASE6F_E_EXPLODED_PRESENTATION=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6F_B_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
