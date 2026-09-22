"""Synthetic/documentation-only assertions; never load real-study data."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/phase_history/PHASE6H_C_SCOPED_QUALIFICATION_AND_I6_CLOSURE.md'
GATE = ROOT / 'scripts/run_phase6h_c_closure_checks.sh'


class Phase6HCClosureContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = DOC.read_text(encoding='utf-8')
        cls.gate = GATE.read_text(encoding='utf-8')

    def test_not_a_whole_study_or_clinical_accuracy_claim(self):
        record = self.record
        for qualifier in ('0.0532%', '128 source triangles', '96 sampled contour segments',
                          'No whole-surface Hausdorff', 'clinical validation',
                          'not exhaustive slice', 'not a study-independent assurance'):
            self.assertIn(qualifier, record)

    def test_boundary_and_manual_review_limitations_explicit(self):
        for qualifier in ('acquisition-boundary contact', 'open-looking scan-limited rim',
                          'do **not** prove globally open', 'direct visual Accurate-vs-Refined',
                          'all three clipping planes were', 'Direct CT'):
            self.assertIn(qualifier, self.record)

    def test_fallback_is_observation_not_unexplained_success(self):
        self.assertIn('HTTP 422', self.record)
        self.assertIn('HTTP 200', self.record)
        self.assertIn('underlying 422 classification remains an explicit follow-up', self.record)

    def test_no_study_identifiers_or_private_paths_baked_into_record(self):
        self.assertNotRegex(self.record, r'\bmap-[0-9a-f]{32}\b')
        self.assertNotRegex(self.record, r'\b[0-9a-f]{64}\b')
        self.assertNotRegex(self.record, r'/home/[^\s`]+|/var/lib/[^\s`]+')
        self.assertNotIn('PatientName', self.record)

    def test_gate_stays_synthetic_no_publish_or_runtime_mutation(self):
        for forbidden in ('--execute', 'git commit', 'git push', 'curl ', 'wget ',
                          'uvicorn ', 'pip install', 'git add ', 'data/segmentation'):
            self.assertNotIn(forbidden, self.gate)
        self.assertIn('run_phase6h_a_checks.sh', self.gate)
        self.assertIn('PHASE6H_C_CANDIDATE_CHECKS_OK=YES', self.gate)


if __name__ == '__main__':
    unittest.main()
