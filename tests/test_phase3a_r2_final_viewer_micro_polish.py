from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Phase3AR2FinalViewerMicroPolishTests(unittest.TestCase):
    def test_opacity_range_reaches_zero_with_direct_semantics(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        slider = re.search(r'id="opacitySlider"[\s\S]*?>', html)
        self.assertIsNotNone(slider)
        self.assertIn('min="0"', slider.group(0))
        self.assertIn('max="100"', slider.group(0))
        self.assertIn('value="100"', slider.group(0))
        self.assertIn('<div class="range-labels"><span>0%</span><span>100%</span></div>', html)
        self.assertIn("state.opacity = Number(opacitySlider.value) / 100;", js)
        self.assertNotIn("1 - state.opacity", js)

    def test_transparent_mode_uses_clean_front_surface_and_zero_hides_layer(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        self.assertIn("const nextTransparent = state.opacity < 0.999;", js)
        self.assertIn("mesh.visible = state.opacity > 0.001;", js)
        self.assertIn("mesh.material.side = nextTransparent ? THREE.FrontSide : THREE.DoubleSide;", js)
        self.assertIn("mesh.material.depthWrite = true;", js)
        self.assertIn("mesh.material.depthTest = true;", js)

    def test_logo_blends_without_modifying_authoritative_asset(self) -> None:
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

        self.assertRegex(css, r"\.brand-logo\s*\{[\s\S]*?clip-path:\s*circle\(")
        self.assertRegex(css, r"\.brand-logo\s*\{[\s\S]*?border-radius:\s*50%")

    def test_gizmo_is_transparent_lower_aligned_and_has_axis_arrowheads(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

        self.assertIn('id="gizmoArrowS"', html)
        self.assertIn('id="gizmoArrowA"', html)
        self.assertIn('id="gizmoArrowR"', html)
        self.assertIn('id="gizmoArrowL"', html)
        self.assertIn('marker-end="url(#gizmoArrowS)"', html)
        self.assertIn('marker-end="url(#gizmoArrowA)"', html)
        self.assertIn('marker-end="url(#gizmoArrowR)"', html)
        self.assertIn('marker-end="url(#gizmoArrowL)"', html)
        self.assertRegex(css, r"\.orientation-cube\s*\{[\s\S]*?background:\s*transparent;")
        self.assertRegex(css, r"@media \(min-width: 981px\)[\s\S]*?\.orientation-cube\s*\{[^}]*bottom:\s*(?:10px|-4px);")
        self.assertRegex(css, r"@media \(min-width: 981px\)[\s\S]*?\.orientation-cube\s*\{[^}]*width:\s*98px;[^}]*height:\s*98px;")

    def test_r2_cache_version_is_explicit(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'/css/styles\.css\?v=(?:phase3a-r2(?:-final1)?|phase3b-geometry1)')
        self.assertRegex(html, r'/js/app\.js\?v=(?:phase3a-r2(?:-final1)?|phase3b-geometry1)')


if __name__ == "__main__":
    unittest.main()
