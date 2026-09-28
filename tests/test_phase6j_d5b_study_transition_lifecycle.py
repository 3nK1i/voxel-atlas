"""Phase 6J-D5B: study-transition and stale-async browser lifecycle contracts."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
VOLUME_VIEWER = ROOT / "web/js/volume-surface-viewer.js"
SEGMENTATION_VIEWER = ROOT / "web/js/segmentation-surface-viewer.js"
B1_CHECK = ROOT / "scripts/check_phase6j_b1_mri_workflow.mjs"
B2B_CHECK = ROOT / "scripts/check_phase6j_b2b_mri_study_workflows.mjs"


def block(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    finish = text.index(end, begin)
    return text[begin:finish]


class StudyTransitionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.app = APP.read_text(encoding="utf-8")

    def test_apply_study_invalidates_async_state_before_binding_new_study(self):
        body = block(self.app, "function applyStudy(study) {", "async function ensureCanonicalVolume(study) {")
        self.assertIn("previousStudyId !== nextStudyId", body)
        self.assertIn("previousSeriesUid !== nextSeriesUid", body)
        self.assertIn("previousVolumeRevision !== nextVolumeRevision", body)
        invalidate = body.index("invalidateStudyScopedAsyncState();")
        assign = body.index("state.study = study;")
        self.assertLess(invalidate, assign)
        self.assertIn("setMprVolumeState(study);", body)

    def test_invalidator_detaches_all_study_scoped_async_owners_without_ml_execution(self):
        body = block(
            self.app,
            "function invalidateStudyScopedAsyncState() {",
            "function syncSegmentation3dAppearance()",
        )
        for required in (
            "studyLifecycleGeneration += 1",
            "mprAbortController?.abort()",
            "mprRenderGeneration += 1",
            "mprDescriptorPromise = null",
            "segmentationOverlayDescriptorPromise = null",
            "segmentationSurfaceDescriptorPromise = null",
            "volumeSurfaceDescriptorPromise = null",
            "volumeBuildPromise = null",
            "automaticSurfaceMode?.invalidate()",
            "segmentationSurfaceGate?.invalidate()",
            "autoSurfaceBuildPromise = null",
            "autoSurfaceBuildStudyId = null",
        ):
            with self.subTest(required=required):
                self.assertIn(required, body)
        self.assertNotIn("fetch(", body)
        self.assertNotIn("requestSegmentationStart", body)
        self.assertNotIn("/segmentation-workflow/start", body)

    def test_descriptor_and_mpr_completions_are_lifecycle_bound(self):
        for start, end in (
            ("async function refreshVolumeSurfaceDescriptor()", "async function requestVolumeSurfaceBuild()"),
            ("async function refreshSegmentationSurfaceDescriptor(labelMapId)", "function setSegmentationOverlayAvailability(descriptor)"),
            ("async function refreshSegmentationOverlayDescriptor(labelMapId)", "async function renderSegmentationOverlayPlane("),
            ("async function ensureMprReady()", "function setMprCrosshairFromPointer("),
        ):
            with self.subTest(start=start):
                body = block(self.app, start, end)
                self.assertIn("captureStudyLifecycle()", body)
                self.assertIn("studyLifecycleMatches(lifecycle)", body)
        self.assertIn(
            "if (mprDescriptorPromise === request) mprDescriptorPromise = null",
            self.app,
        )
        self.assertIn(
            "if (segmentationOverlayDescriptorPromise === request) segmentationOverlayDescriptorPromise = null",
            self.app,
        )
        self.assertIn(
            "if (segmentationSurfaceDescriptorPromise === request) segmentationSurfaceDescriptorPromise = null",
            self.app,
        )

    def test_volume_build_and_restore_cannot_reactivate_superseded_study(self):
        build = block(
            self.app,
            "async function ensureCanonicalVolume(study) {",
            "async function restoreReadyPatientVolume(message) {",
        )
        self.assertIn("const studyId = study.study_id", build)
        self.assertIn("let lifecycle = captureStudyLifecycle()", build)
        self.assertIn("payload.study.study_id !== studyId", build)
        self.assertIn("Patient volume construction study binding is invalid", build)
        self.assertIn("lifecycle = captureStudyLifecycle()", build)
        self.assertGreaterEqual(build.count("studyLifecycleMatches(lifecycle)"), 4)
        self.assertIn("if (volumeBuildPromise === request) volumeBuildPromise = null", build)

        restore = block(
            self.app,
            "async function restoreReadyPatientVolume(message) {",
            "async function refreshLatestStudy() {",
        )
        self.assertIn("const lifecycle = captureStudyLifecycle()", restore)
        self.assertGreaterEqual(restore.count("studyLifecycleMatches(lifecycle)"), 2)

        latest = block(
            self.app,
            "async function refreshLatestStudy() {",
            "async function uploadDicomFiles(files) {",
        )
        self.assertIn("const lifecycle = captureStudyLifecycle()", latest)
        self.assertIn("if (!studyLifecycleMatches(lifecycle)) return;", latest)

    def test_rendering_and_surface_layers_keep_abort_generation_guards(self):
        foundation = block(
            self.app,
            "async function ensureVolumeRenderingFoundation() {",
            "const MPR_AXIS_INDEX",
        )
        self.assertIn("const lifecycle = captureStudyLifecycle()", foundation)
        self.assertIn("studyLifecycleMatches(lifecycle)", foundation)
        self.assertIn("volumeRenderingTask !== task", foundation)

        volume = VOLUME_VIEWER.read_text(encoding="utf-8")
        self.assertIn("this.generation += 1", volume)
        self.assertIn("this.controller?.abort()", volume)
        self.assertIn("generation !== this.generation || controller.signal.aborted", volume)

        segmentation = SEGMENTATION_VIEWER.read_text(encoding="utf-8")
        self.assertIn("this.generation += 1", segmentation)
        self.assertIn("controller.abort()", segmentation)
        self.assertIn("generation !== this.generation || controller.signal.aborted", segmentation)

    def test_cache_token_and_legacy_mri_harnesses_accept_d5b_suffix(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertRegex(index, r"phase6j-d45c-r2-phase6j-d5b-r1(?:-phase6j-d5c-r\d+)?")
        self.assertIn("phase6j-d5b-r\\d+", B1_CHECK.read_text(encoding="utf-8"))
        self.assertIn("phase6j-d5c-r\\d+", B1_CHECK.read_text(encoding="utf-8"))
        self.assertIn("phase6j-d5b-r\\d+", B2B_CHECK.read_text(encoding="utf-8"))
        self.assertIn("phase6j-d5c-r\\d+", B2B_CHECK.read_text(encoding="utf-8"))

    def test_d5b_does_not_change_scientific_or_inference_contract(self):
        lifecycle = block(
            self.app,
            "function invalidateStudyScopedAsyncState() {",
            "function syncSegmentation3dAppearance()",
        )
        self.assertNotIn("isovalue", lifecycle.lower())
        self.assertNotIn("normalization", lifecycle.lower())
        self.assertNotIn("requestSegmentationStart", lifecycle)
        self.assertIn("Switching modes never starts segmentation", self.app)


if __name__ == "__main__":
    unittest.main()
