from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4H3BSliceAndThickSlabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.renderer = (
            ROOT / "web/js/patient-volume-ray-marcher.js"
        ).read_text(encoding="utf-8")

    def test_primary_selector_adds_true_slice_and_thick_slab_modes(self) -> None:
        self.assertIn('<option value="slice">Slice</option>', self.html)
        self.assertIn('<option value="thick-slab">Thick Slab</option>', self.html)
        self.assertIn('id="sliceRenderingControls"', self.html)
        self.assertIn('id="slicePlaneSelect"', self.html)
        self.assertIn('id="slicePosition"', self.html)
        self.assertIn('id="slabThicknessSelect"', self.html)
        self.assertIn('id="slabProjectionSelect"', self.html)

    def test_controls_use_patient_anatomical_planes_and_physical_units(self) -> None:
        for value, label in (
            ("axial", "Axial"),
            ("coronal", "Coronal"),
            ("sagittal", "Sagittal"),
        ):
            with self.subTest(value=value):
                self.assertIn(f'<option value="{value}"', self.html)
                self.assertIn(label, self.html)
        for value in ("1", "5", "10", "20", "custom"):
            self.assertIn(f'<option value="{value}"', self.html)
        self.assertIn("mm", self.html)
        self.assertIn("DICOM Patient LPS", self.html)

    def test_shader_samples_plane_and_slab_in_patient_lps(self) -> None:
        for marker in (
            "RENDER_MODE_SLICE",
            "RENDER_MODE_THICK_SLAB",
            "uSlicePlaneAxis",
            "uSlicePositionLpsMm",
            "uSlabThicknessMm",
            "uSlabProjectionMode",
            "uSliceSampleSpacingMm",
            "uSlicePatientBoundsMinimum",
            "uSlicePatientBoundsMaximum",
            "samplePatientPlane",
            "samplePatientThickSlab",
            "decodeMedicalIntensityLinear",
            "texelFetch(uVolume",
            "uLocalToPatientLps",
            "inverse(uLocalToPatientLps)",
            "windowMedicalIntensity(projectedIntensity)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.renderer)

    def test_slice_state_is_uniform_only_and_reuses_resident_texture(self) -> None:
        self.assertIn("setSliceRendering(settings", self.renderer)
        self.assertIn("sliceRenderingState", self.renderer)
        self.assertIn("uniforms.uSlicePositionLpsMm.value", self.renderer)

        start = self.app.index('slicePosition.addEventListener("input"')
        end = self.app.index('slabThicknessSelect.addEventListener', start)
        handler = self.app[start:end]
        self.assertIn("state.mpr.crosshairLpsMm", handler)
        self.assertIn("syncSliceRenderingControlsFromMpr", handler)
        self.assertNotIn("fetch(", handler)
        self.assertNotIn("volumeTextureManager.load", handler)
        self.assertNotIn("volumeRayMarcher.create", handler)

    def test_thick_slab_exposes_three_truthful_aggregation_methods(self) -> None:
        for value, label in (
            ("mip", "MIP"),
            ("minip", "MinIP"),
            ("average", "Average"),
        ):
            with self.subTest(value=value):
                self.assertIn(f'<option value="{value}"', self.html)
                self.assertIn(label, self.html)
        self.assertIn("SLAB_PROJECTION_METHODS", self.renderer)
        self.assertIn("constrainPatientSliceSettings", self.renderer)

    def test_slice_preserves_full_plane_windowing_and_disables_interval_cutoffs(self) -> None:
        sample_start = self.renderer.index("bool samplePatientPlane(")
        sample_end = self.renderer.index("bool samplePatientThickSlab(", sample_start)
        slice_sampling = self.renderer[sample_start:sample_end]
        self.assertNotIn("uIntensityBounds", slice_sampling)
        self.assertIn("setIntensityIntervalControlsEnabled", self.app)
        self.assertIn('mode.id !== "slice"', self.app)

    def test_crosshair_and_mpr_geometry_are_the_single_position_source(self) -> None:
        self.assertIn("syncSliceRenderingControlsFromMpr", self.app)
        self.assertIn("state.mpr.descriptor.planes", self.app)
        self.assertIn("state.mpr.crosshairLpsMm", self.app)
        self.assertIn("scheduleMprRender", self.app)
        self.assertNotIn("screenAxis", self.app)

    def test_h3b_cache_and_compact_validation_entrypoints_are_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r21-phase4h4', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h4', self.html)
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4h4"',
            self.app,
        )
        self.assertTrue((ROOT / "scripts/run_phase4h3b_checks.sh").is_file())
        self.assertTrue((ROOT / "scripts/check_phase4h3b_slice_slab.mjs").is_file())

    def test_canonical_volume_and_safety_contracts_remain_unchanged(self) -> None:
        self.assertIn("decodeMedicalIntensity", self.renderer)
        self.assertIn("clipPatientRayInterval", self.renderer)
        self.assertNotIn("textureResource.texture.image.data", self.app)
        self.assertNotIn("marchingCubes", self.renderer)
        self.assertNotIn("segmentation", self.html.lower())


if __name__ == "__main__":
    unittest.main()
