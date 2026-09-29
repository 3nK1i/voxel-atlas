from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase6FDPerStructureClippingParticipationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.panel = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
        self.interaction = (ROOT / "web/js/segmentation-structure-interaction.js").read_text(encoding="utf-8")
        self.seg_viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
        self.volume_viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")

    def test_selected_structure_exposes_directional_cut_participation(self) -> None:
        self.assertIn('id="segmentationStructureClipParticipation"', self.html)
        self.assertIn("Follow Directional Cut", self.html)
        self.assertIn("this.clippingParticipation", self.panel)
        self.assertIn("structure.clippingEnabled = this.clippingParticipation.checked", self.panel)

    def test_existing_interaction_state_remains_the_authority(self) -> None:
        self.assertIn("clippingEnabled: true", self.interaction)
        self.assertIn("clippingEnabled: structure.clippingEnabled !== false", self.interaction)
        self.assertNotIn("fetch(", self.interaction)
        self.assertNotIn("marching_cubes", self.interaction)

    def test_same_patient_lps_clipping_request_drives_volume_and_surfaces(self) -> None:
        self.assertIn("const request = clippingRequest();", self.app)
        self.assertIn("volumeSurfaceLayer?.setClippingPlanes(request)", self.app)
        self.assertIn("segmentationSurfaceLayer?.setClippingPlanes(request)", self.app)
        self.assertIn("volumeRayMarcher.setClippingPlanes(request)", self.app)

    def test_surface_viewers_use_display_only_material_clipping(self) -> None:
        self.assertIn("setClippingPlanes(clipping = {})", self.seg_viewer)
        self.assertIn("interaction.clippingEnabled", self.seg_viewer)
        self.assertIn("applySurfaceClippingToMaterial", self.seg_viewer)
        self.assertIn("setClippingPlanes(clipping = {})", self.volume_viewer)
        self.assertIn("applySurfaceClippingToMaterial", self.volume_viewer)
        for text in (self.seg_viewer, self.volume_viewer):
            start = text.index("setClippingPlanes(clipping = {})")
            end = text.index("\n  }", start) + 4
            clipping_method = text[start:end]
            self.assertNotIn("geometry.setAttribute", clipping_method)
            self.assertNotIn("geometry.applyMatrix4", clipping_method)
            self.assertNotIn("fetch(", clipping_method)

    def test_surface_clipping_helper_is_present_and_geometry_free(self) -> None:
        helper = ROOT / "web/js/reconstruction-surface-clipping.js"
        self.assertTrue(helper.is_file())
        text = helper.read_text(encoding="utf-8")
        for marker in (
            "resolvePatientSurfaceClippingDescriptors",
            "applySurfaceClippingToMaterial",
            "enableSurfaceLocalClipping",
            "Patient LPS",
        ):
            self.assertIn(marker, text)
        for forbidden in (
            "fetch(",
            "marching_cubes",
            "setAttribute(\"position\"",
            "setIndex(",
            "applyMatrix4(",
        ):
            self.assertNotIn(forbidden, text)

    def test_phase6f_d_stays_inside_roadmap_boundary(self) -> None:
        combined = self.html + "\n" + self.app + "\n" + self.panel
        self.assertNotIn("segmentationStructureExplode", combined)
        self.assertNotIn("transform gizmo", combined.lower())
        self.assertNotIn("boolean mesh", combined.lower())


if __name__ == "__main__":
    unittest.main()
