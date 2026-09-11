#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
presentation = (ROOT / "web/js/reconstruction-surface-presentation.js").read_text()
panel = (ROOT / "web/js/segmentation-structure-panel.js").read_text()
viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text()
volume_viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text()
app = (ROOT / "web/js/app.js").read_text()

checks = {
    "opacity_policy_centralized": "resolveSegmentationSurfaceOpacityPolicy" in presentation,
    "near_opaque_magic_threshold_removed": "opacity >= 0.98" not in presentation,
    "exact_opaque_boundary": "const fullyOpaque = opacity >= 1;" in presentation,
    "semantic_overlay_stays_in_transparent_render_lane": "transparent: true," in presentation,
    "full_alpha_depth_write_preserved": "depthWrite: fullyOpaque," in presentation,
    "user_opacity_authoritative": "structure.opacity = clamp(Number(this.opacity.value) / 100, 0, 1);" in panel,
    "surface_viewer_uses_shared_policy": "applySegmentationSurfaceMaterialProfile" in viewer,
    "direct_ct_composition_policy_centralized": "resolveDirectCtSurfaceCompositionPolicy" in presentation,
    "surface_semantic_overlay_state": "semanticOverlayActive" in volume_viewer and "setSemanticOverlayActive(active)" in volume_viewer,
    "surface_mode_overlay_wired": "surfaceSemanticOverlayActive" in app and 'snapshot.mode === "surface"' in app,
    "no_geometry_api_added_to_policy": all(token not in presentation for token in ("fetch(", "marching_cubes", "setAttribute(\"position\"", "setIndex(")),
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{name.upper()}={'PASS' if ok else 'FAIL'}")
if failed:
    raise SystemExit(1)
print("PHASE6F_C_ARCHITECTURE_OK=YES")
