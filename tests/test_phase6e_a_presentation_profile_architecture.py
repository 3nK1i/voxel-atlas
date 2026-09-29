from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
CSS = ROOT / "web/css/styles.css"
CTRL = ROOT / "web/js/reconstruction-presentation-profile.js"
DOC = ROOT / "docs/phase_history/PHASE6E_A_PRESENTATION_PROFILE_ARCHITECTURE.md"


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


class Phase6EAPresentationProfileArchitectureTests(unittest.TestCase):
    def test_profile_controller_declares_only_fidelity_and_presentation(self):
        source = CTRL.read_text(encoding="utf-8")
        self.assertIn('id: "fidelity"', source)
        self.assertIn('id: "presentation"', source)
        self.assertIn('this.profile = "fidelity"', source)
        self.assertNotIn('id: "diagnostic"', source.lower())
        self.assertNotIn('id: "teaching"', source.lower())

    def test_profile_controller_is_strictly_presentation_state_and_io_free(self):
        source = CTRL.read_text(encoding="utf-8")
        lowered = source.lower()
        for token in ("fetch(", "xmlhttprequest", "/api/", "marching", "segmentation-workflow", ".build("):
            self.assertNotIn(token, lowered)
        for token in ("position", "index", "triangle", "vertex", "affine", "isovalue", "hu"):
            self.assertNotIn(token, lowered)

    def test_profile_control_is_in_right_3d_view_and_not_left_reconstruction_modes(self):
        index = INDEX.read_text(encoding="utf-8")
        right_start = index.index('id="reconstructionVisualizationPanel"')
        right_end = index.index('</section>', right_start)
        right = index[right_start:right_end]
        left_start = index.index('id="reconstructionPanel"')
        left_end = index.index('</section>', left_start)
        left = index[left_start:left_end]
        self.assertIn('data-reconstruction-presentation-profile="fidelity"', right)
        self.assertIn('data-reconstruction-presentation-profile="presentation"', right)
        self.assertIn('id="reconstructionPresentationProfileStatus"', right)
        self.assertNotIn('data-reconstruction-presentation-profile=', left)

    def test_app_wires_profile_state_separately_from_visualization_mode_and_surface_sources(self):
        app = APP.read_text(encoding="utf-8")
        self.assertIn("ReconstructionPresentationProfileController", app)
        self.assertIn("reconstructionPresentationProfileController", app)
        self.assertIn("requestReconstructionPresentationProfile", app)
        profile_block = block(
            app,
            "function applyReconstructionPresentationProfileSnapshot(",
            "function requestReconstructionPresentationProfile(",
        )
        lowered = profile_block.lower()
        self.assertNotIn("requestreconstructionvisualizationmode", lowered)
        self.assertNotIn("requestreconstructionsurfacesourceselection", lowered)
        self.assertNotIn("fetch(", lowered)
        self.assertNotIn(".build(", lowered)

    def test_profile_controller_remains_free_of_rendering_implementation_details(self):
        app = APP.read_text(encoding="utf-8")
        controller = CTRL.read_text(encoding="utf-8")
        for token in (
            "meshstandardmaterial",
            "hemispherelight",
            "directionallight",
            "roughness",
            "metalness",
            "envmapintensity",
        ):
            self.assertNotIn(token, controller.lower())
        profile_block = block(
            app,
            "function applyReconstructionPresentationProfileSnapshot(",
            "function requestReconstructionPresentationProfile(",
        ).lower()
        self.assertNotIn("new three.", profile_block)
        self.assertNotIn("roughness =", profile_block)
        self.assertNotIn("metalness =", profile_block)


    def test_existing_6d2_mode_and_surface_source_controls_remain_present(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertEqual(index.count('data-reconstruction-mode='), 3)
        self.assertIn('data-reconstruction-surface-source="volume-derived"', index)
        self.assertIn('data-reconstruction-surface-source="segmentation-derived"', index)
        self.assertIn('value="300"', index)
        self.assertIn("Bone baseline: 300 HU when in range", index)

    def test_profile_ui_explains_geometry_is_unchanged(self):
        index = INDEX.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("Geometry and source data remain unchanged", index)
        self.assertIn("reconstruction-presentation-profile", css)
        self.assertIn("reconstruction-presentation-profile-option", css)

    def test_phase6e_a_document_preserves_6e_substep_boundaries(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("a7b8637460bc3c5ae657b4fd5ef8a8d5199ee474", doc)
        self.assertIn("Fidelity", doc)
        self.assertIn("Presentation", doc)
        self.assertIn("6E-B", doc)
        self.assertIn("lighting", doc.lower())
        self.assertIn("material", doc.lower())
        self.assertIn("6F", doc)
        self.assertIn("Clinical validation is not claimed", doc)


if __name__ == "__main__":
    unittest.main()
