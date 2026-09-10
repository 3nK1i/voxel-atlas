#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/index.html").read_text(encoding="utf-8")
SEG = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
VOL = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")
CTRL = (ROOT / "web/js/reconstruction-visualization-mode.js").read_text(encoding="utf-8")
DOC = (ROOT / "docs/phase_history/PHASE6D2B_VOLUME_SURFACE_TRANSITIONS.md").read_text(encoding="utf-8")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"{label}=FAIL")
    print(f"{label}=PASS")


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


mode_request = block(APP, "function requestReconstructionVisualizationMode(", "function setVolumeAvailability(")
seg_visibility = block(SEG, "  setPresentationVisible(", "  _makeMaterial(")
vol_visibility = block(VOL, "  setPresentationVisible(", "  async build(")
volume_visibility = block(APP, "function applyVolumeVisibility()", "function updateVolumeBounds()")

require("ReconstructionVisualizationModeController" in APP, "PHASE6D2B_CONTROLLER_INTEGRATION")
require(all(f'data-reconstruction-mode="{mode}"' in INDEX for mode in ("volume", "surface", "combined")), "PHASE6D2B_VISIBLE_MODE_IDENTITIES")
combined_window = INDEX[INDEX.index('data-reconstruction-mode="combined"') - 180:INDEX.index('data-reconstruction-mode="combined"') + 220]
require("disabled" in combined_window, "PHASE6D2B_COMBINED_DEFERRED")
require('setPresentationVisible(snapshot.visibility.surfaceSources["volume-derived"])' in APP, "PHASE6D2B_VOLUME_SURFACE_VISIBILITY_WIRED")
require('setPresentationVisible(snapshot.visibility.surfaceSources["segmentation-derived"])' in APP, "PHASE6D2B_SEGMENTATION_SURFACE_VISIBILITY_WIRED")
require("_abortPending" not in seg_visibility and "clear()" not in seg_visibility and "dispose" not in seg_visibility.lower(), "PHASE6D2B_SEGMENTATION_HIDE_NONDESTRUCTIVE")
require("abort" not in vol_visibility.lower() and "_disposeCurrent" not in vol_visibility and "clearSurface" not in vol_visibility, "PHASE6D2B_VOLUME_HIDE_NONDESTRUCTIVE")
require("fetch(" not in mode_request.lower() and ".build(" not in mode_request and ".clear(" not in mode_request, "PHASE6D2B_MODE_SWITCH_NO_GEOMETRY_WORK")
require("state.opacity > 0.001" in volume_visibility and "snapshot.visibility.volume" in volume_visibility, "PHASE6D2B_VOLUME_OPACITY_POLICY_PRESERVED")
require('value="300"' in INDEX and "Bone baseline: 300 HU when in range" in INDEX, "PHASE6D2B_PHASE6D1_300HU_BASELINE_PRESERVED")
require("fetch(" not in CTRL.lower() and "/api/" not in CTRL.lower(), "PHASE6D2A_PRESENTATION_ONLY_PRESERVED")
require("Combined remains visibly disabled until Phase 6D2C" in DOC, "PHASE6D2B_6D2C_BOUNDARY")
require("Phase 6E" in DOC and "Phase 6F" in DOC, "PHASE6D2B_LATER_PHASE_BOUNDARY")
require("Clinical validation is not claimed" in DOC, "CLINICAL_VALIDATION_NOT_CLAIMED")
print("PHASE6D2B_ARCHITECTURE_OK=YES")
