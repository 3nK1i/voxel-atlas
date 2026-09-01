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
require("function clinicalVisualOpacity(opacity)", JS, "clinical_alpha_curve")
require("Math.pow(clamped, 0.55)", JS, "clinical_alpha_gamma")
require("const visualOpacity = clinicalVisualOpacity(state.opacity);", JS, "clinical_alpha_apply")
require("mesh.material.opacity = visualOpacity;", JS, "clinical_alpha_material")
require_any(('/css/styles.css?v=phase3a-r2-final1', '/css/styles.css?v=phase3b-geometry1'), HTML, "css_cache_version")
require_any(('/js/app.js?v=phase3a-r2-final1', '/js/app.js?v=phase3b-geometry1'), HTML, "js_cache_version")

print("PASS logo=qualified_asset_seamless_blend")
print("PASS gizmo=final_lower_alignment")
print("PASS transparency=perceptual_clinical_curve")
print("PHASE3A_R2_FINAL_CORRECTION_OK=YES")
