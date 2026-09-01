#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
css = (ROOT / 'web' / 'css' / 'styles.css').read_text(encoding='utf-8')
js = (ROOT / 'web' / 'js' / 'app.js').read_text(encoding='utf-8')

checks = {
    'image_rect_state': 'entry.imageRect = {' in js and 'const imageRect = entry.imageRect;' in js,
    'pixel_crosshair_vars': '"--mpr-crosshair-x-px"' in js and '"--mpr-crosshair-y-px"' in js,
    'crosshair_vertical_clip': 'left: var(--mpr-crosshair-x-px);' in css and 'height: var(--mpr-image-height);' in css,
    'crosshair_horizontal_clip': 'top: var(--mpr-crosshair-y-px);' in css and 'width: var(--mpr-image-width);' in css,
    'pointer_canvas_rect': 'const rect = entry.canvas.getBoundingClientRect();' in js,
    'letterbox_guard': 'event.clientX < rect.left' in js and 'event.clientY < rect.top' in js,
    'dicom_cta': '.upload-button:not(:disabled) {' in css and '0 0 15px' in css,
    'dicom_cta_hover': '.upload-button:not(:disabled):hover' in css,
    'dicom_cta_press': '.upload-button:not(:disabled):active' in css,
    'cache': 'phase3d-r21' in html,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    print('PHASE3D_R21_CROSSHAIR_CTA=FAIL')
    print('FAILED=' + ','.join(failed))
    raise SystemExit(1)
print('PHASE3D_R21_CROSSHAIR_CTA=PASS')
