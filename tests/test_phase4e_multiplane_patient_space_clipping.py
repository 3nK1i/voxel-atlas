from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4EMultiplanePatientSpaceClippingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.renderer = (
            ROOT / "web/js/patient-volume-ray-marcher.js"
        ).read_text(encoding="utf-8")

    def test_workspace_exposes_three_independent_patient_space_planes(self) -> None:
        for plane in ("axial", "coronal", "sagittal"):
            for marker in (
                f'data-clip-enabled="{plane}"',
                f'data-clip-slider="{plane}"',
                f'data-clip-side="{plane}"',
                f'data-clip-position="{plane}"',
            ):
                with self.subTest(marker=marker):
                    self.assertIn(marker, self.html)

        for side in (
            "Keep Inferior",
            "Keep Superior",
            "Keep Anterior",
            "Keep Posterior",
            "Keep Right",
            "Keep Left",
        ):
            with self.subTest(side=side):
                self.assertIn(side, self.html)

        self.assertNotIn('id="sectionSlider"', self.html)
        self.assertNotIn("sectionSlider.disabled = true", self.app)

    def test_ray_interval_is_clipped_in_dicom_patient_lps_space(self) -> None:
        for marker in (
            "uLocalToPatientLps",
            "uClipPlanePositions",
            "uClipPlaneKeepSigns",
            "uClipPlaneEnabled",
            "clipPatientRayInterval",
            "clipAgainstPatientPlane",
            "setClippingPlanes",
            "createPatientClippingState",
            "DICOM Patient LPS millimetres",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.renderer)

        self.assertIn(
            "vec2 intersection = clipPatientRayInterval",
            self.renderer,
        )
        self.assertNotIn("marchingCubes", self.renderer)
        self.assertNotIn("isocontour", self.renderer.lower())

    def test_clipping_and_mpr_share_the_same_patient_coordinates(self) -> None:
        for marker in (
            "CLIPPING_PLANES",
            "state.mpr.crosshairLpsMm",
            "syncClippingControlsFromMpr",
            "updateClippingFromControl",
            "applyPatientClipping",
            "volumeRayMarcher.setClippingPlanes",
            "updateMprCrosshairOverlays",
            "scheduleMprRender",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

        self.assertIn('data-clipping-state="unavailable"', self.html)

    def test_reset_disables_all_planes_without_changing_transfer_or_volume(self) -> None:
        reset = self.app[self.app.index("function resetWorkspace()") :]
        reset = reset[: reset.index("function preferredTheme")]
        self.assertIn("resetPatientClipping()", reset)
        self.assertIn("applyTransferPreset", reset)
        self.assertIn("applyOpacity", reset)
        self.assertNotIn("volumeRayMarcher.dispose", reset)
        self.assertNotIn("volumeTextureManager.dispose", reset)

    def test_low_density_ct_label_is_anatomy_neutral(self) -> None:
        self.assertIn('id: "ct-lung"', self.renderer)
        self.assertIn('label: "Low-Density CT"', self.renderer)
        self.assertNotIn('label: "Lung"', self.renderer)
        self.assertNotIn("lung-range", self.renderer)

    def test_phase4e_cache_and_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r21-phase4g', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4g', self.html)
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4f"',
            self.app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4e_checks.sh").is_file())
        self.assertTrue(
            (ROOT / "scripts/check_phase4e_patient_clipping.mjs").is_file()
        )


if __name__ == "__main__":
    unittest.main()
