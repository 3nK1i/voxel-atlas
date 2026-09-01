from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase3DR21CrosshairAndCtaPolishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
        self.js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

    def test_crosshair_uses_pixel_registered_display_rect(self) -> None:
        self.assertIn("entry.imageRect = {", self.js)
        self.assertIn("const imageRect = entry.imageRect;", self.js)
        self.assertIn('"--mpr-crosshair-x-px"', self.js)
        self.assertIn('"--mpr-crosshair-y-px"', self.js)
        self.assertNotIn('"--mpr-crosshair-x", `${clamp(hFraction, 0, 1) * 100}%`', self.js)
        self.assertNotIn('"--mpr-crosshair-y", `${clamp(vFraction, 0, 1) * 100}%`', self.js)

    def test_crosshair_lines_are_clipped_to_actual_image_rectangle(self) -> None:
        self.assertIn("left: var(--mpr-crosshair-x-px);", self.css)
        self.assertIn("top: var(--mpr-image-top);", self.css)
        self.assertIn("height: var(--mpr-image-height);", self.css)
        self.assertIn("top: var(--mpr-crosshair-y-px);", self.css)
        self.assertIn("left: var(--mpr-image-left);", self.css)
        self.assertIn("width: var(--mpr-image-width);", self.css)

    def test_pointer_mapping_still_uses_displayed_canvas_rectangle(self) -> None:
        self.assertIn("const rect = entry.canvas.getBoundingClientRect();", self.js)
        self.assertIn("(event.clientX - rect.left) / rect.width", self.js)
        self.assertIn("(event.clientY - rect.top) / rect.height", self.js)

    def test_upload_cta_uses_same_premium_blue_language(self) -> None:
        self.assertIn(".upload-button:not(:disabled) {", self.css)
        self.assertIn("color-mix(in srgb, #0757a6 82%, var(--accent) 18%)", self.css)
        self.assertIn("inset 0 0 0 1px", self.css)
        self.assertIn("0 0 15px", self.css)
        self.assertIn(".upload-button:not(:disabled):hover", self.css)
        self.assertIn(".upload-button:not(:disabled):active", self.css)

    def test_r21_cache_busting_is_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r21', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21', self.html)


if __name__ == "__main__":
    unittest.main()
