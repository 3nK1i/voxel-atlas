"""Phase 6J-D5D: integrated D2 -> D5 lifecycle acceptance contracts."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

D5D_RUNNER = ROOT / "scripts/run_phase6j_d5d_checks.sh"
D5D_DOC = ROOT / "docs/phase_history/PHASE6J_D5D_INTEGRATED_LIFECYCLE_ACCEPTANCE.md"
D5C_RUNNER = ROOT / "scripts/run_phase6j_d5c_checks.sh"
D5B_RUNNER = ROOT / "scripts/run_phase6j_d5b_checks.sh"
D4_RUNNER = ROOT / "scripts/run_phase6j_d4_checks.sh"
D45D_RUNNER = ROOT / "scripts/run_phase6j_d45d_checks.sh"


class IntegratedLifecycleAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d5c = D5C_RUNNER.read_text(encoding="utf-8")
        cls.d5b = D5B_RUNNER.read_text(encoding="utf-8")
        cls.d4 = D4_RUNNER.read_text(encoding="utf-8")
        cls.d45d = D45D_RUNNER.read_text(encoding="utf-8")

    def _runner(self) -> str:
        self.assertTrue(D5D_RUNNER.is_file(), "D5D integrated runner is missing")
        return D5D_RUNNER.read_text(encoding="utf-8")

    def _doc(self) -> str:
        self.assertTrue(D5D_DOC.is_file(), "D5D integrated acceptance document is missing")
        return D5D_DOC.read_text(encoding="utf-8")

    def test_d5d_artifacts_exist(self):
        self.assertTrue(D5D_RUNNER.is_file())
        self.assertTrue(D5D_DOC.is_file())

    def test_current_gate_composition_reaches_d2_through_d5(self):
        self.assertIn("bash scripts/run_phase6j_d5b_checks.sh", self.d5c)
        self.assertIn("bash scripts/run_phase6j_d45c_checks.sh", self.d5b)
        self.assertIn("bash scripts/run_phase6j_d4_checks.sh", self.d5b)
        self.assertIn("tests.test_phase6j_d3_mri_mpr_overlays", self.d4)
        self.assertIn("tests.test_phase6j_d2_mri_label_map_import", self.d4)

    def test_d5d_reuses_current_gate_and_focused_d45d_contract(self):
        runner = self._runner()
        self.assertIn("bash scripts/run_phase6j_d5c_checks.sh", runner)
        self.assertIn("tests.test_phase6j_d45d_direct_mri_acceptance", runner)
        self.assertIn("tests.test_phase6j_d2_mri_label_map_import", runner)
        self.assertIn("scripts/qualify_phase6j_d45d_real_mri.py --help", runner)

    def test_historical_d45d_delta_guard_is_not_replayed(self):
        runner = self._runner()
        doc = self._doc()
        self.assertIn("EXPECTED_BASE=c688507", self.d45d)
        self.assertNotIn("bash scripts/run_phase6j_d45d_checks.sh", runner)
        self.assertIn("historical", doc.lower())
        self.assertIn("c688507", doc)

    def test_d5d_is_qualification_only_and_preserves_no_inference_contract(self):
        runner = self._runner()
        for token in (
            "D5D_PRODUCTION_IMPLEMENTATION_CHANGES=NO",
            "MRI_INFERENCE=NOT_RUN",
            "PRODUCTION_MRI_IMPORT=NOT_RUN",
            "CLINICAL_VALIDATION=NOT_CLAIMED",
            "DIRECT_CT_BACKWARD_COMPATIBILITY=PRESERVED",
            "D5B_CROSS_STUDY_LIFECYCLE=PRESERVED",
            "D5C_SAME_STUDY_LIFECYCLE=PRESERVED",
        ):
            with self.subTest(token=token):
                self.assertIn(token, runner)

    def test_document_locks_integrated_manual_matrix(self):
        doc = self._doc()
        for token in (
            "MRI → CT → MRI",
            "Direct MR",
            "Direct CT",
            "300 HU",
            "Volume / Surface / Combined",
            "no MRI inference",
            "clinical validation",
        ):
            with self.subTest(token=token):
                self.assertIn(token, doc)


if __name__ == "__main__":
    unittest.main()
