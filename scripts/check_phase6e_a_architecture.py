#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
CTRL = (ROOT / "web/js/reconstruction-presentation-profile.js").read_text(encoding="utf-8")
DOC = (ROOT / "docs/phase_history/PHASE6E_A_PRESENTATION_PROFILE_ARCHITECTURE.md").read_text(encoding="utf-8")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"{label}=FAIL")
    print(f"{label}=PASS")


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


right_start = INDEX.index('id="reconstructionVisualizationPanel"')
right_end = INDEX.index('</section>', right_start)
right = INDEX[right_start:right_end]
left_start = INDEX.index('id="reconstructionPanel"')
left_end = INDEX.index('</section>', left_start)
left = INDEX[left_start:left_end]
profile_apply = block(APP, "function applyReconstructionPresentationProfileSnapshot(", "function requestReconstructionPresentationProfile(")
profile_request = block(APP, "function requestReconstructionPresentationProfile(", "function applyReconstructionVisualizationSnapshot(")

require('id: "fidelity"' in CTRL and 'id: "presentation"' in CTRL, "PHASE6E_A_EXACT_PROFILE_CATALOG")
require('this.profile = "fidelity"' in CTRL, "PHASE6E_A_FIDELITY_DEFAULT")
require('data-reconstruction-presentation-profile="fidelity"' in right and 'data-reconstruction-presentation-profile="presentation"' in right, "PHASE6E_A_RIGHT_3D_PROFILE_CONTROL")
require('data-reconstruction-presentation-profile=' not in left, "PHASE6E_A_LEFT_MODE_CARDS_UNCHANGED")
require("ReconstructionPresentationProfileController" in APP and "reconstructionPresentationProfileController" in APP, "PHASE6E_A_APP_PROFILE_WIRING")
require("requestReconstructionVisualizationMode" not in profile_apply + profile_request and "requestReconstructionSurfaceSourceSelection" not in profile_apply + profile_request, "PHASE6E_A_MODE_SOURCE_STATE_SEPARATE")
require(all(token not in CTRL.lower() for token in ("fetch(", "/api/", "marching", "segmentation-workflow", ".build(")), "PHASE6E_A_CONTROLLER_IO_FREE")
require(all(token not in profile_apply.lower() for token in ("fetch(", ".build(", "material", "light")), "PHASE6E_A_NO_LIGHT_MATERIAL_APPLICATION_YET")
require("Geometry and source data remain unchanged" in INDEX, "PHASE6E_A_GEOMETRY_IMMUTABILITY_EXPLAINED")
require("reconstruction-presentation-profile-option" in CSS, "PHASE6E_A_PROFILE_UI_STYLED")
require(INDEX.count('data-reconstruction-mode=') == 3, "PHASE6D2_MODE_CARDS_PRESERVED")
require('data-reconstruction-surface-source="volume-derived"' in INDEX and 'data-reconstruction-surface-source="segmentation-derived"' in INDEX, "PHASE6D2_SURFACE_SOURCES_PRESERVED")
require('value="300"' in INDEX and "Bone baseline: 300 HU when in range" in INDEX, "PHASE6D1_300HU_BASELINE_PRESERVED")
require("phase6e-a-r1" in INDEX and "phase6e-a-r1" in APP, "PHASE6E_A_BROWSER_CACHE_BOUNDARY")
require("6E-B" in DOC and "6F" in DOC, "PHASE6E_A_LATER_STEP_BOUNDARY")
require("Clinical validation is not claimed" in DOC, "CLINICAL_VALIDATION_NOT_CLAIMED")
print("PHASE6E_A_ARCHITECTURE_OK=YES")
