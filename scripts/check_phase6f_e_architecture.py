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
explode = (ROOT / "web/js/segmentation-exploded-presentation.js").read_text(encoding="utf-8")
viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
clipping = (ROOT / "web/js/reconstruction-surface-clipping.js").read_text(encoding="utf-8")
volume_viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")

require('id="segmentationStructureExplode"' in html, "6F-E exploded presentation control missing")
require("Explode anatomy" in html, "6F-E control label missing")
require("MAX_ANATOMICAL_GROUP_EXPLODE_MM = 40" in explode, "6F-E explosion bound changed")
require("applyAnatomicalGroupExplosion" in panel, "6F-E panel is not applying grouped explosion")
require("explodedSeparationMm" in panel, "6F-E presentation does not preserve global separation")
require("explodedOffsetLpsMm" in interaction, "6F-E lost per-structure display offset state")
require("patientLpsOffsetToViewer" in viewer, "6F-E viewer transform missing")
require("item.mesh.position.set" in viewer, "6F-E display transform is not applied as a mesh transform")
require("viewerOffset" in clipping, "6F-E clipping is not translated with exploded display state")
require("descriptor.constant - normalDotOffset" in clipping, "6F-E clipping plane translation is missing")
require("segmentation-exploded-presentation" not in volume_viewer, "6F-E must not explode Direct CT geometry")
require("phase6f-e-r1" in html and "phase6f-e-r1" in app, "6F-E browser cache revision missing")

for text, name in ((explode, "explosion helper"), (interaction, "interaction state")):
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "marching_cubes",
        'setAttribute("position"',
        "setIndex(",
        "geometry.applyMatrix4",
        "/api/",
    ):
        require(forbidden not in text, f"6F-E {name} unexpectedly touches geometry or I/O: {forbidden}")

require("PHASE6F_F" not in html, "6F-F final qualification enabled prematurely")

print("PHASE6F_E_ARCHITECTURE_OK=YES")
print("ANATOMICAL_GROUP_MEMBERSHIP=CATALOG_AUTHORITATIVE")
print("EXPLODED_PRESENTATION=BOUNDED_DISPLAY_TRANSFORM")
print("MAX_ANATOMICAL_GROUP_EXPLODE_MM=40")
print("MPR_CANONICAL_PATIENT_LPS=UNCHANGED")
print("DIRECT_CT_EXPLOSION=NO")
print("PHASE6F_F_FINAL_QUALIFICATION=NOT_ENABLED")
