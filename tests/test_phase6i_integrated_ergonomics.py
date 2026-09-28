"""Phase 6I integrated UI polish: source contract, no patient data or backend dependencies."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'web/index.html').read_text(encoding='utf-8')
CSS = (ROOT / 'web/css/styles.css').read_text(encoding='utf-8')
HELP = (ROOT / 'web/js/parameter-help.js').read_text(encoding='utf-8')


class Phase6IIntegratedErgonomics(unittest.TestCase):
    def test_mode_cards_remain_full_width_without_question_mark_help(self):
        panel = HTML.split('id="reconstructionPanel"', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('va-reconstruction-mode-help-row', panel)
        self.assertNotIn('data-help-reconstruction-mode=', panel)
        for mode in ('volume', 'surface', 'combined'):
            with self.subTest(mode=mode):
                self.assertEqual(panel.count(f'data-reconstruction-mode="{mode}"'), 1)
        self.assertRegex(CSS, r'\.reconstruction-mode-card\s*\{[^}]*width:\s*100%;')
        self.assertNotIn('.va-reconstruction-mode-help-row > .va-parameter-help', CSS)
        self.assertNotIn('button.after(trigger(', HELP)

    def test_direct_ct_help_is_aligned_with_parameter_title(self):
        panel = HTML.split('id="volumeSurfacePanel"', 1)[1].split('</section>', 1)[0]
        for label_id, title in (
            ('volumeSurfaceIsovalue', 'CT isovalue'),
            ('volumeSurfaceRegionMode', 'Direct CT visibility'),
        ):
            with self.subTest(label_id=label_id):
                self.assertRegex(
                    panel,
                    rf'<span(?: id="[^"]+")? class="va-volume-surface-caption-title">{title}</span>',
                )
                self.assertIn(f'for="{label_id}"', panel)
                self.assertIn(f'id="{label_id}"', panel)
        self.assertIn('label.querySelector(".va-volume-surface-caption-title")', HELP)
        self.assertIn('addToCaption(caption, id, title, dialogId)', HELP)
        self.assertIn('.va-volume-surface-caption-title {', CSS)
        self.assertRegex(CSS, r'\.va-volume-surface-caption-title\s*\{[^}]*display:\s*inline-flex;')
        self.assertRegex(CSS, r'\.va-volume-surface-caption-title\s*\{[^}]*align-items:\s*center;')
        self.assertIn('event.preventDefault()', HELP)
        self.assertIn('event.stopPropagation()', HELP)

    def test_ct_numeric_input_and_hu_unit_share_single_box_without_semantic_change(self):
        panel = HTML.split('id="volumeSurfacePanel"', 1)[1].split('</section>', 1)[0]
        self.assertRegex(
            panel,
            r'<span class="volume-surface-isovalue-entry">\s*'
            r'<input id="volumeSurfaceIsovalue" type="number" step="10" value="300" inputmode="decimal" disabled>\s*'
            r'<strong id="volumeSurfaceIsovalueUnits">HU</strong>\s*</span>',
        )
        polished_css = CSS
        self.assertRegex(polished_css, r'\.volume-surface-isovalue-entry\s*\{[^}]*border:\s*1px solid')
        self.assertRegex(polished_css, r'\.volume-surface-isovalue-entry\s*\{[^}]*border-radius:')
        self.assertRegex(polished_css, r'\.volume-surface-isovalue-entry\s*\{[^}]*background:')
        self.assertRegex(polished_css, r'\.volume-surface-isovalue-entry input\s*\{[^}]*background:\s*transparent;')
        self.assertIn('.volume-surface-isovalue-entry:focus-within {', polished_css)
        self.assertNotIn('type="text"', panel.split('class="volume-surface-isovalue-entry"')[1].split('</span>', 1)[0])
        self.assertIn('Bone baseline: 300 HU when in range', panel)

    def test_help_popover_and_mode_behavior_have_no_new_actions(self):
        self.assertEqual(HTML.count('src="/js/parameter-help.js?v='), 1)
        self.assertIn('phase6i-polish-r1', HTML.split('/css/styles.css?v=', 1)[1].split('"', 1)[0])
        self.assertIn('phase6i-polish-r1', HTML.split('/js/parameter-help.js?v=', 1)[1].split('"', 1)[0])
        self.assertNotIn('requestReconstructionVisualizationMode(', HELP)
        self.assertNotIn('requestSegmentation', HELP)
        self.assertIn('aria-expanded', HELP)
        self.assertIn('returnFocus: true', HELP)


if __name__ == '__main__':
    unittest.main()
