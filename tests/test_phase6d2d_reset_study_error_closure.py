from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
CSS = ROOT / "web/css/styles.css"
DOC = ROOT / "docs/phase_history/PHASE6D2D_RESET_STUDY_ERROR_CLOSURE.md"


def function_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


class Phase6D2DResetStudyErrorClosureTests(unittest.TestCase):
    def test_reconstruction_modes_are_left_sidebar_cards_not_right_sidebar_switch(self):
        index = INDEX.read_text(encoding="utf-8")
        left_start = index.index('id="reconstructionPanel"')
        left_end = index.index('</section>', left_start)
        left = index[left_start:left_end]
        right_start = index.index('id="reconstructionVisualizationPanel"')
        right_end = index.index('</section>', right_start)
        right = index[right_start:right_end]

        self.assertEqual(left.count('data-reconstruction-mode='), 3)
        self.assertIn('data-reconstruction-mode="volume"', left)
        self.assertIn('data-reconstruction-mode="surface"', left)
        self.assertIn('data-reconstruction-mode="combined"', left)
        self.assertIn('class="status-row reconstruction-mode-card"', left)
        self.assertIn('reconstruction-mode-icon-volume', left)
        self.assertIn('reconstruction-mode-icon-surface', left)
        self.assertIn('reconstruction-mode-icon-combined', left)
        self.assertNotIn('data-reconstruction-mode=', right)
        self.assertNotIn('reconstruction-mode-switch', right)
        self.assertIn('data-reconstruction-surface-source="volume-derived"', right)
        self.assertIn('data-reconstruction-surface-source="segmentation-derived"', right)

    def test_green_check_is_active_mode_semantics_not_generic_readiness(self):
        app = APP.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        block = function_block(
            app,
            "function applyReconstructionVisualizationSnapshot(",
            "function syncReconstructionVisualizationResources()",
        )
        self.assertIn('button.dataset.active = String(snapshot.mode === modeId && available)', block)
        self.assertIn('.reconstruction-mode-card[data-active="true"] .readiness-check', css)
        self.assertIn('.reconstruction-mode-card[data-active="false"] .readiness-check', css)
        self.assertIn('.reconstruction-mode-card[data-active="false"] .readiness-check path', css)

    def test_left_cards_report_surface_and_combined_availability_truthfully(self):
        index = INDEX.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        self.assertIn('id="surfaceModeStatusText"', index)
        self.assertIn('id="combinedModeStatusText"', index)
        block = function_block(
            app,
            "function applyReconstructionVisualizationSnapshot(",
            "function syncReconstructionVisualizationResources()",
        )
        self.assertIn("surfaceModeStatusText", block)
        self.assertIn("combinedModeStatusText", block)
        # Direct-volume preparation is modality-aware: CT and MR share the same
        # presentation path while the helper resolves the active source label.
        self.assertIn("directVolumeSurfaceLabel()", block)
        self.assertIn("`Select to prepare ${directVolumeSurfaceLabel()}`", block)
        self.assertIn("Volume + selected surface ready", block)

    def test_workspace_reset_returns_to_volume_without_destroying_or_building_geometry(self):
        app = APP.read_text(encoding="utf-8")
        block = function_block(app, "function resetWorkspace()", "function preferredTheme()")
        self.assertIn('requestReconstructionVisualizationMode("volume")', block)
        lowered = block.lower()
        self.assertNotIn("fetch(", lowered)
        self.assertNotIn(".build(", lowered)
        self.assertNotIn("clearsurface", lowered)
        self.assertNotIn("segmentation-workflow", lowered)

    def test_patient_volume_clear_resets_mode_and_source_preferences_for_new_study(self):
        app = APP.read_text(encoding="utf-8")
        self.assertIn("DEFAULT_RECONSTRUCTION_SURFACE_SOURCE_SELECTION", app)
        helper = function_block(
            app,
            "function resetReconstructionVisualizationForStudy()",
            "function clearPatientVolumeRendering()",
        )
        self.assertIn('DEFAULT_RECONSTRUCTION_SURFACE_SOURCE_SELECTION', helper)
        self.assertIn('"volume-derived": true', app)
        self.assertIn('"segmentation-derived": true', app)
        self.assertIn("reconstructionVisualizationController?.reset()", helper)
        clear = function_block(
            app,
            "function clearPatientVolumeRendering()",
            "async function activatePatientVolumeRendering(",
        )
        self.assertIn("resetReconstructionVisualizationForStudy()", clear)

    def test_surface_failure_and_remove_paths_do_not_force_invalid_modes_or_rebuild(self):
        app = APP.read_text(encoding="utf-8")
        build = function_block(
            app,
            "async function requestVolumeSurfaceBuild()",
            "function clearVolumeDerivedSurface()",
        )
        clear = function_block(
            app,
            "function clearVolumeDerivedSurface()",
            "function clearSegmentationWorkflowPoll()",
        )
        self.assertIn("syncReconstructionVisualizationResources()", build)
        self.assertNotIn("requestReconstructionVisualizationMode", build)
        self.assertIn("syncReconstructionVisualizationResources()", clear)
        self.assertNotIn("requestReconstructionVisualizationMode", clear)
        self.assertNotIn("fetch(", clear.lower())

    def test_right_panel_explains_surface_source_scope_after_mode_relocation(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn("Surface source selections apply in Surface and Combined modes", index)
        self.assertIn("resident geometry", index)

    def test_6d2d_document_closes_phase6d2_without_entering_6e_or_6f(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("e96f0138bbfe55963b7069680d8ead3d641d64d7", doc)
        self.assertIn("6D2A", doc)
        self.assertIn("6D2B", doc)
        self.assertIn("6D2C", doc)
        self.assertIn("Volume", doc)
        self.assertIn("Surface", doc)
        self.assertIn("Combined", doc)
        self.assertIn("study change", doc.lower())
        self.assertIn("failed", doc.lower())
        self.assertIn("Phase 6E", doc)
        self.assertIn("Phase 6F", doc)
        self.assertIn("Clinical validation is not claimed", doc)


if __name__ == "__main__":
    unittest.main()
