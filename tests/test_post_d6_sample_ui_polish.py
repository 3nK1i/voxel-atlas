"""Post-D6 sample-catalog polish and Direct-MR presentation initialization contracts."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PostD6SampleUiPolishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
        self.backend = (ROOT / "backend/voxelatlas/volume_surfaces.py").read_text(encoding="utf-8")
        self.runner = (ROOT / "scripts/run_post_d6_ui_polish_checks.sh").read_text(encoding="utf-8")

    def test_exact_modality_art_assets_replace_text_monograms(self) -> None:
        ct_svg = (ROOT / "web/assets/sample-study-ct.svg").read_text(encoding="utf-8")
        mr_svg = (ROOT / "web/assets/sample-study-mr.svg").read_text(encoding="utf-8")
        self.assertIn('SAMPLE_MODALITY_ARTWORK = Object.freeze({', self.app)
        self.assertIn('CT: "/assets/sample-study-ct.svg"', self.app)
        self.assertIn('MR: "/assets/sample-study-mr.svg"', self.app)
        self.assertIn('artwork.className = "sample-study-modality-art"', self.app)
        self.assertIn('artwork.src = SAMPLE_MODALITY_ARTWORK[sample.modality]', self.app)
        self.assertNotIn('monogram.textContent = sample.modality', self.app)
        self.assertIn('.sample-study-modality-art', self.css)
        self.assertIn('object-fit: cover;', self.css)

        for svg, prefix, label in (
            (ct_svg, "mh-ct-d-", "(0008,0060) CT"),
            (mr_svg, "mh-mr-d-", "(0008,0060) MR"),
        ):
            with self.subTest(label=label):
                self.assertIn('viewBox="0 0 480 360"', svg)
                self.assertIn('preserveAspectRatio="xMidYMid slice"', svg)
                self.assertIn('prefers-reduced-motion:reduce', svg)
                self.assertIn(prefix, svg)
                self.assertIn(label, svg)

    def test_open_is_direct_and_confirmation_ui_is_removed(self) -> None:
        self.assertIn('open.textContent = "Open";', self.app)
        self.assertNotIn('Open in VoxelAtlas', self.app)
        for retired in (
            'sampleReplaceConfirm', 'sampleReplaceText', 'sampleReplaceCancel',
            'sampleReplaceAccept', 'sampleReplacementResolver',
            'confirmSampleReplacement', 'resolveSampleReplacement',
            'Replace the current workspace?', 'Keep current study', 'Open sample',
        ):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, self.app + self.index)
        self.assertNotIn('sample-replace-', self.css)

        match = re.search(
            r'async function requestSampleLoad\(sample\) \{(?P<body>[\s\S]*?)\n\}',
            self.app,
        )
        self.assertIsNotNone(match)
        body = match.group('body')
        self.assertNotIn('confirmSampleReplacement', body)
        self.assertIn('setSampleCatalogProgress(', body)
        self.assertIn('await sampleStudyCatalogClient.load(sample.sampleId)', body)
        self.assertIn('applyStudy(payload.study)', body)
        self.assertLess(body.index('setSampleCatalogProgress('), body.index('await sampleStudyCatalogClient.load(sample.sampleId)'))
        # The currently displayed browser study is not replaced until the load request succeeds.
        self.assertLess(body.index('await sampleStudyCatalogClient.load(sample.sampleId)'), body.index('applyStudy(payload.study)'))

    def test_mri_presentation_initializes_to_035_without_changing_backend_default(self) -> None:
        self.assertIn('const MRI_PRESENTATION_INITIAL_ISOVALUE = 0.35;', self.app)
        self.assertIn('const initialLevel = isMr && mrPresentationLevelInRange', self.app)
        self.assertIn('? MRI_PRESENTATION_INITIAL_ISOVALUE', self.app)
        self.assertIn('volumeSurfaceIsovalue.value = isMr ? initialLevel.toFixed(2) : String(initialLevel);', self.app)
        self.assertIn('DEFAULT_MR_NORMALIZED_ISOVALUE = 0.50', self.backend)
        self.assertIn('DEFAULT_CT_BONE_ISOVALUE_HU = 300.0', self.backend)
        self.assertIn('volumeSurfaceIsovalue.step = "0.01"', self.app)
        self.assertIn('volumeSurfaceIsovalue.step = "10"', self.app)

    def test_runner_executes_shell_check_functions_without_timeout_lookup(self) -> None:
        self.assertIn('declare -F "$1"', self.runner)
        self.assertIn('if "$@" >"$log" 2>&1; then', self.runner)
        self.assertIn('elif timeout "$CHECK_TIMEOUT_SECONDS" "$@" >"$log" 2>&1; then', self.runner)
        for helper in (
            "check_expected_delta",
            "check_no_backend_delta",
            "check_patient_data_safety",
            "check_new_file_whitespace",
        ):
            with self.subTest(helper=helper):
                self.assertRegex(
                    self.runner,
                    rf'run_quiet\s+"[^"]+"\s+{helper}',
                )

    def test_cache_tokens_cover_the_web_changes(self) -> None:
        self.assertIn('phase6j-d45c-r2-postd6-ui-r1', self.index)
        self.assertIn('phase6j-d5c-r1-postd6-ui-r1', self.index)


if __name__ == "__main__":
    unittest.main()
