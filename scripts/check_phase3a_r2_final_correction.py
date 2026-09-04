from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
JS = (ROOT / "web/js/app.js").read_text(encoding="utf-8")


def require(marker: str, text: str, label: str) -> None:
    if marker not in text:
        raise SystemExit(f"FAIL {label}: missing {marker!r}")

def require_any(markers: tuple[str, ...], text: str, label: str) -> None:
    if not any(marker in text for marker in markers):
        raise SystemExit(f"FAIL {label}: missing one of {markers!r}")


require('src="/assets/logo.png"', HTML, "qualified_logo_asset")
require('[data-theme="dark"] .brand-logo', CSS, "logo_dark_theme_rule")
require("mix-blend-mode: lighten;", CSS, "logo_seamless_blend")
require("bottom: -4px; width: 98px; height: 98px;", CSS, "gizmo_final_alignment")
require("volumeRayMarcher.setOpacity(state.opacity);", JS, "volume_opacity_application")
require("volumeLayer.available && state.opacity > 0.001", JS, "volume_zero_hidden")
require_any(('/css/styles.css?v=phase3a-r2-final1', '/css/styles.css?v=phase3b-geometry1', '/css/styles.css?v=phase3c-volume1', '/css/styles.css?v=phase3d-mpr1', '/css/styles.css?v=phase3d-r1', '/css/styles.css?v=phase3d-r2', '/css/styles.css?v=phase3d-r21-phase4h2-r1'), HTML, "css_cache_version")
require_any(('/js/app.js?v=phase3a-r2-final1', '/js/app.js?v=phase3b-geometry1', '/js/app.js?v=phase3c-volume1', '/js/app.js?v=phase3d-mpr1', '/js/app.js?v=phase3d-r1', '/js/app.js?v=phase3d-r2', '/js/app.js?v=phase3d-r21-phase4d1', '/js/app.js?v=phase3d-r21-phase4h2-r1a'), HTML, "js_cache_version")

print("PASS logo=qualified_asset_seamless_blend")
print("PASS gizmo=final_lower_alignment")
print("PASS transparency=direct_volume_opacity")
print("PHASE3A_R2_FINAL_CORRECTION_OK=YES")
