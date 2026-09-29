from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase6D0ExplicitSurfaceSelectionCorrectionTests(unittest.TestCase):
    def test_initial_structure_presentation_does_not_auto_select_or_request_3d_surface(self):
        module = (ROOT / 'web/js/segmentation-structure-panel.js').read_text()
        self.assertIn('selectedLabelId: null', module)
        self.assertNotIn('structures.keys().next().value', module)
        self.assertNotIn('structures.get(selectedLabelId).surfaceVisible = true', module)

    def test_reset_returns_to_no_3d_surface_selection(self):
        module = (ROOT / 'web/js/segmentation-structure-panel.js').read_text()
        self.assertIn('presentation.selectedLabelId = null;', module)
        self.assertNotIn('const selected = presentation.structures.get(presentation.selectedLabelId);', module)

    def test_empty_inspector_state_is_explicit(self):
        module = (ROOT / 'web/js/segmentation-structure-panel.js').read_text()
        self.assertIn('this.selectedName.textContent = "No structure selected";', module)
        self.assertIn('this.selectedMetadata.textContent = "Select a visible structure to edit its presentation.";', module)

    def test_cache_identity_advances_for_correction(self):
        app = (ROOT / 'web/js/app.js').read_text()
        html = (ROOT / 'web/index.html').read_text()
        self.assertIn('segmentation-structure-panel.js?v=phase5e-r1-phase6c-r2-phase6d0-explicit-r1', app)
        self.assertIn('phase6d0-r1-phase6d0-explicit-r1', html)


if __name__ == '__main__':
    unittest.main()
