"""Phase 6J-D5C: same-study Direct/Semantic coexistence and mode lifecycle."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
MODE = ROOT / "web/js/reconstruction-visualization-mode.js"
VOLUME_VIEWER = ROOT / "web/js/volume-surface-viewer.js"
SEGMENTATION_VIEWER = ROOT / "web/js/segmentation-surface-viewer.js"
B1 = ROOT / "scripts/check_phase6j_b1_mri_workflow.mjs"
B2B = ROOT / "scripts/check_phase6j_b2b_mri_study_workflows.mjs"
D5B_CHECK = ROOT / "scripts/check_phase6j_d5b_study_lifecycle.mjs"
D5B_TEST = ROOT / "tests/test_phase6j_d5b_study_transition_lifecycle.py"


def block(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    finish = text.index(end, begin)
    return text[begin:finish]


class SameStudySurfaceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.app = APP.read_text(encoding="utf-8")

    def test_selecting_nonresident_direct_source_in_active_surface_mode_prepares_direct_only(self):
        body = block(
            self.app,
            "function requestReconstructionSurfaceSourceSelection(sourceId, selected) {",
            "function setVolumeAvailability(available) {",
        )
        self.assertIn('sourceId === "volume-derived"', body)
        self.assertIn("selected", body)
        self.assertIn('result?.mode !== "volume"', body)
        self.assertIn("!volumeSurfaceLayer.current", body)
        self.assertIn("canPrepareAutomaticDirectVolumeSurface(result)", body)
        self.assertIn("void ensureAutomaticDirectVolumeSurface();", body)
        self.assertNotIn("requestSegmentationStart", body)
        self.assertNotIn("segmentation-workflow/start", body)

    def test_volume_mode_direct_selection_remains_intent_only(self):
        body = block(
            self.app,
            "function requestReconstructionSurfaceSourceSelection(sourceId, selected) {",
            "function setVolumeAvailability(available) {",
        )
        # Direct-source selection is allowed to prepare only while Surface/Combined is already active.
        self.assertRegex(
            body,
            r'sourceId === "volume-derived"[\s\S]*?result\?\.mode !== "volume"[\s\S]*?ensureAutomaticDirectVolumeSurface\(\)',
        )

    def test_mode_changes_remain_presentation_only_and_resident_geometry_is_reused(self):
        body = block(
            self.app,
            "function requestReconstructionVisualizationMode(modeId) {",
            "function ensureAutomaticSelectedSurface() {",
        )
        self.assertIn("!volumeSurfaceLayer.current", body)
        self.assertIn("canPrepareAutomaticDirectVolumeSurface(snapshot)", body)
        self.assertIn("canPrepareAutomaticSegmentationSurface()", body)
        self.assertNotIn("requestSegmentationStart", body)
        self.assertNotIn("clearVolumeDerivedSurface", body)
        self.assertNotIn("segmentationSurfaceLayer.clear", body)

    def test_visibility_is_non_destructive_for_both_resident_surface_sources(self):
        volume = VOLUME_VIEWER.read_text(encoding="utf-8")
        segmentation = SEGMENTATION_VIEWER.read_text(encoding="utf-8")
        self.assertIn("setPresentationVisible(visible)", volume)
        self.assertIn("setPresentationVisible(visible)", segmentation)
        self.assertNotIn("clearSurface()", block(volume, "setPresentationVisible(visible)", "setPresentationProfile(profileId)"))
        self.assertNotIn("this.clear()", block(segmentation, "setPresentationVisible(visible)", "setPresentationProfile(profileId)"))

    def test_controller_keeps_selected_resident_sources_distinct_from_availability(self):
        mode = MODE.read_text(encoding="utf-8")
        for token in (
            "available: false, resident: false, selected: false",
            "state.selected && state.resident",
            "selectedResidentSurfaceSources",
            "residentSurfaceSources",
        ):
            with self.subTest(token=token):
                self.assertIn(token, mode)

    def test_cache_token_and_legacy_harnesses_accept_d5c_suffix(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn("phase6j-d5b-r1-phase6j-d5c-r1", index)
        self.assertIn("phase6j-d5c-r\\d+", B1.read_text(encoding="utf-8"))
        self.assertIn("phase6j-d5c-r\\d+", B2B.read_text(encoding="utf-8"))
        self.assertIn("phase6j-d5c-r\\d+", D5B_CHECK.read_text(encoding="utf-8"))
        self.assertIn("phase6j-d5c-r\\d+", D5B_TEST.read_text(encoding="utf-8"))

    def test_d5c_does_not_change_scientific_or_inference_contracts(self):
        body = block(
            self.app,
            "function requestReconstructionSurfaceSourceSelection(sourceId, selected) {",
            "function setVolumeAvailability(available) {",
        )
        self.assertNotIn("normalization", body.lower())
        self.assertNotIn("patient_lps", body.lower())
        self.assertNotIn("isovalue =", body.lower())
        self.assertNotIn("requestSegmentationStart", body)


if __name__ == "__main__":
    unittest.main()
