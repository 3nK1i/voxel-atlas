from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4H1ProfessionalMedicalDisplayControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.ray_marcher = (
            ROOT / "web/js/patient-volume-ray-marcher.js"
        ).read_text(encoding="utf-8")
        self.quality = (
            ROOT / "web/js/volume-rendering-quality.js"
        ).read_text(encoding="utf-8")
        self.styles = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

    def test_primary_window_and_quality_controls_are_compact_and_truthful(self) -> None:
        for marker in (
            'id="transferWindowCenter"',
            'id="transferWindowCenterLabel"',
            'id="transferWindowCenterValue"',
            'id="transferWindowWidth"',
            'id="transferWindowWidthValue"',
            'id="renderQualityPolicy"',
            '>Interactive<',
            '>Balanced<',
            '>High<',
            '>Maximum<',
            'id="advancedRenderingControls"',
            "Advanced rendering",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.html)

        self.assertIn("Window level", self.html)
        self.assertIn("Window width", self.html)
        self.assertIn("Absorption", self.html)
        self.assertIn('aria-label="Volume rendering absorption"', self.html)
        self.assertNotIn("diagnostic quality", self.html.lower())

    def test_windowing_is_separate_from_intensity_cutoffs_and_source_voxels(self) -> None:
        for marker in (
            "uWindowCenter",
            "uWindowWidth",
            "uIntensityBounds",
            "windowMedicalIntensity",
            "windowCenter",
            "windowWidth",
            "rangeLow",
            "rangeHigh",
            "setTransferPreset",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.ray_marcher)

        self.assertIn("lowByte + highByte * 256.0", self.ray_marcher)
        self.assertIn("uDecodeOffset + uDecodeScale", self.ray_marcher)
        self.assertNotIn("textureResource.texture.image.data", self.app)

    def test_ct_uses_hu_and_mr_uses_native_relative_intensity(self) -> None:
        combined = self.app + self.ray_marcher
        self.assertIn('transfer.units === "HU"', self.app)
        self.assertIn('`${Math.round(value)} HU`', self.app)
        self.assertIn('`${Number(value).toFixed(digits)} rel`', self.app)
        self.assertIn('transfer.units === "HU" ? "HU" : "relative"', self.app)
        self.assertIn('units: "HU"', self.ray_marcher)
        self.assertIn('units: "modality"', self.ray_marcher)
        self.assertNotIn("MR · HU", combined)

    def test_manual_transfer_changes_enter_custom_state_without_volume_reload(self) -> None:
        for marker in (
            'option.value = "custom"',
            'option.textContent = "Custom"',
            "markTransferCustomized",
            "transferBasePresetId",
            'transferWindowCenter.addEventListener("input"',
            'transferWindowWidth.addEventListener("input"',
            'renderQualityPolicy.addEventListener("change"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

        section = self.app[self.app.index("function applyTransferAdjustments") :]
        section = section[: section.index("function", 20)]
        self.assertNotIn("fetch(", section)
        self.assertNotIn("volumeTextureManager.load", section)

    def test_quality_policy_remains_adaptive_during_interaction(self) -> None:
        for marker in (
            "RENDERING_QUALITY_POLICIES",
            "normalizeRenderingQualityPolicy",
            "setPolicy",
            'policy = "balanced"',
            'mode: "interactive"',
            'mode: "settled"',
            "recordFrameDuration",
            "minimumInteractiveSamplingRate",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.quality)

    def test_h1_cache_and_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r21-phase4h1-r1', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h1-r1', self.html)
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4h1"',
            self.app,
        )
        self.assertIn(
            'from "./volume-rendering-quality.js?v=phase4h1"',
            self.app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4h1_checks.sh").is_file())
        self.assertTrue(
            (ROOT / "scripts/check_phase4h1_display_controls.mjs").is_file()
        )

    def test_h1_r1_groups_overall_opacity_with_advanced_rendering(self) -> None:
        details_start = self.html.index('id="advancedRenderingControls"')
        details_end = self.html.index("</details>", details_start)
        details = self.html[details_start:details_end]
        self.assertIn('id="opacitySlider"', details)
        self.assertIn('id="opacityValue"', details)
        self.assertIn("Overall opacity", details)
        self.assertLess(details.index("Absorption"), details.index("Overall opacity"))
        self.assertNotIn('<section class="control-section opacity-control">', self.html)

    def test_h1_r1_uses_clear_professional_icons_and_blue_action_language(self) -> None:
        self.assertIn('class="upload-icon-svg"', self.html)
        self.assertIn('class="volume-status-icon"', self.html)
        self.assertIn('class="readiness-check"', self.html)
        self.assertIn("Phase 4H1-R1 - ergonomic medical workspace polish", self.styles)
        self.assertIn("--workflow-accent: var(--accent);", self.styles)
        self.assertIn(".volume-only-layer-grid .layer-button.is-active", self.styles)

    def test_h1_r1_mpr_tools_are_named_and_each_plane_can_enter_fullscreen(self) -> None:
        self.assertEqual(self.html.count('data-mpr-fullscreen="'), 3)
        for plane in ("axial", "coronal", "sagittal"):
            with self.subTest(plane=plane):
                self.assertIn(f'data-mpr-center="{plane}"', self.html)
                self.assertIn(f'data-mpr-reset-window="{plane}"', self.html)
                self.assertIn(f'data-mpr-fullscreen="{plane}"', self.html)
        for marker in (
            "toggleMprFullscreen",
            "syncFullscreenControls",
            'document.querySelectorAll("[data-mpr-fullscreen]")',
            "entry.panel.requestFullscreen()",
            'document.addEventListener("fullscreenchange"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

    def test_h1_r1_typography_is_responsive_not_globally_scaled(self) -> None:
        self.assertIn("--ui-readable", self.styles)
        self.assertIn("clamp(", self.styles)
        self.assertIn(".metadata-list dt", self.styles)
        self.assertIn(".transfer-adjustment-heading", self.styles)


if __name__ == "__main__":
    unittest.main()
