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


require("const DEFAULT_OPACITY = 1.0;", JS, "opacity_default")
require("state.opacity = Number(opacitySlider.value) / 100;", JS, "opacity_mapping")
if not any(marker in JS for marker in ("mesh.material.opacity = state.opacity;", "mesh.material.opacity = visualOpacity;")):
    raise SystemExit("FAIL opacity_material: missing supported direct/perceptual opacity application")
reject("1 - state.opacity", JS, "opacity_not_inverted")
require("transparent: false", JS, "opaque_default_material")
require("side: THREE.DoubleSide", JS, "winding_robust_material")
require("forceSinglePass: true", JS, "transparent_single_pass")
require("const INITIAL_VIEW_DISTANCE_SCALE = 1.18;", JS, "initial_framing")
require("offset.multiplyScalar(INITIAL_VIEW_DISTANCE_SCALE);", JS, "initial_framing_apply")
require('id="orientationGizmo"', HTML, "orientation_gizmo")
require("function updateOrientationGizmo()", JS, "orientation_gizmo_runtime")
require("anatomyGroup.quaternion", JS, "orientation_gizmo_anatomy_sync")
require("camera.quaternion", JS, "orientation_gizmo_camera_sync")
require(".orientation-cube svg", CSS, "orientation_gizmo_style")
if not any(marker in HTML for marker in ('/css/styles.css?v=phase3a-r1', '/css/styles.css?v=phase3a-r2', '/css/styles.css?v=phase3a-r2-final1', '/css/styles.css?v=phase3b-geometry1')):
    raise SystemExit("FAIL css_cache_version: missing supported Phase 3A viewer cache version")
if not any(marker in HTML for marker in ('/js/app.js?v=phase3a-r1', '/js/app.js?v=phase3a-r2', '/js/app.js?v=phase3a-r2-final1', '/js/app.js?v=phase3b-geometry1')):
    raise SystemExit("FAIL js_cache_version: missing supported Phase 3A viewer cache version")

print("PASS opacity=direct_100_percent_opaque")
print("PASS material=solid_clinical_double_side")
print("PASS initial_view=about_15_percent_smaller")
print("PASS orientation_gizmo=camera_and_anatomy_synced")
print("PHASE3A_R1_VIEWER_POLISH_OK=YES")
