#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

checks = {
    "scale_removed": "mpr-scale-bar" not in html and "mpr-scale-bracket" not in html and "function mprScaleSpec" not in js,
    "physical_contain": all(token in js for token in (
        "physicalWidth / physicalHeight",
        '"--mpr-image-width"',
        '"--mpr-image-height"',
        '"--mpr-image-left"',
        '"--mpr-image-top"',
        "entry.canvas.getBoundingClientRect()",
    )),
    "black_full_surface": "position: absolute;\n  inset: 0;" in css and "width: 100% !important;" in css and "height: 100% !important;" in css,
    "toolbar_six": html.count('class="viewer-tool-button') == 6,
    "toolbar_modes": 'data-viewer-tool="rotate"' in html and 'data-viewer-tool="pan"' in html and "function setViewerInteractionMode(mode)" in js,
    "svg_icons": html.count('<svg viewBox="0 0 24 24"') >= 6,
    "active_effect": ".viewer-tool-button.is-active" in css and ".direction-button.is-active" in css and "linear-gradient(" in css,
    "cache": "phase3d-r2" in html,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    print("PHASE3D_R2_FINAL_PRESENTATION=FAIL")
    print("FAILED=" + ",".join(failed))
    raise SystemExit(1)
print("PHASE3D_R2_FINAL_PRESENTATION=PASS")
