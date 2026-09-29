from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
CTRL = ROOT / "web/js/reconstruction-visualization-mode.js"
DOC = ROOT / "docs/phase_history/PHASE6D2C_COMBINED_VISUALIZATION.md"


def function_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


class Phase6D2CCombinedVisualizationTests(unittest.TestCase):
    def test_combined_mode_is_enabled_by_capability_not_hard_disabled(self):
        index = INDEX.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        marker = 'data-reconstruction-mode="combined"'
        start = index.rfind("<button", 0, index.index(marker))
        end = index.index("</button>", index.index(marker)) + len("</button>")
        combined = index[start:end]
        self.assertNotIn("disabled", combined)
        self.assertIn("snapshot.canCombined", app)
        request = function_block(app, "function requestReconstructionVisualizationMode(", "function setVolumeAvailability(")
        self.assertNotIn('modeId === "combined"', request)
        self.assertIn("requestMode(modeId)", request)
        self.assertIn("phase6d2c-r1", index)

    def test_surface_source_controls_are_explicit_and_separate_from_modes(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn('data-reconstruction-surface-source="volume-derived"', index)
        self.assertIn('data-reconstruction-surface-source="segmentation-derived"', index)
        self.assertIn("Surface sources", index)
        self.assertIn("Direct CT", index)
        self.assertIn("Segmentation", index)

    def test_source_selection_is_presentation_only_and_cannot_build_or_fetch(self):
        app = APP.read_text(encoding="utf-8")
        block = function_block(
            app,
            "function requestReconstructionSurfaceSourceSelection(",
            "function setVolumeAvailability(",
        )
        lowered = block.lower()
        self.assertIn("selectSurfaceSource", block)
        self.assertNotIn("fetch(", lowered)
        self.assertNotIn(".build(", lowered)
        self.assertNotIn(".clear(", lowered)
        self.assertNotIn("segmentation-workflow", lowered)

    def test_resource_sync_preserves_user_source_preferences(self):
        app = APP.read_text(encoding="utf-8")
        block = function_block(
            app,
            "function syncReconstructionVisualizationResources()",
            "function requestReconstructionVisualizationMode(",
        )
        self.assertIn("state.reconstructionVisualization.surfaceSourceSelection", block)
        self.assertIn('"volume-derived"', block)
        self.assertIn('"segmentation-derived"', block)
        self.assertIn("state.segmentationSurface.enabled", block)

    def test_combined_status_is_truthful_about_selected_resident_sources(self):
        app = APP.read_text(encoding="utf-8")
        block = function_block(
            app,
            "function applyReconstructionVisualizationSnapshot(",
            "function syncReconstructionVisualizationResources()",
        )
        self.assertIn('snapshot.mode === "combined"', block)
        self.assertIn("selectedResidentSurfaceSources", block)
        self.assertIn("Combined view", block)

    def test_controller_remains_presentation_only_and_supports_both_sources(self):
        source = CTRL.read_text(encoding="utf-8")
        self.assertIn('id: "combined"', source)
        self.assertIn('id: "volume-derived"', source)
        self.assertIn('id: "segmentation-derived"', source)
        self.assertNotIn("fetch(", source.lower())
        self.assertNotIn("/api/", source.lower())

    def test_300_hu_and_later_phase_boundaries_remain_intact(self):
        index = INDEX.read_text(encoding="utf-8")
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn('value="300"', index)
        self.assertIn("Bone baseline: 300 HU when in range", index)
        self.assertIn("6D2D", doc)
        self.assertIn("Phase 6E", doc)
        self.assertIn("Phase 6F", doc)
        self.assertIn("Clinical validation is not claimed", doc)


if __name__ == "__main__":
    unittest.main()
