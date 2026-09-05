from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4H4DualSidedPatientLpsClippingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.renderer = (
            ROOT / "web/js/patient-volume-ray-marcher.js"
        ).read_text(encoding="utf-8")
        self.styles = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

    def test_workspace_exposes_three_dual_handle_anatomical_ranges(self) -> None:
        for plane in ("axial", "coronal", "sagittal"):
            for boundary in ("start", "end"):
                with self.subTest(plane=plane, boundary=boundary):
                    self.assertIn(
                        f'data-clip-{boundary}="{plane}"',
                        self.html,
                    )
                    self.assertIn(
                        f'data-clip-{boundary}-position="{plane}"',
                        self.html,
                    )
                    self.assertIn(
                        f'data-clip-{boundary}-percent="{plane}"',
                        self.html,
                    )

        for label in (
            "Inferior",
            "Superior",
            "Posterior",
            "Anterior",
            "Right",
            "Left",
        ):
            self.assertIn(label, self.html)

        self.assertNotIn("data-clip-side", self.html)
        self.assertNotIn("Keep Inferior", self.html)
        self.assertNotIn("Keep Superior", self.html)
        self.assertNotIn("Keep Anterior", self.html)
        self.assertNotIn("Keep Posterior", self.html)
        self.assertNotIn("Keep Right", self.html)
        self.assertNotIn("Keep Left", self.html)
        self.assertIn('id="clippingResetButton"', self.html)
        self.assertIn("clippingResetButton.addEventListener", self.app)

    def test_dual_handle_ranges_are_compact_accessible_and_highlight_retained_roi(self) -> None:
        for marker in (
            "clip-boundary-labels",
            "clip-dual-range",
            "clip-retained-track",
            "--clip-start-percent",
            "--clip-end-percent",
            "::-webkit-slider-thumb",
            "::-moz-range-thumb",
        ):
            self.assertIn(marker, self.styles + self.html)

        for label in (
            "Inferior clipping boundary",
            "Superior clipping boundary",
            "Posterior clipping boundary",
            "Anterior clipping boundary",
            "Right clipping boundary",
            "Left clipping boundary",
        ):
            self.assertIn(f'aria-label="{label}"', self.html)

    def test_app_keeps_clipping_boundaries_independent_from_mpr_crosshair(self) -> None:
        for marker in (
            "CLIPPING_MINIMUM_GAP_PERCENT",
            "clippingBoundaryLpsMm",
            "updateClippingBoundaryFromControl",
            "minimumLpsMm",
            "maximumLpsMm",
        ):
            self.assertIn(marker, self.app)

        request_start = self.app.index("function clippingRequest()")
        request_end = self.app.index("function applyPatientClipping()", request_start)
        request = self.app[request_start:request_end]
        self.assertNotIn("crosshairLpsMm", request)
        self.assertNotIn("retainedSide", request)

        update_start = self.app.index("function updateClippingBoundaryFromControl")
        update_end = self.app.index("function resetPatientClipping", update_start)
        update = self.app[update_start:update_end]
        self.assertNotIn("crosshairLpsMm", update)
        self.assertNotIn("scheduleMprRender", update)

    def test_shader_intersects_six_physical_patient_lps_planes(self) -> None:
        for marker in (
            "uClipBoundsMinimum",
            "uClipBoundsMaximum",
            "clipAgainstPatientRange",
            "clipPatientRayInterval",
            "patientPointRetained",
            "minimumPositionsLpsMm",
            "maximumPositionsLpsMm",
            "sixPlaneCount",
        ):
            self.assertIn(marker, self.renderer)

        self.assertNotIn("uClipPlaneKeepSigns", self.renderer)
        self.assertNotIn("uClipPlanePositions", self.renderer)
        self.assertNotIn("keepSigns", self.renderer)

    def test_coronal_ergonomic_direction_is_reversed_from_lps_y(self) -> None:
        self.assertIn('startLabel: "Posterior"', self.app)
        self.assertIn('endLabel: "Anterior"', self.app)
        self.assertIn("reversed: true", self.app)
        self.assertIn('axis: "y"', self.app)

    def test_all_volume_modes_reuse_the_same_clipped_resident_texture(self) -> None:
        for mode in (
            "RENDER_MODE_DVR",
            "RENDER_MODE_MIP",
            "RENDER_MODE_MINIP",
            "RENDER_MODE_AVERAGE",
            "RENDER_MODE_SLICE",
            "RENDER_MODE_THICK_SLAB",
        ):
            self.assertIn(mode, self.renderer)
        self.assertIn("uVolume: { value: texture }", self.renderer)
        self.assertNotIn("textureResource.texture.image.data", self.app)
        self.assertNotIn("segmentation", self.html.lower())

    def test_h4_cache_and_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r21-phase4h5', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h5', self.html)
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4h4"',
            self.app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4h4_checks.sh").is_file())
        self.assertTrue((ROOT / "scripts/check_phase4h4_dual_clipping.mjs").is_file())


if __name__ == "__main__":
    unittest.main()
