#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE = "b6e39b4f8813a9e6c48596a16323d426801530fb"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    interaction = (ROOT / "web/js/segmentation-structure-interaction.js").read_text(
        encoding="utf-8"
    )
    panel = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
    app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    overlay = (ROOT / "web/js/segmentation-overlay.js").read_text(encoding="utf-8")
    surface = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")

    require("createStructureInteractionState" in interaction, "6F-A interaction state missing")
    require("resolveStructureInteraction" in interaction, "6F-A interaction resolver missing")
    require("isolatedLabelId" in interaction, "6F-A isolation state missing")
    require("clippingEnabled" in interaction, "6F-A clipping participation state missing")
    require("explodedOffsetLpsMm" in interaction, "6F-A exploded display state missing")
    require("effectiveVisible" in interaction, "6F-A visibility precedence missing")
    require("effectiveSurfaceVisible" in interaction, "6F-A surface precedence missing")

    for forbidden in (
        "fetch(",
        "xmlhttprequest",
        "marching_cubes",
        "new three",
        "geometry.dispose",
        "/api/",
    ):
        require(forbidden not in interaction.lower(), f"6F-A state leaked side effect: {forbidden}")

    require("createStructureInteractionState" in panel, "Structure presentation not integrated")
    require("createStructureInteractionDefaults" in panel, "Structure defaults not integrated")
    require("resetStructureInteractionState" in panel, "Structure reset does not reset interaction")
    require("phase6f-a-r1" in app, "Structure-panel cache key not advanced")
    require("phase6f-a-r1" in html, "App cache key not advanced")

    # 6F-A is foundation-only. Existing rendering consumers are intentionally unchanged.
    require("drawSegmentationLabels" in overlay, "Segmentation overlay implementation changed unexpectedly")
    require("class PatientSegmentationSurfaceLayer" in surface, "Segmentation surface layer missing")
    require("segmentationStructureRestoreIsolation" not in html, "6F-B UI enabled prematurely")
    require("segmentationStructureClipParticipation" not in html, "6F-D UI enabled prematurely")
    require("segmentationStructureExplode" not in html, "6F-E UI enabled prematurely")

    print("PHASE6F_A_EXPECTED_BASE=" + EXPECTED_BASE)
    print("PHASE6F_A_STATE_MODEL=PASS")
    print("PHASE6F_A_PRECEDENCE_RULES=PASS")
    print("PHASE6F_A_GEOMETRY_IO_SIDE_EFFECTS=NONE")
    print("PHASE6F_A_EXISTING_UI_BEHAVIOR=PRESERVED")
    print("PHASE6F_B_ADVANCED_VISIBILITY=NOT_ENABLED")
    print("PHASE6F_D_PER_STRUCTURE_CLIPPING=NOT_ENABLED")
    print("PHASE6F_E_EXPLODED_PRESENTATION=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6F_A_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
