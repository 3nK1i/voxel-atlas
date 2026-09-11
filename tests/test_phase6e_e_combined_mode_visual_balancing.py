from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BALANCE = ROOT / "web/js/reconstruction-combined-presentation.js"
APP = ROOT / "web/js/app.js"
VOLUME_SURFACE = ROOT / "web/js/volume-surface-viewer.js"
SEGMENTATION_SURFACE = ROOT / "web/js/segmentation-surface-viewer.js"
INDEX = ROOT / "web/index.html"
DOC = ROOT / "docs/phase_history/PHASE6E_E_COMBINED_MODE_VISUAL_BALANCING.md"


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


class Phase6EECombinedModeVisualBalancingTests(unittest.TestCase):
    def test_combined_balance_policy_exists_and_is_presentation_only(self):
        source = BALANCE.read_text(encoding="utf-8")
        self.assertIn('fidelity', source)
        self.assertIn('presentation', source)
        self.assertIn('volumeOpacityMultiplier', source)
        self.assertIn('directCtSurfaceOpacity', source)
        self.assertIn('segmentationOpacityMultiplier: 1', source)
        for token in ('fetch(', '/api/', 'geometry.', 'marching', 'applyMatrix4', 'setAttribute'):
            self.assertNotIn(token, source)

    def test_combined_mode_reduces_volume_and_direct_ct_but_preserves_user_state(self):
        source = BALANCE.read_text(encoding="utf-8")
        self.assertIn('userVolumeOpacity', source)
        self.assertIn('effectiveVolumeOpacity', source)
        self.assertIn('normalizedMode === "combined"', source)
        self.assertIn('directCtSurfaceOpacity: 1', source)
        self.assertIn('segmentationOpacityMultiplier: 1', source)

    def test_app_applies_balance_on_mode_profile_and_user_opacity_changes(self):
        app = APP.read_text(encoding="utf-8")
        self.assertIn('resolveCombinedPresentationBalance', app)
        self.assertIn('function applyCombinedPresentationBalance(', app)
        self.assertIn('volumeRayMarcher.setOpacity(state.opacity);', app)
        self.assertIn('volumeRayMarcher.setOpacity(plan.effectiveVolumeOpacity)', app)
        self.assertIn('volumeSurfaceLayer?.setPresentationOpacity(plan.directCtSurfaceOpacity)', app)
        profile = block(
            app,
            'function applyReconstructionPresentationProfileSnapshot(',
            'function requestReconstructionPresentationProfile(',
        )
        self.assertIn('applyCombinedPresentationBalance', profile)
        mode = block(
            app,
            'function applyReconstructionVisualizationSnapshot(',
            'function syncReconstructionVisualizationResources()',
        )
        self.assertIn('applyCombinedPresentationBalance', mode)

    def test_direct_ct_layer_has_non_destructive_presentation_opacity(self):
        source = VOLUME_SURFACE.read_text(encoding="utf-8")
        self.assertIn('this.presentationOpacity = 1', source)
        self.assertIn('setPresentationOpacity(opacity)', source)
        method = block(source, '  _applyPresentationOpacity() {', '  async build(isovalue) {')
        self.assertIn('material.opacity', method)
        self.assertIn('material.transparent', method)
        self.assertIn('material.depthWrite', method)
        for token in ('fetch(', '.build(', '_disposeCurrent', 'geometry.'):
            self.assertNotIn(token, method)

    def test_segmentation_semantic_color_and_opacity_remain_authoritative(self):
        source = SEGMENTATION_SURFACE.read_text(encoding="utf-8")
        self.assertIn('applySegmentationSurfaceMaterialProfile', source)
        self.assertNotIn('setPresentationOpacityMultiplier', source)
        shared = (ROOT / 'web/js/reconstruction-surface-presentation.js').read_text(encoding='utf-8')
        self.assertIn('material.opacity = opacity', shared)
        self.assertIn('material.color.set(structure?.colorHex || "#ffffff")', shared)

    def test_combined_balance_does_not_change_geometry_extraction_or_300_hu_default(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn('value="300"', index)
        self.assertIn('Bone baseline: 300 HU when in range', index)

    def test_cache_keys_advance_for_6e_e(self):
        index = INDEX.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        self.assertIn('phase6e-e-r1', index)
        self.assertIn('reconstruction-combined-presentation.js?v=phase6e-e-r1', app)
        self.assertIn('volume-surface-viewer.js?v=phase6d2b-r1-phase6e-b-r1-phase6e-d-r1-phase6e-e-r1', app)

    def test_document_records_combined_only_boundary(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn('fd74ea2161ea19388c7503be97b055d9d31c896a', doc)
        self.assertIn('Combined', doc)
        self.assertIn('segmentation', doc.lower())
        self.assertIn('opacity', doc.lower())
        self.assertIn('geometry', doc.lower())
        self.assertIn('300 HU', doc)
        self.assertIn('6E-F', doc)
        self.assertIn('Clinical validation is not claimed', doc)


if __name__ == '__main__':
    unittest.main()
