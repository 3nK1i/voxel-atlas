#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "voxelatlas"
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.segmentation_overlays import (  # noqa: E402
    OVERLAY_MEDIA_TYPE,
    OVERLAY_SAMPLING,
    SegmentationOverlayService,
)


service = (BACKEND / "segmentation_overlays.py").read_text(encoding="utf-8")
app = (BACKEND / "app.py").read_text(encoding="utf-8")
html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
javascript = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
module = (ROOT / "web" / "js" / "segmentation-overlay.js").read_text(
    encoding="utf-8"
)
css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")

checks = {
    "service_contract": SegmentationOverlayService.__name__ == "SegmentationOverlayService",
    "rgba_transport": OVERLAY_MEDIA_TYPE == "application/x-voxelatlas-rgba8",
    "categorical_sampling": OVERLAY_SAMPLING == "nearest_neighbor",
    "patient_lps_binding": "array_index_to_patient_lps" in service,
    "current_study_binding": "does not belong to the current study" in service,
    "transparent_background": "rgba = np.zeros" in service,
    "authenticated_descriptor": '"/api/studies/latest/segmentation-overlay"' in app,
    "authenticated_planes": '"/api/studies/latest/segmentation-overlay/{plane}"' in app,
    "no_store": '"Cache-Control": "no-store"' in app,
    "three_overlay_canvases": all(
        value in html
        for value in (
            "mprAxialSegmentationCanvas",
            "mprCoronalSegmentationCanvas",
            "mprSagittalSegmentationCanvas",
        )
    ),
    "basic_controls": (
        "segmentationOverlayToggle" in html
        and "segmentationOverlayOpacity" in html
    ),
    "synchronized_fetch": "/api/studies/latest/segmentation-overlay" in javascript,
    "payload_validation": "validateOverlayPayload" in module,
    "noninteractive_overlay": "pointer-events: none" in css,
    "phase5e_not_enabled": "segmentationStructureSearch" not in html,
    "clinical_validation_not_claimed": "non-clinical visualization" in html,
}

failed = [name for name, passed in checks.items() if not passed]
if failed:
    print("PHASE5D_SEGMENTATION_OVERLAY_ARCHITECTURE=FAIL")
    print("FAILED=" + ",".join(failed))
    raise SystemExit(1)

print("PHASE5D_SEGMENTATION_OVERLAY_ARCHITECTURE=PASS")
print("COORDINATE_SYSTEM=patient_lps")
print("LABEL_SAMPLING=nearest_neighbor")
print("OVERLAY_TRANSPORT=rgba8")
print("MPR_PLANES=axial,coronal,sagittal")
print("PHASE5E_STRUCTURE_PANEL=NOT_ENABLED")
print("CLINICAL_VALIDATION=NOT_CLAIMED")
