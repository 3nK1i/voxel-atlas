from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4C1VolumeTextureTransportTests(unittest.TestCase):
    def test_browser_manages_verified_patient_volume_texture_lifecycle(self) -> None:
        manager = (ROOT / "web/js/volume-texture-manager.js").read_text(encoding="utf-8")
        app_js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        for marker in (
            "crypto.subtle.digest",
            "X-VoxelAtlas-Volume-Revision",
            "X-VoxelAtlas-Volume-SHA256",
            "new this.three.Data3DTexture",
            "texture.internalFormat = \"RG8\"",
            "texture.unpackAlignment = 1",
            "texture.dispose()",
            "AbortController",
            "fetchImpl.bind(globalThis)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, manager)

        self.assertIn("new PatientVolumeTextureManager", app_js)
        self.assertIn("renderer.initTexture(texture)", app_js)
        self.assertGreaterEqual(app_js.count("volumeTextureManager.dispose();"), 2)
        self.assertGreaterEqual(app_js.count("volumeRenderingTask !== task"), 2)

    def test_c1_transport_remains_separate_from_the_c2_ray_marcher(self) -> None:
        app_js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        manager = (ROOT / "web/js/volume-texture-manager.js").read_text(encoding="utf-8")

        self.assertIn('data-layer="volume" disabled', html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h3b', html)
        self.assertIn(
            'from "./volume-texture-manager.js?v=phase4c1-r1"',
            app_js,
        )
        self.assertNotIn("sampler3D", manager)
        self.assertIn("await activatePatientVolumeRendering(textureResource, task)", app_js)

    def test_compact_c1_validation_entrypoint_is_present(self) -> None:
        runner = ROOT / "scripts/run_phase4c1_checks.sh"
        documentation = (
            ROOT / "docs/phase_history/PHASE4C1_VERIFIED_VOLUME_TEXTURE_TRANSPORT.md"
        )

        self.assertTrue(runner.is_file())
        self.assertTrue(documentation.is_file())


if __name__ == "__main__":
    unittest.main()
