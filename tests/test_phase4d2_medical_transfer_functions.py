from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4D2MedicalTransferFunctionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.renderer = (
            ROOT / "web/js/patient-volume-ray-marcher.js"
        ).read_text(encoding="utf-8")

    def test_workspace_exposes_compact_medical_transfer_controls(self) -> None:
        for marker in (
            'id="volumeRenderingPanel"',
            'id="transferPresetSelect"',
            'id="transferRangeLow"',
            'id="transferRangeHigh"',
            'id="transferDensity"',
            'id="transferResetButton"',
            'id="transferFunctionNote"',
            'aria-label="Medical volume rendering preset"',
            'aria-label="Minimum visible medical intensity"',
            'aria-label="Maximum visible medical intensity"',
            'aria-label="Volume rendering absorption"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.html)

    def test_renderer_uses_piecewise_color_and_opacity_transfer_points(self) -> None:
        for marker in (
            "TRANSFER_POINT_COUNT = 6",
            "uniform float uTransferIntensities[",
            "uniform float uTransferOpacities[",
            "uniform vec3 uTransferColors[",
            "sampleMedicalTransfer",
            "createMedicalTransferFunction",
            "listMedicalTransferPresets",
            "setTransferPreset",
            "uDensityScale",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.renderer)

        self.assertNotIn("marchingCubes", self.renderer)
        self.assertNotIn("isocontour", self.renderer.lower())

    def test_ct_and_mr_preset_contract_is_modality_truthful(self) -> None:
        for preset in (
            'id: "ct-general"',
            'id: "ct-soft-tissue"',
            'id: "ct-bone"',
            'id: "ct-lung"',
            'id: "mr-balanced"',
            'id: "mr-lower-intensity"',
            'id: "mr-higher-intensity"',
        ):
            with self.subTest(preset=preset):
                self.assertIn(preset, self.renderer)

        self.assertIn('units === "HU"', self.renderer)
        self.assertIn('|| "modality"', self.renderer)
        for unsupported_claim in ("mr-t1", "mr-t2", "mr-flair"):
            self.assertNotIn(unsupported_claim, self.renderer.lower())

    def test_controls_update_gpu_uniforms_without_reloading_volume(self) -> None:
        for marker in (
            "configureTransferControls",
            "applyTransferPreset",
            "applyTransferAdjustments",
            "volumeRayMarcher.setTransferPreset",
            'transferPresetSelect.addEventListener("change"',
            'transferRangeLow.addEventListener("input"',
            'transferRangeHigh.addEventListener("input"',
            'transferDensity.addEventListener("input"',
            'transferResetButton.addEventListener("click"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

        controls_section = self.app[self.app.index("function applyTransferAdjustments") :]
        controls_section = controls_section[: controls_section.index("function", 20)]
        self.assertNotIn("fetch(", controls_section)
        self.assertNotIn("volumeTextureManager.load", controls_section)

    def test_phase4e_multi_plane_clipping_is_integrated(self) -> None:
        combined = self.html + self.app
        self.assertIn('id="directionalCutPanel"', combined)
        self.assertIn('data-clip-enabled="axial"', combined)
        self.assertIn('data-clip-enabled="coronal"', combined)
        self.assertIn('data-clip-enabled="sagittal"', combined)
        self.assertIn("volumeRayMarcher.setClippingPlanes", combined)

        documentation = (
            ROOT / "docs/phase_history/PHASE4D2_MEDICAL_TRANSFER_FUNCTIONS.md"
        ).read_text(encoding="utf-8")
        self.assertIn("multi-plane patient-space clipping", documentation)
        self.assertIn("Phase 4E", documentation)
        self.assertIn("No segmentation", documentation)

    def test_phase4d2_cache_and_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r21-phase4h6', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h6', self.html)
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4h6"',
            self.app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4d2_checks.sh").is_file())
        self.assertTrue(
            (ROOT / "scripts/check_phase4d2_transfer_functions.mjs").is_file()
        )


if __name__ == "__main__":
    unittest.main()
