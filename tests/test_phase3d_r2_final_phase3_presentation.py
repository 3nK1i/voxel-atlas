from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase3DR2FinalPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
        self.js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

    def test_mpr_removes_scale_bar_without_removing_clinical_metadata(self) -> None:
        self.assertNotIn('mpr-scale-bar', self.html)
        self.assertNotIn('mpr-scale-bracket', self.html)
        self.assertNotIn('>5 cm<', self.html)
        self.assertNotIn('function mprScaleSpec', self.js)
        self.assertNotIn('--mpr-scale-height', self.js)
        for plane in ("Axial", "Coronal", "Sagittal"):
            self.assertIn(f'id="mpr{plane}Position" class="mpr-position"', self.html)
            self.assertIn(f'id="mpr{plane}Index" class="mpr-index"', self.html)

    def test_black_mpr_surface_fills_panel_and_canvas_is_contained_without_crop(self) -> None:
        self.assertIn('inset: 0;', self.css)
        self.assertIn('--mpr-image-width', self.css)
        self.assertIn('--mpr-image-height', self.css)
        self.assertIn('--mpr-image-left', self.css)
        self.assertIn('--mpr-image-top', self.css)
        self.assertIn('function configureMprSurface(entry, planeDescriptor)', self.js)
        self.assertIn('const availableWidth = Math.max(frame.width, 1);', self.js)
        self.assertIn('const availableHeight = Math.max(frame.height, 1);', self.js)
        self.assertIn('"--mpr-image-width"', self.js)
        self.assertIn('"--mpr-image-height"', self.js)
        self.assertIn('"--mpr-image-left"', self.js)
        self.assertIn('"--mpr-image-top"', self.js)
        self.assertIn('const rect = entry.canvas.getBoundingClientRect();', self.js)
        self.assertNotIn('object-fit: cover', self.css)

    def test_viewer_toolbar_matches_six_tool_reference_and_uses_real_svg_icons(self) -> None:
        for identifier in (
            'rotateToolButton',
            'panToolButton',
            'fitViewButton',
            'zoomOutButton',
            'zoomInButton',
            'fullscreenButton',
        ):
            self.assertIn(f'id="{identifier}"', self.html)
        self.assertEqual(self.html.count('class="viewer-tool-button'), 6)
        self.assertGreaterEqual(self.html.count('<svg viewBox="0 0 24 24"'), 6)
        self.assertIn('data-viewer-tool="rotate"', self.html)
        self.assertIn('data-viewer-tool="pan"', self.html)

    def test_viewer_toolbar_modes_are_functional_and_accessible(self) -> None:
        self.assertIn('function setViewerInteractionMode(mode)', self.js)
        self.assertIn('controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE', self.js)
        self.assertIn('controls.mouseButtons.LEFT = THREE.MOUSE.PAN', self.js)
        self.assertIn('aria-pressed', self.html)
        self.assertIn('rotateToolButton.addEventListener', self.js)
        self.assertIn('panToolButton.addEventListener', self.js)
        self.assertIn('setViewerInteractionMode("rotate")', self.js)
        self.assertIn('id="primaryInteractionHint"', self.html)
        self.assertIn('Left drag - Pan', self.js)

    def test_target_style_selected_button_effect_is_shared_by_toolbar_and_directional_cut(self) -> None:
        self.assertIn('.viewer-tool-button.is-active', self.css)
        self.assertIn('.direction-button.is-active', self.css)
        self.assertIn('linear-gradient(', self.css)
        self.assertIn('box-shadow:', self.css)
        self.assertIn('border-color:', self.css)

    def test_r2_cache_busting_is_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r2', self.html)
        self.assertIn('/js/app.js?v=phase3d-r2', self.html)


if __name__ == "__main__":
    unittest.main()
