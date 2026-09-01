#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

checks = {
    "physical_aspect": "function mprPhysicalMetrics" in js and "physicalWidth / physicalHeight" in js,
    "spacing_contract": "pixel_spacing_mm" in js and "horizontal_range_mm" in js and "vertical_range_mm" in js,
    "target_metadata": html.count('class="mpr-title-block"') == 3 and html.count('class="mpr-position"') == 3,
    "controls": html.count("data-mpr-center=") == 3 and html.count("data-mpr-reset-window=") == 3,
    "axis_colors": "--mpr-v-line" in css and "--mpr-h-line" in css,
    "scale_retired_by_r2": "data-mpr-scale=" not in html and "function mprScaleSpec" not in js,
    "cache": "phase3d-r1" in html or "phase3d-r2" in html,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    print("PHASE3D_R1_MPR_PRESENTATION=FAIL")
    print("FAILED=" + ",".join(failed))
    raise SystemExit(1)
print("PHASE3D_R1_MPR_PRESENTATION=PASS")
