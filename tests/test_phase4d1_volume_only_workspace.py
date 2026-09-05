from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4D1VolumeOnlyWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

    def test_full_volume_is_the_only_anatomical_layer(self) -> None:
        self.assertEqual(self.html.count('data-layer="'), 1)
        self.assertIn(
            'class="layer-button is-active" data-layer="volume" disabled aria-pressed="true"',
            self.html,
        )
        self.assertIn("volume-only-layer-grid", self.html)

        for forbidden in (
            'data-layer="skull"',
            'data-layer="brain"',
            'data-layer="combined"',
            "data-future-layer=",
            "Skull + Brain",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.html)

    def test_browser_has_no_surface_model_runtime_or_fallback(self) -> None:
        for forbidden in (
            "GLTFLoader",
            "SKULL_URL",
            "loadSkull",
            "prepareSkull",
            "createClinicalMaterial",
            "MeshPhysicalMaterial",
            "/assets/models/",
            'layerRegistry.get("skull")',
            'layerRegistry.get("brain")',
            'state.layer = "skull"',
            "Demo anatomy",
            "Demo skull",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.app)

    def test_volume_only_state_remains_truthful_until_gpu_rendering_is_ready(self) -> None:
        combined = self.html + self.app
        for marker in (
            'id="volumeStatusRow"',
            'id="volumeLayerButton"',
            "const volumeLayer =",
            "setVolumeAvailability(false)",
            "setVolumeAvailability(true)",
            'modelChip.textContent = "Patient scan - Full Volume"',
            "Upload a CT or MRI DICOM study to visualize its voxel volume in 3D.",
            "Synchronized MPR remains available.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

        self.assertNotIn('id="surfaceStatusRow"', self.html)
        self.assertNotIn("registerLayer", self.app)
        self.assertNotIn("setLayer(", self.app)

    def test_volume_controls_and_c2_ray_marcher_remain_connected(self) -> None:
        combined = self.html + self.app
        for marker in (
            "PatientVolumeRayMarcher",
            "volumeRayMarcher.create",
            "volumeRayMarcher.setOpacity",
            "volumeRayMarcher.dispose",
            'id="opacitySlider"',
            'id="directionalCutPanel"',
            'data-clip-enabled="axial"',
            'data-clip-enabled="coronal"',
            'data-clip-enabled="sagittal"',
            'fetch("/api/studies/latest/volume-rendering"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_phase4d1_cache_boundary_and_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h4', self.html)
        self.assertTrue((ROOT / "scripts/run_phase4d1_checks.sh").is_file())
        self.assertTrue((ROOT / "scripts/check_phase4d1_volume_only_workspace.mjs").is_file())


if __name__ == "__main__":
    unittest.main()
