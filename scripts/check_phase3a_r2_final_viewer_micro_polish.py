from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
JS = (ROOT / "web/js/app.js").read_text(encoding="utf-8")


def require(marker: str, text: str, label: str) -> None:
    if marker not in text:
        raise SystemExit(f"FAIL {label}: missing {marker!r}")


def reject(marker: str, text: str, label: str) -> None:
    if marker in text:
        raise SystemExit(f"FAIL {label}: forbidden {marker!r}")


require('id="opacitySlider"', HTML, "opacity_slider")
require('min="0"', HTML, "opacity_min_zero")
require('<div class="range-labels"><span>0%</span><span>100%</span></div>', HTML, "opacity_labels")
require("state.opacity = Number(opacitySlider.value) / 100;", JS, "opacity_mapping")
reject("1 - state.opacity", JS, "opacity_not_inverted")
require("volumeRayMarcher.setOpacity(state.opacity);", JS, "volume_opacity_application")
require("volumeLayer.available && state.opacity > 0.001", JS, "opacity_zero_hidden")
require("clip-path: circle(49% at 50% 50%);", CSS, "logo_clip")
require("background: transparent;", CSS, "gizmo_transparent")
for marker in (
    'id="gizmoArrowS"',
    'id="gizmoArrowA"',
    'id="gizmoArrowR"',
    'id="gizmoArrowL"',
    'marker-end="url(#gizmoArrowS)"',
    'marker-end="url(#gizmoArrowA)"',
    'marker-end="url(#gizmoArrowR)"',
    'marker-end="url(#gizmoArrowL)"',
):
    require(marker, HTML, "gizmo_arrowheads")
if not any(marker in CSS for marker in (
    "bottom: 10px; width: 98px; height: 98px;",
    "bottom: -4px; width: 98px; height: 98px;",
)):
    raise SystemExit("FAIL gizmo_desktop_alignment: missing supported R2 alignment")
if not any(marker in HTML for marker in ('/css/styles.css?v=phase3a-r2', '/css/styles.css?v=phase3a-r2-final1', '/css/styles.css?v=phase3b-geometry1', '/css/styles.css?v=phase3c-volume1', '/css/styles.css?v=phase3d-mpr1', '/css/styles.css?v=phase3d-r1', '/css/styles.css?v=phase3d-r2', '/css/styles.css?v=phase3d-r21-phase4h6')):
    raise SystemExit('FAIL css_cache_version: missing supported R2 cache version')
if not any(marker in HTML for marker in ('/js/app.js?v=phase3a-r2', '/js/app.js?v=phase3a-r2-final1', '/js/app.js?v=phase3b-geometry1', '/js/app.js?v=phase3c-volume1', '/js/app.js?v=phase3d-mpr1', '/js/app.js?v=phase3d-r1', '/js/app.js?v=phase3d-r2', '/js/app.js?v=phase3d-r21-phase4d1', '/js/app.js?v=phase3d-r21-phase4h6')):
    raise SystemExit('FAIL js_cache_version: missing supported R2 cache version')

print("PASS opacity=direct_zero_to_one_hundred")
print("PASS transparency=volume_absorption_zero_hidden")
print("PASS logo=authoritative_asset_clipped_to_blend")
print("PASS gizmo=transparent_lower_arrowed")
print("PHASE3A_R2_FINAL_VIEWER_MICRO_POLISH_OK=YES")
