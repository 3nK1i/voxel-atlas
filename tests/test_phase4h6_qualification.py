from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RenderingQualificationTests(unittest.TestCase):
    def test_compact_readable_clipping_labels(self):
        css = (ROOT / 'web/css/styles.css').read_text()
        for selector in ('.clip-range-summary', '.clip-boundary-labels',
                         '.clip-boundary-values strong', '.clip-plane-heading strong',
                         '.clip-plane-toggle'):
            rules = re.findall(re.escape(selector) + r'\s*\{([^}]+)\}', css)
            sizes = [float(n) for rule in rules for n in re.findall(r'font-size:\s*([\d.]+)px', rule)]
            self.assertEqual(sizes[-1], 11, selector)

    def test_runtime_contract(self):
        result = subprocess.run(['node', 'scripts/check_phase4h6_qualification.mjs'],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_local_only_diagnostics_integration(self):
        app = (ROOT / 'web/js/app.js').read_text()
        self.assertIn('installRenderingQualification', app)
        self.assertIn('qualification?.recordFrame', app)
        self.assertIn('qualification?.resetWindow()', app)
        handler = app.split('renderQualityPolicy.addEventListener("change", () => {')[1].split('});')[0]
        self.assertIn('qualification?.resetWindow()', handler)
        self.assertIn('phase3d-r21-phase4h6', (ROOT / 'web/index.html').read_text())

    def test_clipping_is_active_at_full_range_by_default_and_after_reset(self):
        app = (ROOT / 'web/js/app.js').read_text()
        html = (ROOT / 'web/index.html').read_text()
        for plane in ('axial', 'coronal', 'sagittal'):
            self.assertIn(
                f'{plane}: {{ enabled: true, startPercent: 0, endPercent: 100 }}', app)
            self.assertRegex(
                html, rf'data-clip-enabled="{plane}"[^>]*checked[^>]*disabled')
        reset = app.split('function resetPatientClipping()')[1].split('\nfunction ', 1)[0]
        self.assertIn('state.clipping[plane].enabled = true', reset)


if __name__ == '__main__':
    unittest.main()
