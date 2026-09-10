from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
VOL = ROOT / "web/js/volume-surface-viewer.js"
SEG = ROOT / "web/js/segmentation-surface-viewer.js"
SHARED = ROOT / "web/js/reconstruction-surface-presentation.js"
DOC = ROOT / "docs/phase_history/PHASE6E_B_SHARED_LIGHTING_MATERIAL_FOUNDATION.md"


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


class Phase6EBSharedLightingMaterialFoundationTests(unittest.TestCase):
    def test_shared_surface_presentation_module_declares_both_profile_presets(self):
        source = SHARED.read_text(encoding="utf-8")
        self.assertIn('fidelity:', source)
        self.assertIn('presentation:', source)
        self.assertIn('lighting:', source)
        self.assertIn('volumeSurface:', source)
        self.assertIn('segmentationSurface:', source)
        self.assertIn('createSurfaceLightingRig', source)

    def test_app_uses_shared_lighting_rig_instead_of_inline_surface_lights(self):
        app = APP.read_text(encoding="utf-8")
        self.assertIn('createSurfaceLightingRig', app)
        self.assertIn('surfaceLightingRig', app)
        scene_block = block(app, 'const scene = new THREE.Scene();', 'const camera = new THREE.PerspectiveCamera')
        self.assertNotIn('new THREE.HemisphereLight', scene_block)
        self.assertNotIn('new THREE.DirectionalLight', scene_block)

    def test_profile_application_updates_lighting_and_resident_materials_only(self):
        app = APP.read_text(encoding="utf-8")
        profile_block = block(
            app,
            'function applyReconstructionPresentationProfileSnapshot(',
            'function requestReconstructionPresentationProfile(',
        )
        self.assertIn('surfaceLightingRig.setProfile(snapshot.profile)', profile_block)
        self.assertIn('volumeSurfaceLayer?.setPresentationProfile(snapshot.profile)', profile_block)
        self.assertIn('segmentationSurfaceLayer?.setPresentationProfile(snapshot.profile)', profile_block)
        lowered = profile_block.lower()
        for token in ('fetch(', '.build(', 'clearsurface', '.clear(', 'segmentation-workflow', 'setdescriptor('):
            self.assertNotIn(token, lowered)

    def test_volume_surface_layer_uses_shared_material_policy_and_nondestructive_profile_switch(self):
        source = VOL.read_text(encoding="utf-8")
        self.assertIn('applyVolumeSurfaceMaterialProfile', source)
        self.assertIn('createVolumeSurfaceMaterial', source)
        self.assertIn('setPresentationProfile(profileId)', source)
        switch = block(source, '  setPresentationProfile(profileId) {', '  async build(isovalue) {')
        self.assertIn('applyVolumeSurfaceMaterialProfile', switch)
        for token in ('fetch(', 'dispose(', 'clearSurface(', 'BufferGeometry', 'applyMatrix4'):
            self.assertNotIn(token, switch)

    def test_segmentation_surface_layer_uses_shared_material_policy_and_preserves_semantic_color(self):
        source = SEG.read_text(encoding="utf-8")
        self.assertIn('createSegmentationSurfaceMaterial', source)
        self.assertIn('applySegmentationSurfaceMaterialProfile', source)
        self.assertIn('setPresentationProfile(profileId)', source)
        shared = SHARED.read_text(encoding="utf-8")
        self.assertIn('structure?.colorHex', shared)
        switch = block(source, '  setPresentationProfile(profileId) {', '  _makeMaterial(structure) {')
        for token in ('fetch(', 'dispose(', '_abortPending(', 'BufferGeometry', 'applyMatrix4'):
            self.assertNotIn(token, switch)

    def test_shared_policy_preserves_geometry_and_semantic_contracts(self):
        source = SHARED.read_text(encoding="utf-8").lower()
        for token in ('fetch(', '/api/', 'position.setattribute', 'geometry.', 'marching', 'isovalue', 'segmentation-workflow'):
            self.assertNotIn(token, source)
        self.assertIn('colorhex', source)
        self.assertIn('opacity', source)
        self.assertIn('metalness', source)
        self.assertIn('roughness', source)

    def test_existing_6d2_and_300hu_contracts_remain(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertEqual(index.count('data-reconstruction-mode='), 3)
        self.assertIn('data-reconstruction-surface-source="volume-derived"', index)
        self.assertIn('data-reconstruction-surface-source="segmentation-derived"', index)
        self.assertIn('value="300"', index)
        self.assertIn('Bone baseline: 300 HU when in range', index)

    def test_phase6e_b_document_preserves_later_profile_qualification_boundaries(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn('4c6fa747e4f14eb5e28e0e4b42536b992acba805', doc)
        self.assertIn('6E-C', doc)
        self.assertIn('6E-D', doc)
        self.assertIn('shared lighting', doc.lower())
        self.assertIn('material', doc.lower())
        self.assertIn('geometry', doc.lower())
        self.assertIn('Clinical validation is not claimed', doc)


if __name__ == '__main__':
    unittest.main()
