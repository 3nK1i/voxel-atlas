from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MprClippingVisualizationTests(unittest.TestCase):
    def test_behavior_probe(self):
        result = subprocess.run(
            ["node", "scripts/check_phase4h5_mpr_clipping.mjs"],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_readable_clipping_typography(self):
        css = (ROOT / "web/css/styles.css").read_text()
        for selector in (".clip-range-summary", ".clip-boundary-labels", ".clip-boundary-values strong", ".clip-plane-heading strong"):
            rules = re.findall(re.escape(selector) + r"\s*\{([^}]+)\}", css)
            sizes = [float(n) for rule in rules for n in re.findall(r"font-size:\s*([\d.]+)px", rule)]
            # H6: user-requested 1 px reduction; maintain a readable floor.
            self.assertTrue(sizes and sizes[-1] >= 11, selector)

    def test_overlay_integration_and_reference_pixels_preserved(self):
        app = (ROOT / "web/js/app.js").read_text()
        html = (ROOT / "web/index.html").read_text()
        css = (ROOT / "web/css/styles.css").read_text()
        self.assertIn('id="mprClippingOverlayToggle"', html)
        self.assertIn("Dashed lines: clipping bounds", html)
        self.assertIn('mpr-clipping-overlay.js?v=phase4h6', app)
        self.assertIn('phase3d-r21-phase4h6', html)
        self.assertIn("resizeObserver.observe(entry.view)", app)
        for name, next_name in (("applyPatientClipping", "syncClippingControlsFromMpr"), ("updateMprClippingOverlays", "drawGray8")):
            body = app.split(f"function {name}(")[1].split(f"function {next_name}(")[0]
            self.assertIn("ClippingOverlay", body)
            self.assertNotIn("fetch(", body)
            self.assertNotIn("scheduleMprRender(", body)
            self.assertNotIn("putImageData", body)
            self.assertNotRegex(body, r"crosshairLpsMm.*=")
        self.assertIn("renderedPositionLpsMm = position", app)
        self.assertIn(".mpr-clipping-overlay", css)
        self.assertIn("pointer-events: none", css)


if __name__ == "__main__":
    unittest.main()
