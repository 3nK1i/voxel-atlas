from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
SEGMENTATION_VIEWER = ROOT / "web/js/segmentation-surface-viewer.js"
VOLUME_VIEWER = ROOT / "web/js/volume-surface-viewer.js"
DOC = ROOT / "docs/phase_history/PHASE6D2B_VOLUME_SURFACE_TRANSITIONS.md"


def function_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


class Phase6D2BVolumeSurfaceTransitionTests(unittest.TestCase):
    def test_workspace_exposes_volume_and_surface_modes_with_capability_gating(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="reconstructionVisualizationPanel"', index)
        self.assertIn('data-reconstruction-mode="volume"', index)
        self.assertIn('data-reconstruction-mode="surface"', index)
        self.assertIn('data-reconstruction-mode="combined"', index)
        # Phase 6I-B: Combined is no longer gated on an already resident CT mesh.
        # The mode controller still rejects unsupported requests at runtime.
        self.assertIn('data-reconstruction-mode="combined"', index)
        self.assertIn("Volume", index)
        self.assertIn("Surface", index)
        self.assertIn("Combined", index)
        self.assertIn("phase6d2b-r1", index)

    def test_app_wires_controller_to_non_destructive_layer_visibility(self):
        app = APP.read_text(encoding="utf-8")
        self.assertIn("ReconstructionVisualizationModeController", app)
        self.assertIn("applyReconstructionVisualizationSnapshot", app)
        self.assertIn("syncReconstructionVisualizationResources", app)
        self.assertIn('setPresentationVisible(snapshot.visibility.surfaceSources["volume-derived"])', app)
        self.assertIn('setPresentationVisible(snapshot.visibility.surfaceSources["segmentation-derived"])', app)
        self.assertIn("requestReconstructionVisualizationMode", app)

    def test_mode_switch_does_not_build_or_clear_surface_geometry(self):
        app = APP.read_text(encoding="utf-8")
        block = function_block(
            app,
            "function requestReconstructionVisualizationMode(",
            "function setVolumeAvailability(",
        )
        lowered = block.lower()
        self.assertNotIn(".build(", lowered)
        self.assertNotIn("clearsurface", lowered)
        self.assertNotIn(".clear(", lowered)
        self.assertNotIn("fetch(", lowered)
        self.assertNotIn("segmentation-workflow", lowered)

    def test_volume_surface_layer_has_non_destructive_presentation_visibility(self):
        source = VOLUME_VIEWER.read_text(encoding="utf-8")
        block = function_block(source, "  setPresentationVisible(", "  async build(")
        self.assertIn("this.group.visible", block)
        self.assertNotIn("_disposeCurrent", block)
        self.assertNotIn("clearSurface", block)
        self.assertNotIn("abort", block.lower())

    def test_segmentation_surface_layer_visibility_does_not_abort_pending_work(self):
        source = SEGMENTATION_VIEWER.read_text(encoding="utf-8")
        block = function_block(source, "  setPresentationVisible(", "  _makeMaterial(")
        self.assertIn("this.group.visible", block)
        self.assertNotIn("_abortPending", block)
        self.assertNotIn("clear()", block)
        self.assertNotIn("dispose", block.lower())

    def test_volume_opacity_remains_part_of_volume_visibility_policy(self):
        app = APP.read_text(encoding="utf-8")
        block = function_block(app, "function applyVolumeVisibility()", "function updateVolumeBounds()")
        self.assertIn("state.opacity > 0.001", block)
        self.assertIn("snapshot.visibility.volume", block)
        self.assertIn("modeAllowsVolume", block)

    def test_building_surface_does_not_implicitly_change_visualization_mode(self):
        app = APP.read_text(encoding="utf-8")
        block = function_block(app, "async function requestVolumeSurfaceBuild()", "function clearVolumeDerivedSurface()")
        self.assertIn("volumeSurfaceLayer.build(level)", block)
        self.assertIn("syncReconstructionVisualizationResources()", block)
        self.assertNotIn('requestMode("surface")', block)
        self.assertNotIn("applyVolumeVisibility()", block)

    def test_phase6d1_300_hu_baseline_and_later_phase_boundaries_remain_intact(self):
        index = INDEX.read_text(encoding="utf-8")
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn('value="300"', index)
        self.assertIn("Bone baseline: 300 HU when in range", index)
        self.assertIn("6D2C", doc)
        self.assertIn("Combined", doc)
        self.assertIn("disabled", doc.lower())
        self.assertIn("Phase 6E", doc)
        self.assertIn("Phase 6F", doc)
        self.assertIn("Clinical validation is not claimed", doc)


if __name__ == "__main__":
    unittest.main()
