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
                         '.clip-plane-label'):
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
        self.assertIn('const qualificationSampling = Boolean(qualification)', app)
        self.assertIn('if (qualificationSampling) shouldRender = true', app)
        self.assertIn('qualificationSampling || state.autoRotate', app)
        handler = app.split('renderQualityPolicy.addEventListener("change", () => {')[1].split('});')[0]
        self.assertIn('qualification?.resetWindow()', handler)
        self.assertIn('phase3d-r21-phase4h6', (ROOT / 'web/index.html').read_text())

    def test_full_range_is_inactive_by_default_and_after_reset(self):
        app = (ROOT / 'web/js/app.js').read_text()
        html = (ROOT / 'web/index.html').read_text()
        for plane in ('axial', 'coronal', 'sagittal'):
            self.assertIn(
                f'{plane}: {{ enabled: false, startPercent: 0, endPercent: 100 }}', app)
            self.assertRegex(
                html, rf'data-clip-enabled="{plane}"[^>]*data-active="false"')
        reset = app.split('function resetPatientClipping()')[1].split('\nfunction ', 1)[0]
        self.assertIn('state.clipping[plane].enabled = false', reset)

    def test_intensity_interval_uses_one_non_crossing_dual_handle_control(self):
        html = (ROOT / 'web/index.html').read_text()
        app = (ROOT / 'web/js/app.js').read_text()
        styles = (ROOT / 'web/css/styles.css').read_text()
        renderer = (ROOT / 'web/js/patient-volume-ray-marcher.js').read_text()

        self.assertIn('id="transferIntensityRange"', html)
        self.assertIn('id="transferRangeLow"', html)
        self.assertIn('id="transferRangeHigh"', html)
        self.assertIn('class="transfer-dual-range"', html)
        self.assertIn('class="transfer-retained-track"', html)
        self.assertIn('--intensity-start-percent', styles)
        self.assertIn('--intensity-end-percent', styles)
        intensity_style = styles.split(
            '.transfer-dual-range input[type="range"]::-webkit-slider-thumb', 1
        )[1].split('}', 1)[0]
        self.assertIn('width: 16px', intensity_style)
        self.assertIn('height: 16px', intensity_style)
        self.assertIn('border: 0', intensity_style)
        self.assertIn('syncIntensityRangeTrack(transfer)', app)
        self.assertIn('constrainMedicalIntensityInterval(', app)
        self.assertIn('maximum - minimum < minimumGap', renderer)


if __name__ == '__main__':
    unittest.main()
