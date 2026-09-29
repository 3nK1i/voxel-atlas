from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "web/js/reconstruction-surface-presentation.js"
PROFILE = ROOT / "web/js/reconstruction-presentation-profile.js"
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
DOC = ROOT / "docs/phase_history/PHASE6E_D_PRESENTATION_SKULL_CAVITY_POLISH.md"


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


class Phase6EDPresentationSkullCavityPolishTests(unittest.TestCase):
    def test_fidelity_reference_values_remain_locked(self):
        source = SHARED.read_text(encoding="utf-8")
        fidelity = block(source, '  fidelity: Object.freeze({', '  presentation: Object.freeze({')
        for token in (
            'sky: "#d8efff", ground: "#182332", intensity: 1.18',
            'color: "#fff6ea", intensity: 1.35, position: Object.freeze([2.8, 3.6, 4.8])',
            'color: "#c9ddff", intensity: 0.48, position: Object.freeze([-3.4, 1.4, 2.6])',
            'color: "#e4efff", intensity: 0.62, position: Object.freeze([-1.2, 3.0, -4.2])',
            'color: "#e8e1d2"',
            'roughness: 0.62',
            'selectedRoughness: 0.52',
        ):
            self.assertIn(token, fidelity)
        self.assertNotIn('viewRelative: true', fidelity)

    def test_presentation_profile_declares_view_relative_balanced_lighting(self):
        source = SHARED.read_text(encoding="utf-8")
        presentation = source[source.index('  presentation: Object.freeze({'):]
        self.assertIn('viewRelative: true', presentation)
        self.assertIn('ground: "#64748a"', presentation)
        self.assertIn('intensity: 0.88', presentation)
        self.assertIn('position: Object.freeze([-2.5, 1.0, 2.2])', presentation)
        self.assertIn('position: Object.freeze([0.8, 2.0, -2.8])', presentation)

    def test_presentation_direct_ct_material_adds_restrained_shadow_lift(self):
        source = SHARED.read_text(encoding="utf-8")
        presentation = source[source.index('  presentation: Object.freeze({'):]
        self.assertIn('color: "#f0e8da"', presentation)
        self.assertIn('roughness: 0.56', presentation)
        self.assertIn('emissive: "#4a4134"', presentation)
        self.assertIn('emissiveIntensity: 0.16', presentation)
        self.assertIn('material.emissive?.set?.', source)

    def test_presentation_segmentation_shadow_lift_preserves_semantic_color(self):
        source = SHARED.read_text(encoding="utf-8")
        presentation = source[source.index('  presentation: Object.freeze({'):]
        self.assertIn('emissiveIntensity: 0.08', presentation)
        self.assertIn('selectedEmissiveIntensity: 0.12', presentation)
        self.assertIn('const semanticColor = structure?.colorHex || "#ffffff"', source)
        self.assertIn('material.color.set(structure?.colorHex || "#ffffff")', source)
        self.assertIn('material.emissive?.set?.(semanticColor)', source)

    def test_shared_rig_exposes_view_sync_without_geometry_or_io(self):
        source = SHARED.read_text(encoding="utf-8")
        self.assertIn('syncToView(camera, focus)', source)
        sync = block(source, '    syncToView(camera, focus) {', '  };\n  rig.setProfile("fidelity")')
        self.assertIn('camera?.quaternion', sync)
        self.assertIn('placeViewRelativeLight', sync)
        helper = block(source, 'function placeViewRelativeLight(', 'export function createSurfaceLightingRig')
        self.assertIn('applyQuaternion', helper)
        for token in ('fetch(', '/api/', 'geometry.', 'applyMatrix4', 'setAttribute', 'marching'):
            self.assertNotIn(token, sync + helper)

    def test_app_syncs_presentation_lights_to_camera_only_at_render_time(self):
        app = APP.read_text(encoding="utf-8")
        animate = app[app.index('function animate(timestamp) {'):]
        self.assertIn('surfaceLightingRig.syncToView(camera, controls.target)', animate)
        self.assertLess(
            animate.index('surfaceLightingRig.syncToView(camera, controls.target)'),
            animate.index('renderer.render(scene, camera)'),
        )

    def test_profile_switch_path_remains_geometry_and_io_free(self):
        app = APP.read_text(encoding="utf-8")
        section = block(
            app,
            'function applyReconstructionPresentationProfileSnapshot(',
            'function requestReconstructionPresentationProfile(',
        ).lower()
        for token in (
            'fetch(', '.build(', 'clearsurface', '.clear(', 'applymatrix4(',
            'geometry.setattribute(', 'geometry.setindex(', 'segmentation-workflow',
        ):
            self.assertNotIn(token, section)

    def test_phase6e_d_cache_keys_are_advanced(self):
        index = INDEX.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        self.assertIn('phase6e-d-r1', index)
        self.assertIn('reconstruction-surface-presentation.js?v=phase6e-b-r1-phase6e-d-r1', app)

    def test_phase6e_d_document_records_presentation_only_boundary(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn('df6ceecc18242b22c8490d4b4fad5c096a2f86cf', doc)
        self.assertIn('view-relative', doc.lower())
        self.assertIn('skull', doc.lower())
        self.assertIn('cavity', doc.lower())
        self.assertIn('Fidelity', doc)
        self.assertIn('geometry', doc.lower())
        self.assertIn('300 HU', doc)
        self.assertIn('6E-E', doc)
        self.assertIn('Clinical validation is not claimed', doc)


if __name__ == '__main__':
    unittest.main()
