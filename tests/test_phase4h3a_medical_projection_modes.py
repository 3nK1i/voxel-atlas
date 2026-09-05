from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4H3AMedicalProjectionModesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.renderer = (
            ROOT / "web/js/patient-volume-ray-marcher.js"
        ).read_text(encoding="utf-8")

    def test_primary_panel_exposes_four_truthful_rendering_modes(self) -> None:
        self.assertIn('id="renderingModeSelect"', self.html)
        self.assertIn('id="renderingModeNote"', self.html)
        for value, label in (
            ("dvr", "Volume / DVR"),
            ("mip", "MIP"),
            ("minip", "MinIP"),
            ("average", "Average Intensity"),
        ):
            with self.subTest(value=value):
                self.assertIn(f'<option value="{value}"', self.html)
                self.assertIn(label, self.html)

        self.assertNotIn("segmentation", self.html.lower())
        self.assertNotIn("surface extraction", self.html.lower())

    def test_renderer_defines_scalar_projection_before_window_mapping(self) -> None:
        for marker in (
            "MEDICAL_RENDERING_MODES",
            "listMedicalRenderingModes",
            "aggregateMedicalProjection",
            "uRenderingMode",
            "RENDER_MODE_DVR",
            "RENDER_MODE_MIP",
            "RENDER_MODE_MINIP",
            "RENDER_MODE_AVERAGE",
            "projectionSampleCount",
            "projectedIntensity",
            "windowMedicalIntensity(projectedIntensity)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.renderer)

        projection_loop = self.renderer.index("projectionSampleCount")
        projection_window = self.renderer.index(
            "windowMedicalIntensity(projectedIntensity)", projection_loop
        )
        self.assertGreater(projection_window, projection_loop)
        projection_branch = self.renderer.index(
            "if (uRenderingMode != RENDER_MODE_DVR)", projection_loop
        )
        projection_cutoff = self.renderer.index(
            "intensity < uIntensityBounds.x", projection_branch
        )
        projection_aggregate = self.renderer.index(
            "projectedIntensity = intensity", projection_branch
        )
        self.assertLess(projection_cutoff, projection_aggregate)

    def test_mode_switch_updates_uniform_without_reloading_patient_volume(self) -> None:
        self.assertIn("setRenderingMode(modeId)", self.renderer)
        self.assertIn("uniforms.uRenderingMode.value", self.renderer)
        self.assertIn("renderingModeState", self.renderer)

        start = self.app.index('renderingModeSelect.addEventListener("change"')
        end = self.app.index("opacitySlider.addEventListener", start)
        handler = self.app[start:end]
        self.assertIn("setMedicalRenderingMode", handler)
        self.assertNotIn("fetch(", handler)
        self.assertNotIn("volumeTextureManager.load", handler)
        self.assertNotIn("volumeRayMarcher.create", handler)

    def test_projection_modes_preserve_volume_controls_with_clear_applicability(self) -> None:
        self.assertIn("setDvrOnlyControlsEnabled", self.app)
        self.assertIn("renderingModeSelect", self.app)
        self.assertIn("dvrOnlyControls", self.app)
        self.assertIn("Projection modes aggregate real patient voxels", self.app)
        self.assertIn("DVR compositing", self.app)

    def test_canonical_volume_and_patient_space_contracts_remain_unchanged(self) -> None:
        self.assertIn("clipPatientRayInterval", self.renderer)
        self.assertIn("decodeMedicalIntensity", self.renderer)
        self.assertIn("uLocalToPatientLps", self.renderer)
        self.assertNotIn("textureResource.texture.image.data", self.app)
        self.assertNotIn("marchingCubes", self.renderer)
        self.assertNotIn("isocontour", self.renderer.lower())

    def test_h3a_cache_and_compact_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r21-phase4h6', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h6', self.html)
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4h6"',
            self.app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4h3a_checks.sh").is_file())
        self.assertTrue((ROOT / "scripts/check_phase4h3a_projection_modes.mjs").is_file())


if __name__ == "__main__":
    unittest.main()
