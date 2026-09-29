from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "web/js/reconstruction-surface-presentation.js"
PROFILE = ROOT / "web/js/reconstruction-presentation-profile.js"
APP = ROOT / "web/js/app.js"
INDEX = ROOT / "web/index.html"
CSS = ROOT / "web/css/styles.css"
DOC = ROOT / "docs/phase_history/PHASE6E_C_FIDELITY_PROFILE_QUALIFICATION.md"


def block(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left)
    return text[left:right]


class Phase6ECFidelityProfileQualificationTests(unittest.TestCase):
    def test_fidelity_profile_keeps_locked_reference_lighting_values(self):
        source = SHARED.read_text(encoding="utf-8")
        fidelity = block(source, '  fidelity: Object.freeze({', '  presentation: Object.freeze({')
        expected = (
            'sky: "#d8efff", ground: "#182332", intensity: 1.18',
            'color: "#fff6ea", intensity: 1.35, position: Object.freeze([2.8, 3.6, 4.8])',
            'color: "#c9ddff", intensity: 0.48, position: Object.freeze([-3.4, 1.4, 2.6])',
            'color: "#e4efff", intensity: 0.62, position: Object.freeze([-1.2, 3.0, -4.2])',
        )
        for token in expected:
            self.assertIn(token, fidelity)

    def test_fidelity_profile_keeps_locked_direct_ct_material_reference(self):
        source = SHARED.read_text(encoding="utf-8")
        fidelity = block(source, '  fidelity: Object.freeze({', '  presentation: Object.freeze({')
        self.assertIn('color: "#e8e1d2"', fidelity)
        self.assertIn('roughness: 0.62', fidelity)
        self.assertIn('metalness: 0.0', fidelity)

    def test_fidelity_segmentation_material_is_neutral_but_semantic_color_and_opacity_remain_authoritative(self):
        source = SHARED.read_text(encoding="utf-8")
        fidelity = block(source, '  fidelity: Object.freeze({', '  presentation: Object.freeze({')
        self.assertIn('roughness: 0.60', fidelity)
        self.assertIn('selectedRoughness: 0.52', fidelity)
        self.assertIn('material.color.set(structure?.colorHex || "#ffffff")', source)
        self.assertIn('const opacity = Number(structure?.opacity ?? 1)', source)

    def test_fidelity_remains_default_reference_profile(self):
        profile = PROFILE.read_text(encoding="utf-8")
        self.assertIn('this.profile = "fidelity"', profile)
        self.assertIn('this.profile = "fidelity";', profile)
        self.assertIn('geometry-first inspection', profile)

    def test_profile_switch_path_still_performs_no_geometry_or_io(self):
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

    def test_reconstruction_mode_cards_have_uniform_non_active_border_semantics(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertIn('Phase 6E-C — reconstruction-card border consistency', css)
        self.assertRegex(
            css,
            re.compile(
                r'\.reconstruction-mode-card\[data-state="ready"\]:not\(\[data-active="true"\]\).*?'
                r'\.reconstruction-mode-card\[data-capability="ready"\]:not\(\[data-active="true"\]\).*?'
                r'border-color:',
                re.S,
            ),
        )
        self.assertIn('.reconstruction-mode-card[data-active="true"]', css)

    def test_css_cache_key_is_advanced_for_6e_c_ui_correction(self):
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn('styles.css?v=', index)
        self.assertIn('phase6e-c-r1', index)

    def test_phase6e_c_document_records_scope_and_later_phase_boundary(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn('51d276b903ada7eac904b9f73f17881673d45918', doc)
        self.assertIn('Fidelity', doc)
        self.assertIn('Direct CT', doc)
        self.assertIn('segmentation', doc.lower())
        self.assertIn('reconstruction-card', doc.lower())
        self.assertIn('6E-D', doc)
        self.assertIn('geometry', doc.lower())
        self.assertIn('Clinical validation is not claimed', doc)


if __name__ == '__main__':
    unittest.main()
