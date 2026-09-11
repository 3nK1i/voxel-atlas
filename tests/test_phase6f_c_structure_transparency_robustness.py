from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase6FCStructureTransparencyRobustnessTests(unittest.TestCase):
    def test_surface_material_policy_has_no_near_opaque_magic_threshold(self):
        source = (ROOT / 'web/js/reconstruction-surface-presentation.js').read_text()
        self.assertIn('resolveSegmentationSurfaceOpacityPolicy', source)
        self.assertNotIn('opacity >= 0.98', source)
        self.assertIn('const fullyOpaque = opacity >= 1;', source)
        self.assertIn('transparent: true,', source)
        self.assertIn('depthWrite: fullyOpaque,', source)

    def test_user_opacity_remains_authoritative_in_structure_panel(self):
        source = (ROOT / 'web/js/segmentation-structure-panel.js').read_text()
        self.assertIn('structure.opacity = clamp(Number(this.opacity.value) / 100, 0, 1);', source)

    def test_phase6fc_cache_busts_surface_material_consumers(self):
        viewer = (ROOT / 'web/js/segmentation-surface-viewer.js').read_text()
        app = (ROOT / 'web/js/app.js').read_text()
        html = (ROOT / 'web/index.html').read_text()
        self.assertIn('reconstruction-surface-presentation.js?v=phase6e-b-r1-phase6e-d-r1-phase6f-c-r3', viewer)
        self.assertIn('reconstruction-surface-presentation.js?v=phase6e-b-r1-phase6e-d-r1-phase6f-c-r3', app)
        self.assertIn('segmentation-surface-viewer.js?v=phase6a-r1-phase6b-r1-phase6c-r2-phase6d2b-r1-phase6e-b-r1-phase6e-d-r1-phase6f-b-r1-phase6b-fallback-r1-phase6f-c-r3', app)
        self.assertIn('volume-surface-viewer.js?v=phase6d2b-r1-phase6e-b-r1-phase6e-d-r1-phase6e-e-r1-phase6f-c-r3', app)
        self.assertIn('phase6b-fallback-r1-phase6f-c-r3', html)


    def test_surface_mode_semantic_overlay_controls_direct_ct_depth_policy(self):
        presentation = (ROOT / 'web/js/reconstruction-surface-presentation.js').read_text()
        volume_viewer = (ROOT / 'web/js/volume-surface-viewer.js').read_text()
        app = (ROOT / 'web/js/app.js').read_text()
        self.assertIn('resolveDirectCtSurfaceCompositionPolicy', presentation)
        self.assertIn('semanticOverlayActive', volume_viewer)
        self.assertIn('setSemanticOverlayActive(active)', volume_viewer)
        self.assertIn('surfaceSemanticOverlayActive', app)
        self.assertIn('snapshot.mode === "surface"', app)
        self.assertIn('volumeSurfaceLayer?.setSemanticOverlayActive(surfaceSemanticOverlayActive)', app)

    def test_later_6f_steps_remain_out_of_scope(self):
        doc = (ROOT / 'docs/phase_history/PHASE6F_C_STRUCTURE_TRANSPARENCY_ROBUSTNESS.md').read_text()
        self.assertIn('Phase 6F-D', doc)
        self.assertIn('not enabled', doc.lower())
        self.assertIn('Phase 6F-E', doc)
        self.assertIn('Phase 6F-F', doc)


if __name__ == '__main__':
    unittest.main()
