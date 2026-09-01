#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

checks = {
    "shared_active_effect": '.viewer-tool-button[aria-pressed="true"],\n.direction-button.is-active,\n.layer-button.is-active {' in css,
    "active_gradient": "linear-gradient(" in css and "inset 0 0 0 1px" in css and "0 0 15px" in css,
    "skull_pressed": 'class="layer-button is-active" data-layer="skull" aria-pressed="true"' in html,
    "disabled_layers": all(token in html for token in (
        'data-layer="volume" disabled aria-pressed="false"',
        'data-layer="brain" disabled aria-pressed="false"',
        'data-layer="combined" disabled aria-pressed="false"',
    )),
    "aria_sync": 'button.setAttribute("aria-pressed", isActive ? "true" : "false")' in js,
    "cache": "phase3d-r2" in html,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    print("PHASE3D_R2_FINAL_SELECTION=FAIL")
    print("FAILED=" + ",".join(failed))
    raise SystemExit(1)
print("PHASE3D_R2_FINAL_SELECTION=PASS")
