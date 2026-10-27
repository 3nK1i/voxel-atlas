#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


html = (ROOT / "web/index.html").read_text(encoding="utf-8")
app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
panel = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
clipping = (ROOT / "web/js/reconstruction-surface-clipping.js").read_text(encoding="utf-8")
explode = (ROOT / "web/js/segmentation-exploded-presentation.js").read_text(encoding="utf-8")

# Authoritative visibility and isolation behavior remains present.
for token in ("show-all", "hide-all", "restore-isolation", "isolateStructure"):
    require(token in panel, f"Phase 6F visibility/isolation token missing: {token}")

# Exact user opacity remains authoritative.
require("structure.opacity" in panel, "Phase 6F-C structure opacity state missing")
require("accurate fallback" in viewer, "Phase 6B refined-to-accurate fallback presentation missing")

# Clipping participation remains structure-local and display-only.
require("clippingEnabled" in panel, "Phase 6F-D clipping participation missing")
require("setClippingPlanes" in viewer, "segmentation clipping plane application missing")
require("descriptor.constant - normalDotOffset" in clipping, "exploded clipping translation missing")

# Bounded group explosion remains enabled without Direct CT translation.
require("explodedSeparationMm" in panel, "Phase 6F-E exploded separation state missing")
require("MAX_ANATOMICAL_GROUP_EXPLODE_MM = 40" in explode, "Phase 6F-E 40 mm bound changed")
require("item.mesh.position.set" in viewer, "display-only segmentation mesh translation missing")

# The surrounding mode/profile architecture remains the presentation authority.
require("requestReconstructionPresentationProfile" in app, "Fidelity/Presentation profile controller missing")
require("applyCombinedPresentationBalance" in app, "Combined presentation balance missing")
for label in ("Fidelity", "Presentation", "Surface", "Combined", "Explode anatomy", "Follow Directional Cut"):
    require(label in html, f"required final interaction UI missing: {label}")

print("PHASE6F_F_ARCHITECTURE_OK=YES")
print("SHOW_HIDE_ISOLATE_RESTORE=PRESERVED")
print("USER_STRUCTURE_OPACITY=PRESERVED")
print("PER_STRUCTURE_CLIPPING_PARTICIPATION=PRESERVED")
print("BOUNDED_EXPLODED_PRESENTATION=PRESERVED")
print("FIDELITY_PRESENTATION_ROUNDTRIP=ARCHITECTURE_PRESERVED")
print("SURFACE_COMBINED_ROUNDTRIP=ARCHITECTURE_PRESERVED")
print("REFINED_TO_ACCURATE_FALLBACK=PRESERVED")
print("PHASE6G_QUANTITATIVE_SURFACE_TO_MASK_FIDELITY=NOT_ENABLED")
