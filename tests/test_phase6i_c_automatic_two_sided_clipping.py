"""6I-C non-clinical UI contracts; synthetic runtime probe tests clipping geometry requests."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'web/index.html').read_text(encoding='utf-8')
APP = (ROOT / 'web/js/app.js').read_text(encoding='utf-8')
HELP = (ROOT / 'web/js/parameter-help.js').read_text(encoding='utf-8')
CSS = (ROOT / 'web/css/styles.css').read_text(encoding='utf-8')


class AutomaticClippingTests(unittest.TestCase):
    def test_there_are_six_independent_bounds_and_no_plane_activation_checkboxes(self):
        self.assertNotRegex(HTML, r'<input[^>]*data-clip-enabled=')
        for plane, start, end in (
            ('axial', 'Inferior', 'Superior'),
            ('coronal', 'Posterior', 'Anterior'),
            ('sagittal', 'Right', 'Left'),
        ):
            with self.subTest(plane=plane):
                self.assertIn(f'data-clipping-active="false" data-clip-plane="{plane}"', HTML)
                self.assertIn(f'data-clip-enabled="{plane}" data-active="false" role="status"', HTML)
                self.assertIn(f'data-clip-start="{plane}" aria-label="{start} clipping boundary"', HTML)
                self.assertIn(f'data-clip-end="{plane}" aria-label="{end} clipping boundary"', HTML)
        self.assertIn('id="mprClippingOverlayToggle" type="checkbox"', HTML)
        self.assertIn('id="clippingResetButton"', HTML)

    def test_full_range_remains_movable_and_request_is_derived_from_both_bounds(self):
        self.assertIn('function clippingRangeIsActive(startPercent, endPercent)', APP)
        self.assertIn('return Number(startPercent) > 0 || Number(endPercent) < 100;', APP)
        self.assertIn('enabled: clippingRangeIsActive(state.clipping[plane].startPercent, state.clipping[plane].endPercent)', APP)
        self.assertIn('controlsForPlane.start.disabled = !available;', APP)
        self.assertIn('controlsForPlane.end.disabled = !available;', APP)
        self.assertNotIn('controlsForPlane.enabled.addEventListener', APP)
        self.assertIn('state.clipping[plane].enabled = false;', APP)
        self.assertIn('controlsForPlane.status.textContent = clipping.enabled ? "Active" : "Full range";', APP)
        self.assertIn('minimumLpsMm: Math.min(startLpsMm, endLpsMm)', APP)
        self.assertIn('maximumLpsMm: Math.max(startLpsMm, endLpsMm)', APP)
        self.assertIn('reversed: true', APP)  # Coronal posterior/anterior LPS sign
        self.assertIn('volumeSurfaceLayer?.setClippingPlanes(request)', APP)
        self.assertIn('segmentationSurfaceLayer?.setClippingPlanes(request)', APP)
        self.assertIn('volumeRayMarcher.setClippingPlanes(request)', APP)

    def test_status_styling_and_help_remain_reachable(self):
        self.assertIn('.clip-plane-control[data-clipping-active="true"]', CSS)
        self.assertIn('.clip-plane-state[data-active="true"]', CSS)
        for plane in ('axial','coronal','sagittal'):
            self.assertIn(f'"{plane}-enabled": [', HELP)
            self.assertIn(f"'[data-clip-plane=\"{plane}\"] .clip-plane-label'", HELP)
        self.assertIn('Moving either bound inward', HELP)
        self.assertIn('data-clipping-state="unavailable"', HTML)
        self.assertIn('Follow Directional Cut', HELP)

    def test_synthetic_runtime_all_three_planes_and_two_endpoints(self):
        result = subprocess.run(
            ['node', 'scripts/check_phase6i_c_automatic_clipping.mjs'],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PHASE6I_C_BOTH_BOUNDS_PER_PLANE=PASS', result.stdout)
        self.assertIn('PHASE6I_C_ALL_THREE_LPS_INTERSECTION_REQUESTS=PASS', result.stdout)
        self.assertIn('PHASE6I_C_FULL_RANGE_RESET_AND_NO_HIDDEN_CLIPPING=PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
