"""Phase 6J-D6: final Phase-D qualification/closure contracts."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

D6_RUNNER = ROOT / "scripts/run_phase6j_d6_checks.sh"
D6_DOC = ROOT / "docs/phase_history/PHASE6J_D6_FINAL_PHASE_D_ACCEPTANCE.md"
D5D_RUNNER = ROOT / "scripts/run_phase6j_d5d_checks.sh"
D5D_TEST = ROOT / "tests/test_phase6j_d5d_integrated_acceptance.py"
D5C_RUNNER = ROOT / "scripts/run_phase6j_d5c_checks.sh"
D4_RUNNER = ROOT / "scripts/run_phase6j_d4_checks.sh"
D45D_RUNNER = ROOT / "scripts/run_phase6j_d45d_checks.sh"
D2_STAGE_TEST = ROOT / "tests/test_phase6j_d2_import_stage_reporting.py"


class FinalPhaseDAcceptanceTests(unittest.TestCase):
    def _runner(self) -> str:
        self.assertTrue(D6_RUNNER.is_file(), "D6 final acceptance runner is missing")
        return D6_RUNNER.read_text(encoding="utf-8")

    def _doc(self) -> str:
        self.assertTrue(D6_DOC.is_file(), "D6 final acceptance document is missing")
        return D6_DOC.read_text(encoding="utf-8")

    def test_d6_artifacts_exist(self):
        self.assertTrue(D6_RUNNER.is_file())
        self.assertTrue(D6_DOC.is_file())

    def test_final_gate_reaches_current_d2_through_d5_contracts(self):
        runner = self._runner()
        self.assertIn("bash scripts/run_phase6j_d5c_checks.sh", runner)
        self.assertIn("tests.test_phase6j_d5d_integrated_acceptance", runner)
        self.assertIn("test_phase6j_d2_import_stage_reporting.py", runner)
        self.assertIn("tests.test_phase6j_d45d_direct_mri_acceptance", runner)
        self.assertTrue(D2_STAGE_TEST.is_file())

        d5c = D5C_RUNNER.read_text(encoding="utf-8")
        self.assertIn("bash scripts/run_phase6j_d5b_checks.sh", d5c)
        d4 = D4_RUNNER.read_text(encoding="utf-8")
        self.assertIn("tests.test_phase6j_d3_mri_mpr_overlays", d4)
        self.assertIn("tests.test_phase6j_d2_mri_label_map_import", d4)

    def test_d2_stage_reporting_preserves_historical_tests_import_path(self):
        runner = self._runner()
        self.assertIn('PYTHONPATH="$ROOT/backend:$ROOT/tests"', runner)
        self.assertIn("-m unittest discover", runner)
        self.assertIn("-s tests -p 'test_phase6j_d2_import_stage_reporting.py' -v", runner)

    def test_previous_exact_delta_guards_are_not_replayed(self):
        runner = self._runner()
        doc = self._doc()
        self.assertNotIn("bash scripts/run_phase6j_d45d_checks.sh", runner)
        self.assertNotIn("bash scripts/run_phase6j_d5d_checks.sh", runner)
        self.assertIn("D45D_HISTORICAL_DELTA_GUARD=NOT_REPLAYED", runner)
        self.assertIn("D5D_PREVIOUS_STEP_DELTA_GUARD=NOT_REPLAYED", runner)
        self.assertIn("qualification-only", doc)
        self.assertTrue(D45D_RUNNER.is_file())
        self.assertTrue(D5D_RUNNER.is_file())

    def test_d6_is_qualification_only_and_preserves_safety_boundaries(self):
        runner = self._runner()
        for token in (
            "D6_PRODUCTION_IMPLEMENTATION_CHANGES=NO",
            "MRI_INFERENCE=NOT_RUN",
            "PRODUCTION_MRI_IMPORT=NOT_RUN",
            "CLINICAL_VALIDATION=NOT_CLAIMED",
            "PATIENT_LPS_PROVENANCE=PRESERVED",
            "DIRECT_CT_300HU_COMPATIBILITY=PRESERVED",
            "PHASE_D_D5_LIFECYCLE=PRESERVED",
        ):
            with self.subTest(token=token):
                self.assertIn(token, runner)

    def test_document_locks_final_manual_matrix_and_modality_truthfulness(self):
        doc = self._doc()
        for token in (
            "MRI → CT → MRI",
            "Brain / Spinal Cord",
            "Direct MR",
            "Direct CT",
            "300 HU",
            "normalized signal",
            "0.50",
            "0.35",
            "Volume → Surface → Combined → Volume",
            "clinical validation",
        ):
            with self.subTest(token=token):
                self.assertIn(token, doc)

    def test_d5d_focused_contract_remains_available(self):
        self.assertTrue(D5D_TEST.is_file())
        text = D5D_TEST.read_text(encoding="utf-8")
        self.assertIn("D5B_CROSS_STUDY_LIFECYCLE=PRESERVED", text)
        self.assertIn("D5C_SAME_STUDY_LIFECYCLE=PRESERVED", text)


if __name__ == "__main__":
    unittest.main()
