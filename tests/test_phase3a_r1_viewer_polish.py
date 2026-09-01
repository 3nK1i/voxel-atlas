from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Phase3AR1ViewerPolishTests(unittest.TestCase):
    def test_opacity_semantics_are_direct_and_default_to_fully_opaque(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_OPACITY = 1.0;", js)
        self.assertIn('id="opacityValue" class="control-value">100%</strong>', html)
        self.assertRegex(
            html,
            r'id="opacitySlider"[\s\S]*?value="100"',
        )
        self.assertIn("state.opacity = Number(opacitySlider.value) / 100;", js)
        self.assertTrue(
            "mesh.material.opacity = state.opacity;" in js
            or "mesh.material.opacity = visualOpacity;" in js
        )
        self.assertNotIn("1 - state.opacity", js)
        self.assertNotIn("100 - Number(opacitySlider.value)", js)

    def test_default_clinical_material_is_truly_opaque_and_robust_to_mesh_winding(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        self.assertIn("transparent: false", js)
        self.assertIn("opacity: 1.0", js)
        self.assertIn("depthWrite: true", js)
        self.assertIn("depthTest: true", js)
        self.assertIn("side: THREE.DoubleSide", js)
        self.assertIn("forceSinglePass: true", js)
        self.assertIn("dithering: true", js)
        self.assertIn("const nextTransparent = state.opacity < 0.999;", js)
        self.assertIn("mesh.material.transparent = nextTransparent;", js)

    def test_initial_camera_framing_is_about_fifteen_percent_smaller(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        self.assertIn("const INITIAL_VIEW_DISTANCE_SCALE = 1.18;", js)
        self.assertIn("offset.multiplyScalar(INITIAL_VIEW_DISTANCE_SCALE);", js)
        self.assertIn("fitCamera(box)", js)

    def test_orientation_gizmo_matches_anatomical_target_and_tracks_view(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        for marker in (
            'id="orientationGizmo"',
            'id="gizmoEdges"',
            'id="gizmoAxisS"',
            'id="gizmoAxisA"',
            'id="gizmoAxisR"',
            'id="gizmoAxisL"',
            '>S</text>',
            '>A</text>',
            '>R</text>',
            '>L</text>',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

        self.assertIn("function updateOrientationGizmo()", js)
        self.assertIn("camera.quaternion", js)
        self.assertIn("anatomyGroup.quaternion", js)
        self.assertIn("updateOrientationGizmo();", js)
        self.assertIn(".orientation-cube svg", css)
        self.assertIn(".gizmo-axis-r", css)
        self.assertIn(".gizmo-axis-l", css)

    def test_polish_keeps_phase3a_runtime_cache_version_explicit(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'/css/styles\.css\?v=phase3a-r(?:1|2(?:-final1)?)')
        self.assertRegex(html, r'/js/app\.js\?v=phase3a-r(?:1|2(?:-final1)?)')


if __name__ == "__main__":
    unittest.main()
