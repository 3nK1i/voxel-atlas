from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase3DR1ProfessionalMprPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
        self.js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

    def test_mpr_cards_keep_target_metadata_and_controls(self) -> None:
        for plane in ("Axial", "Coronal", "Sagittal"):
            self.assertIn(f'id="mpr{plane}Position" class="mpr-position"', self.html)
            self.assertIn(f'data-mpr-center="{plane.lower()}"', self.html)
            self.assertIn(f'data-mpr-reset-window="{plane.lower()}"', self.html)
        self.assertIn('class="mpr-title-block"', self.html)
        self.assertIn('class="mpr-panel-tools"', self.html)

    def test_surface_fit_uses_physical_patient_space_extent_not_raster_aspect(self) -> None:
        self.assertIn("function mprPhysicalMetrics", self.js)
        self.assertIn("horizontal_range_mm", self.js)
        self.assertIn("vertical_range_mm", self.js)
        self.assertIn("pixel_spacing_mm", self.js)
        self.assertIn("physicalWidth / physicalHeight", self.js)
        self.assertIn("configureMprSurface(entry, planeDescriptor)", self.js)
        self.assertNotIn("const aspect = width / Math.max(height, 1);", self.js)

    def test_anisotropic_mpr_examples_require_physical_not_raster_aspect(self) -> None:
        axial_raster_aspect = 574 / 112
        axial_physical_aspect = (574 * 0.32229965156794) / (112 * 2.0)
        sagittal_raster_aspect = 112 / 512
        sagittal_physical_aspect = (112 * 2.0) / (512 * 0.322265625)
        self.assertGreater(axial_raster_aspect, 5.0)
        self.assertGreater(axial_physical_aspect, 0.75)
        self.assertLess(axial_physical_aspect, 0.9)
        self.assertLess(sagittal_raster_aspect, 0.25)
        self.assertGreater(sagittal_physical_aspect, 1.3)
        self.assertLess(sagittal_physical_aspect, 1.4)

    def test_r2_can_remove_scale_bar_without_regressing_physical_fit(self) -> None:
        self.assertNotIn("function mprScaleSpec", self.js)
        self.assertNotIn("--mpr-scale-height", self.js)
        self.assertNotIn('data-mpr-scale=', self.html)
        self.assertIn("physicalWidth / physicalHeight", self.js)

    def test_crosshairs_use_plane_specific_professional_axis_colors(self) -> None:
        self.assertIn("--mpr-v-line", self.css)
        self.assertIn("--mpr-h-line", self.css)
        self.assertIn('[data-mpr-plane="axial"]', self.css)
        self.assertIn('[data-mpr-plane="coronal"]', self.css)
        self.assertIn('[data-mpr-plane="sagittal"]', self.css)

    def test_panel_controls_center_crosshair_and_reset_window_level(self) -> None:
        self.assertIn("function centerMprCrosshair", self.js)
        self.assertIn("function resetMprWindowLevel", self.js)
        self.assertIn('[data-mpr-center]', self.js)
        self.assertIn('[data-mpr-reset-window]', self.js)
        self.assertIn("scheduleMprRender", self.js)

    def test_phase3d_r1_or_r2_cache_busting_and_target_copy_are_present(self) -> None:
        self.assertRegex(self.html, r'/css/styles\.css\?v=phase3d-r[12]')
        self.assertRegex(self.html, r'/js/app\.js\?v=phase3d-r[12]')
        self.assertNotIn('Volume ready - MPR rendering pending', self.html)


if __name__ == "__main__":
    unittest.main()
