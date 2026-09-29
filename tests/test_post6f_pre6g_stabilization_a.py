from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Post6FPre6GStabilizationATests(unittest.TestCase):
    def test_right_sidebar_starts_with_volume_rendering_and_quality_precedes_preset(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        right = html.split('<aside class="right-panel panel"', 1)[1].split('</aside>', 1)[0]
        order = [
            'id="volumeRenderingPanel"',
            'id="reconstructionVisualizationPanel"',
            'id="volumeSurfacePanel"',
            'id="segmentationWorkflowPanel"',
            'id="segmentationOverlayPanel"',
            'id="segmentationSurfacePanel"',
            'id="segmentationStructurePanel"',
            'id="directionalCutPanel"',
            'id="segmentationCorrectionPanel"',
        ]
        positions = [right.index(marker) for marker in order]
        self.assertEqual(positions, sorted(positions))
        volume = right[right.index('id="volumeRenderingPanel"'):right.index('id="reconstructionVisualizationPanel"')]
        self.assertLess(volume.index('id="renderQualityPolicy"'), volume.index('id="transferPresetSelect"'))
        self.assertLess(volume.index('id="transferPresetSelect"'), volume.index('id="renderingModeSelect"'))
        self.assertLess(volume.index('id="renderingModeSelect"'), volume.index('id="transferWindowCenter"'))

    def test_direct_ct_surface_actions_use_shared_sidebar_action_system(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('id="volumeSurfaceBuild" class="sidebar-action-button is-primary', html)
        self.assertIn('id="volumeSurfaceClear" class="sidebar-action-button is-secondary', html)
        self.assertIn('.sidebar-action-button', css)
        self.assertIn('.sidebar-action-button.is-primary', css)
        self.assertIn('.sidebar-action-button.is-secondary', css)
        self.assertIn('>Remove Surface</button>', html)
        self.assertIn('id="resetButton" class="sidebar-action-button is-secondary"', html)
        self.assertIn('id="autoRotateButton" class="sidebar-action-button is-secondary"', html)

    def test_ready_study_restoration_prestarts_volume_rendering_before_mpr_wait(self) -> None:
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        restore = app.split("async function restoreReadyPatientVolume", 1)[1].split(
            "async function refreshLatestStudy", 1
        )[0]
        start = restore.index("void ensureVolumeRenderingFoundation();")
        mpr = restore.index("await ensureMprReady();")
        finish = restore.index("await ensureVolumeRenderingFoundation();")
        self.assertLess(start, mpr)
        self.assertLess(mpr, finish)

        build = app.split("async function ensureCanonicalVolume", 1)[1].split(
            "async function restoreReadyPatientVolume", 1
        )[0]
        start = build.index("void ensureVolumeRenderingFoundation();")
        mpr = build.index("await ensureMprReady();")
        finish = build.index("await ensureVolumeRenderingFoundation();")
        self.assertLess(start, mpr)
        self.assertLess(mpr, finish)

    def test_direct_ct_diagnostic_is_read_only_and_component_based(self) -> None:
        script = (ROOT / "scripts" / "diagnose_post6f_direct_ct_surface.py").read_text(encoding="utf-8")
        for marker in (
            "CANONICAL_VOLUME_MUTATION=NO",
            "ISOVALUE_COMPONENTS",
            "BODY_SUPPORT_COMPONENTS",
            "touches_boundary",
            "flatness_ratio",
            "scipy.ndimage",
        ):
            self.assertIn(marker, script)
        self.assertNotIn("np.save(", script)
        self.assertNotIn("write_bytes(", script)

    def test_loading_diagnostic_profiles_existing_pipeline_without_mutation(self) -> None:
        script = (ROOT / "scripts" / "diagnose_post6f_study_loading.py").read_text(encoding="utf-8")
        for marker in (
            'timed("LATEST_STUDY_LOOKUP"',
            'timed("MPR_DESCRIPTOR"',
            'timed("VOLUME_RENDERING_INSPECT"',
            "VOLUME_RENDERING_PREPARE_MS",
            'timed("SAMPLE_PAYLOAD_VERIFY"',
            "SAMPLE_PAYLOAD_VERIFY_MS=SKIPPED_NON_SAMPLE",
            "DIAGNOSTIC_MUTATION=NO",
        ):
            self.assertIn(marker, script)
        self.assertNotIn("activate_study(", script)
        self.assertNotIn("build_latest(", script)


if __name__ == "__main__":
    unittest.main()
