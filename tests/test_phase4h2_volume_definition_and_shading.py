from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4H2VolumeDefinitionAndShadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.renderer = (
            ROOT / "web/js/patient-volume-ray-marcher.js"
        ).read_text(encoding="utf-8")
        self.styles = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

    def test_definition_controls_use_advanced_progressive_disclosure(self) -> None:
        start = self.html.index('id="advancedRenderingControls"')
        end = self.html.index("</details>", start)
        advanced = self.html[start:end]
        for marker in (
            'id="transferOpacitySoftness"',
            'id="transferOpacitySoftnessValue"',
            'id="transferEdgeDefinition"',
            'id="transferEdgeDefinitionValue"',
            'id="transferShadingStrength"',
            'id="transferShadingStrengthValue"',
            "Opacity softness",
            "Edge definition",
            "Depth shading",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, advanced)

        self.assertIn("Intensity minimum", advanced)
        self.assertIn("Intensity maximum", advanced)
        self.assertIn("selected intensity cutoffs", advanced)

        self.assertNotIn("clinically segmented", advanced.lower())
        self.assertNotIn("diagnostic", advanced.lower())

    def test_shader_uses_voxel_gradient_without_changing_medical_values(self) -> None:
        for marker in (
            "uTextureTexelSize",
            "uOpacitySoftness",
            "uEdgeDefinition",
            "uShadingStrength",
            "opacityBoundaryWeight",
            "sampleMedicalGradient",
            "applyMedicalDepthShading",
            "patientSpaceMedicalGradient",
            "evaluateOpacitySoftnessWeight",
            "evaluateEdgeDefinitionWeight",
            "evaluateDepthShadingFactor",
            "transpose(inverse(textureToPatient))",
            "uLocalToPatientLps",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.renderer)

        self.assertIn("lowByte + highByte * 256.0", self.renderer)
        self.assertIn("uDecodeOffset + uDecodeScale", self.renderer)
        self.assertNotIn("textureResource.texture.image.data", self.app)
        self.assertNotIn("marchingCubes", self.renderer)

    def test_intensity_boundaries_keep_fixed_independent_source_domains(self) -> None:
        sync_start = self.app.index("function syncTransferControls")
        sync_end = self.app.index("function configureTransferControls", sync_start)
        sync = self.app[sync_start:sync_end]
        self.assertIn('transferRangeLow.max = String(sourceHigh)', sync)
        self.assertIn('transferRangeHigh.min = String(sourceLow)', sync)
        self.assertNotIn("transfer.rangeHigh - minimumGap", sync)
        self.assertNotIn("transfer.rangeLow + minimumGap", sync)
        self.assertIn("constrainMedicalIntensityInterval", self.app)

    def test_transfer_control_initialization_defines_window_width_minimum(self) -> None:
        sync_start = self.app.index("function syncTransferControls")
        sync_end = self.app.index("function configureTransferControls", sync_start)
        sync = self.app[sync_start:sync_end]
        self.assertIn(
            "const minimumInterval = Math.max(step, 0.000001);",
            sync,
        )
        self.assertIn(
            "transferWindowWidth.min = String(minimumInterval);",
            sync,
        )
        self.assertNotIn("minimumGap", sync)

    def test_display_parameters_are_preset_backed_and_validated(self) -> None:
        for marker in (
            "opacitySoftness",
            "edgeDefinition",
            "shadingStrength",
            'normalizedDisplayParameter(adjustments.opacitySoftness',
            'normalizedDisplayParameter(adjustments.edgeDefinition',
            'normalizedDisplayParameter(adjustments.shadingStrength',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.renderer)

    def test_controls_update_uniforms_without_refetching_or_reuploading_volume(self) -> None:
        for marker in (
            'transferOpacitySoftness.addEventListener("input"',
            'transferEdgeDefinition.addEventListener("input"',
            'transferShadingStrength.addEventListener("input"',
            "markTransferCustomized",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

        section = self.app[self.app.index("function applyTransferAdjustments") :]
        section = section[: section.index("function", 20)]
        self.assertNotIn("fetch(", section)
        self.assertNotIn("volumeTextureManager.load", section)

    def test_h2_cache_and_compact_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r21-phase4h2-r1', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h2-r1a', self.html)
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4h2-r1"',
            self.app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4h2_checks.sh").is_file())
        self.assertTrue((ROOT / "scripts/check_phase4h2_volume_definition.mjs").is_file())

    def test_advanced_controls_remain_compact_and_responsive(self) -> None:
        self.assertIn("Phase 4H2 - professional volume definition", self.styles)
        self.assertIn(".advanced-rendering-hint", self.styles)
        self.assertIn(".transfer-definition-controls", self.styles)


if __name__ == "__main__":
    unittest.main()
