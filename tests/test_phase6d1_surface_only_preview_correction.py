from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "web" / "js" / "app.js"
INDEX_PATH = ROOT / "web" / "index.html"
DOC_PATH = ROOT / "docs" / "phase_history" / "PHASE6D1_VOLUME_DERIVED_SURFACES.md"


def function_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


class Phase6D1SurfaceOnlyPreviewCorrectionTests(unittest.TestCase):
    def test_direct_volume_visibility_excludes_active_volume_surface_preview(self):
        app = APP_PATH.read_text(encoding="utf-8")
        block = function_block(app, "function applyVolumeVisibility()", "function updateVolumeBounds()")

        self.assertIn("volumeLayer.root.visible = volumeLayer.available && state.opacity > 0.001;", block)
        self.assertIn("if (volumeSurfaceLayer?.current) volumeLayer.root.visible = false;", block)

    def test_successful_surface_build_hides_volume_only_after_build_resolves(self):
        app = APP_PATH.read_text(encoding="utf-8")
        block = function_block(app, "async function requestVolumeSurfaceBuild()", "function clearVolumeDerivedSurface()")

        build_index = block.index("await volumeSurfaceLayer.build(level)")
        visibility_index = block.index("applyVolumeVisibility()")
        self.assertGreater(visibility_index, build_index)

    def test_remove_surface_restores_direct_volume_visibility_policy(self):
        app = APP_PATH.read_text(encoding="utf-8")
        block = function_block(app, "function clearVolumeDerivedSurface()", "function clearSegmentationWorkflowPoll()")

        clear_index = block.index("volumeSurfaceLayer.clearSurface()")
        visibility_index = block.index("applyVolumeVisibility()")
        self.assertGreater(visibility_index, clear_index)

    def test_phase6d1_stays_surface_only_preview_not_phase6d2_modes(self):
        index = INDEX_PATH.read_text(encoding="utf-8")
        doc = DOC_PATH.read_text(encoding="utf-8")

        self.assertNotIn("Volume / Surface / Combined", index)
        self.assertIn("phase6d1-r2", index)
        self.assertIn("surface-only preview", doc.lower())
        self.assertIn("is temporarily hidden only after a successful surface build", doc.lower())
        self.assertIn("Phase 6D2", doc)
        self.assertIn("not enabled", doc.lower())


if __name__ == "__main__":
    unittest.main()
