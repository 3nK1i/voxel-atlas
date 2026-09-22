"""Phase 6I-A: source-only, no patient data, no third-party test dependencies."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'web/index.html').read_text(encoding='utf-8')
CSS = (ROOT / 'web/css/styles.css').read_text(encoding='utf-8')
JS = (ROOT / 'web/js/parameter-help.js').read_text(encoding='utf-8')


class ContextualHelpContractTests(unittest.TestCase):
    def test_left_reconstruction_modes_have_independent_help_without_nested_buttons(self):
        left = HTML.split('id="reconstructionPanel"', 1)[1].split('</section>', 1)[0]
        self.assertEqual(left.count('class="va-reconstruction-mode-help-row"'), 3)
        for mode in ('volume', 'surface', 'combined'):
            with self.subTest(mode=mode):
                self.assertIn(f'data-help-reconstruction-mode="{mode}"', left)
                self.assertEqual(left.count(f'data-reconstruction-mode="{mode}"'), 1)
                self.assertIn(f'"mode-{mode}": [', JS)
                self.assertIn(f'`mode-${{mode}}`', JS)
        self.assertIn('button.after(trigger(', JS)
        self.assertIn('.va-reconstruction-mode-help-row > .va-parameter-help', CSS)
        self.assertNotIn('requestReconstructionVisualizationMode(', JS)
        self.assertNotIn('requestSegmentation', JS)

    def test_review_controls_keep_labels_and_values_in_separate_layout_slots(self):
        panel = HTML.split('id="segmentationCorrectionPanel"', 1)[1].split('</section>', 1)[0]
        self.assertIn('<span class="va-correction-action-caption">Action</span>', panel)
        self.assertIn('<span class="va-correction-radius-caption">Radius</span>', panel)
        self.assertIn('<select id="segmentationCorrectionKind" disabled>', panel)
        self.assertIn('<strong id="segmentationCorrectionRadiusValue">3.0 mm</strong>', panel)
        self.assertIn('grid-template-columns: 70px minmax(0, 1fr);', CSS)
        self.assertIn('.correction-controls .va-correction-radius-label', CSS)
        self.assertIn('.correction-controls .va-correction-radius-label > strong', CSS)
        self.assertIn('width: 100%;', CSS.split('.correction-controls select {', 1)[1].split('}', 1)[0])
        self.assertNotIn('const ignored =', JS)

    def test_module_loaded_once_without_changing_app_entrypoint(self):
        self.assertEqual(HTML.count('/js/parameter-help.js?v=phase6i-a-r3'), 1)
        self.assertEqual(HTML.count('src="/js/app.js?v='), 1)
        self.assertIn('phase6i-a-r3', HTML.split('/css/styles.css?v=', 1)[1].split('"', 1)[0])

    def test_every_static_parameter_has_explicit_help(self):
        config = JS.split('const HELP = Object.freeze({', 1)[1].split('\n});', 1)[0]
        fields = (
            'renderQualityPolicy transferPresetSelect renderingModeSelect slicePlaneSelect '
            'slabProjectionSelect slicePosition slabThicknessSelect slabCustomThickness '
            'transferWindowCenter transferWindowWidth transferRangeLow transferRangeHigh '
            'transferDensity opacitySlider transferOpacitySoftness transferEdgeDefinition '
            'transferShadingStrength volumeSurfaceIsovalue volumeSurfaceRegionMode '
            'segmentationOverlayToggle segmentationOverlayOpacity segmentationSurfaceToggle '
            'segmentationStructureSearch segmentationStructureExplode segmentationStructureColor '
            'segmentationStructureOpacity segmentationStructureClipParticipation '
            'mprClippingOverlayToggle segmentationCorrectionKind segmentationCorrectionRadius'
        ).split()
        self.assertEqual(len(fields), 30)
        for field in fields:
            with self.subTest(field=field):
                self.assertEqual(len(re.findall(r'\bid="' + re.escape(field) + r'"', HTML)), 1)
                self.assertRegex(config, r'(?m)^  ' + re.escape(field) + r': \["')

    def test_special_and_dynamic_controls_are_explained(self):
        for name in ('surface-volume', 'surface-segmentation', 'profile', 'source',
                     'workflow', 'structure-row', 'axial-enabled', 'coronal-enabled',
                     'sagittal-enabled', 'axial-start', 'axial-end', 'coronal-start',
                     'coronal-end', 'sagittal-start', 'sagittal-end'):
            with self.subTest(name=name):
                self.assertIn(f'"{name}": [', JS)
        self.assertIn('MutationObserver', JS)
        self.assertIn('segmentationStructureGroups', JS)
        self.assertIn('transferWindowCenterLabel', JS)

    def test_keyboard_click_dismissal_and_safe_explanations(self):
        for phrase in ('aria-expanded', 'aria-haspopup', 'aria-controls',
                       'Escape', 'Enter', 'event.preventDefault()',
                       'event.stopPropagation()', 'closeButton.focus()',
                       'textContent = entry[1]'):
            self.assertIn(phrase, JS)
        self.assertNotIn('innerHTML', JS)
        self.assertNotIn('fetch(', JS)
        self.assertNotIn('localStorage', JS)
        self.assertNotIn('sessionStorage', JS)

    def test_scoped_accessible_styling_and_no_algorithm_changes(self):
        self.assertIn('.va-parameter-help:focus-visible', CSS)
        self.assertIn('.va-parameter-help-popover[hidden]', CSS)
        self.assertIn('.structure-row > .va-parameter-help', CSS)
        self.assertIn('Patient-LPS', JS)
        self.assertIn('source label map', JS.lower())


if __name__ == '__main__':
    unittest.main()
