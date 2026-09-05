from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4FAdaptiveRenderingQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.ray_marcher = (
            ROOT / "web/js/patient-volume-ray-marcher.js"
        ).read_text(encoding="utf-8")
        quality_path = ROOT / "web/js/volume-rendering-quality.js"
        self.quality = quality_path.read_text(encoding="utf-8") if quality_path.exists() else ""

    def test_quality_policy_is_workload_and_device_aware(self) -> None:
        for marker in (
            "createAdaptiveRenderingProfile",
            "texture_dimensions",
            "voxelCount",
            "settledSamplingRate",
            "interactiveSamplingRate",
            "settledPixelRatio",
            "interactivePixelRatio",
            "targetFrameMs",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.quality)

    def test_interaction_reduces_quality_then_restores_settled_quality(self) -> None:
        for marker in (
            "AdaptiveVolumeRenderingQuality",
            "beginInteraction",
            "endInteraction",
            "pulseInteraction",
            "settleDelayMs",
            'mode: "interactive"',
            'mode: "settled"',
            "setSamplingRate",
            "setPixelRatio",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.quality)

    def test_actual_frame_pressure_can_back_off_interactive_work(self) -> None:
        for marker in (
            "recordFrameDuration",
            "frameSamples",
            "minimumInteractiveSamplingRate",
            "FRAME_PRESSURE_SAMPLE_COUNT",
            "FRAME_PRESSURE_THRESHOLD",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.quality)

    def test_app_connects_orbit_sliders_auto_rotate_and_idle_rendering(self) -> None:
        for marker in (
            "AdaptiveVolumeRenderingQuality",
            'controls.addEventListener("start"',
            'controls.addEventListener("end"',
            'controls.addEventListener("change"',
            "qualityInteractionControls",
            'beginInteraction("auto-rotate")',
            'endInteraction("auto-rotate")',
            "viewerRenderRequested",
            "shouldRender",
            "recordFrameDuration",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

        self.assertNotIn("renderer.render(scene, camera);\n  requestAnimationFrame", self.app)

    def test_ray_marcher_sampling_rate_is_bounded_and_mutable(self) -> None:
        for marker in (
            "MIN_RAY_SAMPLING_RATE",
            "MAX_RAY_STEPS",
            "setSamplingRate",
            "uSamplingRate.value",
            "qualityState",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.ray_marcher)

    def test_quality_state_is_visible_without_medical_overclaim(self) -> None:
        self.assertIn('id="renderQualityStatus"', self.html)
        self.assertIn("Rendering quality", self.html)
        self.assertNotIn("diagnostic quality", (self.html + self.quality).lower())

    def test_phase4f_cache_and_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h6', self.html)
        self.assertIn(
            'from "./volume-rendering-quality.js?v=phase4h1"',
            self.app,
        )
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4h6"',
            self.app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4f_checks.sh").is_file())
        self.assertTrue((ROOT / "scripts/check_phase4f_adaptive_quality.mjs").is_file())


if __name__ == "__main__":
    unittest.main()
