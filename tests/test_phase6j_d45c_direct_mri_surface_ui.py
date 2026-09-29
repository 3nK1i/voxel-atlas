"""Phase 6J-D4.5C: modality-aware Direct MR surface UI contracts."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DirectMRSurfaceUIContractTests(unittest.TestCase):
    def setUp(self):
        self.backend = (ROOT / "backend/voxelatlas/volume_surfaces.py").read_text(encoding="utf-8")
        self.index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")
        self.help = (ROOT / "web/js/parameter-help.js").read_text(encoding="utf-8")
        self.css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

    def test_mr_backend_is_now_ui_available_without_changing_ct_contract(self):
        self.assertIn('available = bool(backend_available)', self.backend)
        self.assertIn('"ui_activation": "enabled" if backend_available else "unavailable"', self.backend)
        self.assertIn('DEFAULT_CT_BONE_ISOVALUE_HU = 300.0', self.backend)
        self.assertIn('MRI_SURFACE_INTENSITY_UNITS = "normalized_signal"', self.backend)
        self.assertIn('"segmentation_required": False', self.backend)

    def test_direct_volume_surface_ui_is_modality_aware(self):
        for identifier in (
            'volumeSurfaceSourceLabel', 'volumeSurfaceSourceBadge',
            'volumeSurfaceIsovalueTitle', 'volumeSurfaceIsovalueHint',
            'volumeSurfaceIsovalueUnits', 'volumeSurfaceRegionControl', 'volumeSurfaceRegionTitle',
            'volumeSurfaceContractNote', 'reconstructionSurfaceSourceNote',
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(f'id="{identifier}"', self.index)
        self.assertIn('descriptor?.source_modality === "MR" ? "Direct MR" : "Direct CT"', self.app)
        self.assertIn('"Normalized MRI isovalue"', self.app)
        self.assertIn('"Relative signal after robust 2–98% normalization"', self.app)
        self.assertIn('"Canonical MRI intensity-derived surface', self.app)
        self.assertIn('volumeSurfaceIsovalue.step = "0.01"', self.app)
        self.assertIn('volumeSurfaceIsovalue.step = "10"', self.app)
        self.assertIn('volumeSurfaceRegionTitle.textContent = `${label} visibility`', self.app)

    def test_mr_uses_surface_normalized_range_and_ct_regions_stay_ct_only(self):
        self.assertIn('descriptor.surface_isovalue_range', self.app)
        self.assertIn('this.descriptor.surface_isovalue_range', self.viewer)
        self.assertIn('units !== directSurfaceUnits(this.descriptor)', self.viewer)
        self.assertIn('this.descriptor?.source_modality !== "CT"', self.viewer)
        self.assertIn('state.volumeSurface.descriptor?.source_modality === "CT"', self.app)
        self.assertIn('volumeSurfaceRegionControl.hidden = true', self.app)
        self.assertIn('volumeSurfaceRegionStatus.hidden = true', self.app)
        self.assertIn('.volume-surface-region-control[hidden]', self.css)
        self.assertIn('#volumeSurfaceRegionStatus[hidden]', self.css)
        self.assertIn('display: none !important;', self.css)

    def test_surface_and_combined_prepare_direct_mr_without_segmentation(self):
        self.assertIn('canPrepareAutomaticDirectVolumeSurface', self.app)
        self.assertIn('ensureAutomaticDirectVolumeSurface', self.app)
        self.assertIn('directVolumeSurfaceLabel()', self.app)
        self.assertIn('state.reconstructionVisualization.surfaceSourceSelection["volume-derived"]', self.app)
        self.assertIn('volumeSurfaceLayer.build(level)', self.app)
        self.assertNotIn('Direct MR" : "Segmentation"', self.app)

    def test_volume_surface_viewer_reports_modality_appropriate_identity(self):
        self.assertIn('function directSurfaceLabel(descriptor)', self.viewer)
        self.assertIn('function formatIsovalue(descriptor, value)', self.viewer)
        self.assertIn('"normalized signal" : "HU"', self.viewer)
        self.assertIn('sourceModality: this.descriptor.source_modality', self.viewer)
        self.assertIn('intensityUnits: units', self.viewer)

    def test_volume_surface_source_remains_nonsemantic(self):
        self.assertIn('non-semantic visualization', self.app)
        self.assertIn('no segmentation required', self.app)
        self.assertNotIn('Direct MR Brain', self.index + self.app + self.viewer)
        self.assertNotIn('MRI tissue class', self.index + self.app + self.viewer)

    def test_mode_question_mark_controls_are_removed(self):
        panel = self.index.split('id="reconstructionPanel"', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('va-reconstruction-mode-help-row', panel)
        self.assertNotIn('data-help-reconstruction-mode', panel)
        self.assertNotIn('"mode-volume": [', self.help)
        self.assertNotIn('"mode-surface": [', self.help)
        self.assertNotIn('"mode-combined": [', self.help)
        self.assertNotIn('.va-reconstruction-mode-help-row > .va-parameter-help', self.css)
        for mode in ('volume', 'surface', 'combined'):
            self.assertEqual(panel.count(f'data-reconstruction-mode="{mode}"'), 1)


if __name__ == "__main__":
    unittest.main()
