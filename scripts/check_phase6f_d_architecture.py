#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


html = (ROOT / "web/index.html").read_text(encoding="utf-8")
app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
panel = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
interaction = (ROOT / "web/js/segmentation-structure-interaction.js").read_text(encoding="utf-8")
seg_viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
volume_viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")
helper = (ROOT / "web/js/reconstruction-surface-clipping.js").read_text(encoding="utf-8")

require('id="segmentationStructureClipParticipation"' in html, "6F-D selected structure clipping control missing")
require("Follow Directional Cut" in html, "6F-D clipping control label missing")
require("structure.clippingEnabled = this.clippingParticipation.checked" in panel, "6F-D panel does not update existing clipping state")
require("clippingEnabled: true" in interaction, "6F-D lost default clipping participation")
require("clippingEnabled: structure.clippingEnabled !== false" in interaction, "6F-D interaction resolver lost clipping state")
require("resolvePatientSurfaceClippingDescriptors" in helper, "6F-D clipping descriptor helper missing")
require("applySurfaceClippingToMaterial" in helper, "6F-D material clipping helper missing")
require("enableSurfaceLocalClipping" in helper, "6F-D local clipping activation missing")
require("enableSurfaceLocalClipping(renderer);" in app, "6F-D renderer local clipping not enabled")
require("const request = clippingRequest();" in app, "6F-D does not reuse canonical clipping request")
require("volumeSurfaceLayer?.setClippingPlanes(request);" in app, "6F-D Direct CT surface clipping not wired")
require("segmentationSurfaceLayer?.setClippingPlanes(request);" in app, "6F-D segmentation clipping not wired")
require("volumeRayMarcher.setClippingPlanes(request)" in app, "6F-D volume clipping no longer shares request")
require("interaction.clippingEnabled" in seg_viewer, "6F-D per-structure participation not applied to segmentation material")
require("applySurfaceClippingToMaterial" in seg_viewer, "6F-D segmentation material clipping missing")
require("applySurfaceClippingToMaterial" in volume_viewer, "6F-D Direct CT material clipping missing")
require("segmentationStructureExplode" not in html + app + panel, "6F-E exploded view enabled prematurely")

for text, name in ((helper, "helper"),):
    for forbidden in ("fetch(", "marching_cubes", 'setAttribute("position"', "setIndex(", "geometry.apply"):
        require(forbidden not in text, f"6F-D {name} unexpectedly touches geometry or I/O: {forbidden}")

print("PHASE6F_D_ARCHITECTURE_OK=YES")
print("DIRECTIONAL_CUT_SYSTEM=REUSED")
print("PER_STRUCTURE_CLIPPING_STATE=EXISTING_STATE_ACTIVATED")
print("PATIENT_LPS_SURFACE_CLIPPING=DISPLAY_ONLY")
print("DIRECT_CT_SURFACE_FOLLOWS_DIRECTIONAL_CUT=YES")
print("PHASE6F_E_EXPLODED_PRESENTATION=NOT_ENABLED")
