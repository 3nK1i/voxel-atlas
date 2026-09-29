"""Phase 6I-D: user-visible rendering profile and reversible CT visibility."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'web/index.html').read_text(encoding='utf-8')
CSS = (ROOT / 'web/css/styles.css').read_text(encoding='utf-8')
APP = (ROOT / 'web/js/app.js').read_text(encoding='utf-8')
HELP = (ROOT / 'web/js/parameter-help.js').read_text(encoding='utf-8')
PROFILE = (ROOT / 'web/js/reconstruction-presentation-profile.js').read_text(encoding='utf-8')
SURFACE = (ROOT / 'web/js/reconstruction-surface-presentation.js').read_text(encoding='utf-8')


class Phase6IDPresentationAndVisibility(unittest.TestCase):
    def test_normal_interface_has_presentation_without_profile_selection_buttons(self):
        panel = HTML.split('id="reconstructionVisualizationPanel"', 1)[1].split('</section>', 1)[0]
        self.assertIn('id="reconstructionPresentationProfileStatus"', panel)
        self.assertIn('>Presentation</span>', panel)
        self.assertNotIn('data-reconstruction-presentation-profile=', panel)
        self.assertNotIn('reconstruction-presentation-profile-options', panel)
        self.assertIn('requestProfile("presentation")', APP)
        self.assertIn('dataset.presentationProfile = snapshot.profile', APP)

    def test_internal_fidelity_science_and_qualification_are_preserved(self):
        self.assertIn('id: "fidelity"', PROFILE)
        self.assertIn('id: "presentation"', PROFILE)
        self.assertIn('this.profile = "fidelity"', PROFILE)
        self.assertIn('fidelity: Object.freeze({', SURFACE)
        self.assertIn('presentation: Object.freeze({', SURFACE)
        self.assertIn('setPresentationProfile(snapshot.profile)', APP)
        self.assertIn('resolveCombinedPresentationBalance', APP)
        self.assertIn('Geometry and source data remain unchanged.', HTML)
        self.assertNotIn('fetch(', APP.split('function applyReconstructionPresentationProfileSnapshot(',1)[1].split('function requestReconstructionPresentationProfile(',1)[0])

    def test_direct_ct_visibility_uses_contrasting_closed_and_open_native_select(self):
        self.assertIn('<select id="volumeSurfaceRegionMode" disabled>', HTML)
        for choice in ('value="all"', 'value="hide-region-1"', 'value="hide-region-2"'):
            self.assertIn(choice, HTML)
        scoped = CSS.split('/* Phase 6I-D — readable native Direct CT visibility menu. */',1)[1]
        self.assertIn('.volume-surface-region-control select {', scoped)
        self.assertIn('color: var(--text);', scoped)
        self.assertIn('background-color: var(--panel-solid);', scoped)
        self.assertIn('.volume-surface-region-control select option {', scoped)
        self.assertIn('color: var(--text);', scoped.split('.volume-surface-region-control select option {',1)[1])
        self.assertIn('background-color: var(--panel-solid);', scoped.split('.volume-surface-region-control select option {',1)[1])
        self.assertIn('color-scheme: inherit;', scoped)
        self.assertIn('volumeSurfaceLayer.setRegionDisplayMode(volumeSurfaceRegionMode.value)', APP)
        self.assertIn('volumeSurfaceRegionMode.value = enabled ? state.mode : "all"', APP)
        self.assertIn('Hiding a region is reversible', HELP)

    def test_cache_refresh_and_contextual_help_align_with_presentation_only_ui(self):
        self.assertIn('phase6i-d-r1', HTML.split('/css/styles.css?v=',1)[1].split('"',1)[0])
        self.assertIn('phase6i-d-r1', HTML.split('src="/js/app.js?v=',1)[1].split('"',1)[0])
        self.assertIn('"profile": ["Presentation"', HELP)
        self.assertNotIn('neutral fidelity-oriented viewing or a more polished presentation', HELP)


if __name__ == '__main__':
    unittest.main()
