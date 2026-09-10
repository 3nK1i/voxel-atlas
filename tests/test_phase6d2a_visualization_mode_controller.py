from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase6D2AVisualizationModeControllerTests(unittest.TestCase):
    def test_controller_module_declares_modes_and_surface_sources_separately(self):
        source = (ROOT / "web/js/reconstruction-visualization-mode.js").read_text(encoding="utf-8")
        self.assertIn('id: "volume"', source)
        self.assertIn('id: "surface"', source)
        self.assertIn('id: "combined"', source)
        self.assertIn('id: "volume-derived"', source)
        self.assertIn('id: "segmentation-derived"', source)
        self.assertIn("selectedSurfaceSources", source)
        self.assertIn("visibility", source)

    def test_controller_is_presentation_only_and_cannot_trigger_surface_builds(self):
        source = (ROOT / "web/js/reconstruction-visualization-mode.js").read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertNotIn("fetch(", lowered)
        self.assertNotIn("xmlhttprequest", lowered)
        self.assertNotIn("/api/", lowered)
        self.assertNotIn("marching", lowered)
        self.assertNotIn("segmentation-workflow", lowered)

    def test_phase6d2a_document_keeps_later_6d2_and_6e_6f_work_out_of_scope(self):
        doc = (ROOT / "docs/phase_history/PHASE6D2A_VISUALIZATION_MODE_CONTROLLER.md").read_text(encoding="utf-8")
        self.assertIn("e96f0138bbfe55963b7069680d8ead3d641d64d7", doc)
        self.assertIn("Volume", doc)
        self.assertIn("Surface", doc)
        self.assertIn("Combined", doc)
        self.assertIn("surface source", doc.lower())
        self.assertIn("6D2B", doc)
        self.assertIn("6D2C", doc)
        self.assertIn("6E", doc)
        self.assertIn("6F", doc)
        self.assertIn("Clinical validation is not claimed", doc)


if __name__ == "__main__":
    unittest.main()
