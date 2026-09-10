#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/index.html").read_text(encoding="utf-8")
CTRL = (ROOT / "web/js/reconstruction-visualization-mode.js").read_text(encoding="utf-8")
DOC = (ROOT / "docs/phase_history/PHASE6D2C_COMBINED_VISUALIZATION.md").read_text(encoding="utf-8")
CSS = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"{label}=FAIL")
    print(f"{label}=PASS")


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


combined_marker = 'data-reconstruction-mode="combined"'
combined_at = INDEX.index(combined_marker)
combined_left = INDEX.rfind("<button", 0, combined_at)
combined_right = INDEX.index("</button>", combined_at) + len("</button>")
combined_button = INDEX[combined_left:combined_right]
mode_request = block(APP, "function requestReconstructionVisualizationMode(", "function requestReconstructionSurfaceSourceSelection(")
source_request = block(APP, "function requestReconstructionSurfaceSourceSelection(", "function setVolumeAvailability(")
resource_sync = block(APP, "function syncReconstructionVisualizationResources()", "function requestReconstructionVisualizationMode(")

require("disabled" not in combined_button, "PHASE6D2C_COMBINED_NOT_HARD_DISABLED")
require("snapshot.canCombined" in APP, "PHASE6D2C_COMBINED_CAPABILITY_WIRED")
require('data-reconstruction-surface-source="volume-derived"' in INDEX, "PHASE6D2C_DIRECT_CT_SOURCE_CONTROL")
require('data-reconstruction-surface-source="segmentation-derived"' in INDEX, "PHASE6D2C_SEGMENTATION_SOURCE_CONTROL")
require("surfaceSourceSelection" in resource_sync and '"volume-derived"' in resource_sync and '"segmentation-derived"' in resource_sync, "PHASE6D2C_SOURCE_PREFERENCE_WIRED")
require("state.segmentationSurface.enabled" in resource_sync, "PHASE6D2C_SEGMENTATION_SHOW_LIFECYCLE_RESPECTED")
require("fetch(" not in mode_request.lower() and ".build(" not in mode_request and ".clear(" not in mode_request, "PHASE6D2C_MODE_SWITCH_NO_GEOMETRY_WORK")
require("fetch(" not in source_request.lower() and ".build(" not in source_request and ".clear(" not in source_request, "PHASE6D2C_SOURCE_SWITCH_NO_GEOMETRY_WORK")
require("fetch(" not in CTRL.lower() and "/api/" not in CTRL.lower(), "PHASE6D2A_PRESENTATION_ONLY_PRESERVED")
require('snapshot.mode === "combined"' in APP and "selectedResidentSurfaceSources" in APP, "PHASE6D2C_TRUTHFUL_COMBINED_STATUS")
require("reconstruction-source-option" in CSS and "var(--panel-soft)" in CSS and "var(--accent-bg)" in CSS, "PHASE6D2C_THEME_NATIVE_SOURCE_CONTROLS")
require('value="300"' in INDEX and "Bone baseline: 300 HU when in range" in INDEX, "PHASE6D2C_300HU_BASELINE_PRESERVED")
require("6D2D" in DOC, "PHASE6D2C_6D2D_BOUNDARY")
require("Phase 6E" in DOC and "Phase 6F" in DOC, "PHASE6D2C_LATER_PHASE_BOUNDARY")
require("Clinical validation is not claimed" in DOC, "CLINICAL_VALIDATION_NOT_CLAIMED")
print("PHASE6D2C_ARCHITECTURE_OK=YES")
