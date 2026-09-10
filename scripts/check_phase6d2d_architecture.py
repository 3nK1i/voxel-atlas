#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
CTRL = (ROOT / "web/js/reconstruction-visualization-mode.js").read_text(encoding="utf-8")
DOC = (ROOT / "docs/phase_history/PHASE6D2D_RESET_STUDY_ERROR_CLOSURE.md").read_text(encoding="utf-8")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"{label}=FAIL")
    print(f"{label}=PASS")


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


left_start = INDEX.index('id="reconstructionPanel"')
left_end = INDEX.index('</section>', left_start)
left = INDEX[left_start:left_end]
right_start = INDEX.index('id="reconstructionVisualizationPanel"')
right_end = INDEX.index('</section>', right_start)
right = INDEX[right_start:right_end]
apply_snapshot = block(APP, "function applyReconstructionVisualizationSnapshot(", "function syncReconstructionVisualizationResources()")
reset_workspace = block(APP, "function resetWorkspace()", "function preferredTheme()")
study_reset = block(APP, "function resetReconstructionVisualizationForStudy()", "function clearPatientVolumeRendering()")
build_surface = block(APP, "async function requestVolumeSurfaceBuild()", "function clearVolumeDerivedSurface()")
clear_surface = block(APP, "function clearVolumeDerivedSurface()", "function clearSegmentationWorkflowPoll()")

require(left.count('data-reconstruction-mode=') == 3, "PHASE6D2D_LEFT_MODE_CARD_COUNT")
require(all(f'data-reconstruction-mode="{mode}"' in left for mode in ("volume", "surface", "combined")), "PHASE6D2D_LEFT_MODE_CARDS")
require("reconstruction-mode-icon-volume" in left and "reconstruction-mode-icon-surface" in left and "reconstruction-mode-icon-combined" in left, "PHASE6D2D_DISTINCT_LOCAL_MODE_ICONS")
require('data-reconstruction-mode=' not in right and "reconstruction-mode-switch" not in right, "PHASE6D2D_RIGHT_MODE_SWITCH_REMOVED")
require('data-reconstruction-surface-source="volume-derived"' in right and 'data-reconstruction-surface-source="segmentation-derived"' in right, "PHASE6D2D_RIGHT_SOURCE_CONTROLS_PRESERVED")
require('button.dataset.active = String(snapshot.mode === modeId && available)' in apply_snapshot, "PHASE6D2D_SINGLE_ACTIVE_MODE_STATE")
require('.reconstruction-mode-card[data-active="true"] .readiness-check' in CSS and '.reconstruction-mode-card[data-active="false"] .readiness-check' in CSS, "PHASE6D2D_ACTIVE_GREEN_CHECK_POLICY")
require("surfaceModeStatusText" in apply_snapshot and "combinedModeStatusText" in apply_snapshot, "PHASE6D2D_TRUTHFUL_CARD_STATUS")
require('requestReconstructionVisualizationMode("volume")' in reset_workspace and "fetch(" not in reset_workspace.lower() and ".build(" not in reset_workspace, "PHASE6D2D_RESET_PRESENTATION_ONLY")
require("DEFAULT_RECONSTRUCTION_SURFACE_SOURCE_SELECTION" in study_reset and "reconstructionVisualizationController?.reset()" in study_reset, "PHASE6D2D_STUDY_CHANGE_DETERMINISTIC_RESET")
require("requestReconstructionVisualizationMode" not in build_surface and "requestReconstructionVisualizationMode" not in clear_surface, "PHASE6D2D_BUILD_REMOVE_RECONCILE_VIA_RESOURCES")
require("fetch(" not in CTRL.lower() and "/api/" not in CTRL.lower(), "PHASE6D2_PRESENTATION_CONTROLLER_STILL_IO_FREE")
require("Surface source selections apply in Surface and Combined modes" in INDEX, "PHASE6D2D_SOURCE_SCOPE_EXPLAINED")
require("phase6d2d-r1" in INDEX, "PHASE6D2D_BROWSER_CACHE_BOUNDARY")
require('value="300"' in INDEX and "Bone baseline: 300 HU when in range" in INDEX, "PHASE6D1_300HU_BASELINE_PRESERVED")
require("Phase 6E" in DOC and "Phase 6F" in DOC, "PHASE6D2D_LATER_PHASE_BOUNDARY")
require("Clinical validation is not claimed" in DOC, "CLINICAL_VALIDATION_NOT_CLAIMED")
print("PHASE6D2D_ARCHITECTURE_OK=YES")
