from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Phase3AR2FinalCorrectionTests(unittest.TestCase):
    def test_logo_uses_seamless_blending_without_replacing_qualified_asset(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

        self.assertIn('src="/assets/logo.png"', html)
        self.assertIn('[data-theme="dark"] .brand-logo', css)
        self.assertRegex(css, r'\[data-theme="dark"\] \.brand-logo\s*\{[\s\S]*?mix-blend-mode:\s*lighten;')

    def test_desktop_gizmo_is_lowered_to_align_visible_geometry_with_hint(self) -> None:
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

        self.assertRegex(
            css,
            r"@media \(min-width: 981px\)[\s\S]*?\.orientation-cube\s*\{[^}]*bottom:\s*-4px;[^}]*width:\s*98px;[^}]*height:\s*98px;",
        )
        self.assertRegex(css, r"\.orientation-cube\s*\{[\s\S]*?background:\s*transparent;")

    def test_intermediate_opacity_uses_perceptual_clinical_alpha_curve(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        self.assertIn("function clinicalVisualOpacity(opacity)", js)
        self.assertIn("Math.pow(clamped, 0.55)", js)
        self.assertIn("const visualOpacity = clinicalVisualOpacity(state.opacity);", js)
        self.assertIn("mesh.material.opacity = visualOpacity;", js)
        self.assertIn("mesh.visible = state.opacity > 0.001;", js)
        self.assertNotIn("mesh.material.opacity = state.opacity;", js)

    def test_final_correction_has_fresh_cache_version(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'/css/styles\.css\?v=(?:phase3a-r2-final1|phase3b-geometry1|phase3c-volume1|phase3d-mpr1|phase3d-r1|phase3d-r2)')
        self.assertRegex(html, r'/js/app\.js\?v=(?:phase3a-r2-final1|phase3b-geometry1|phase3c-volume1|phase3d-mpr1|phase3d-r1|phase3d-r2)')


if __name__ == "__main__":
    unittest.main()
