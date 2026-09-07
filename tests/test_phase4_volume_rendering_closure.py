from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE_SHA = "ff1b77727dc9b8efc1ba7a66d74861cffddcc5b9"
EVIDENCE_SHA256 = "415fbcbf3dc636137db775099a4562f6ed623448ceaf9e4053db2e8a4007137f"


class Phase4VolumeRenderingClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.h6 = (
            ROOT / "docs/phase_history/PHASE4H6_RENDERING_QUALIFICATION.md"
        ).read_text(encoding="utf-8")
        self.closure = (
            ROOT / "docs/phase_history/PHASE4_VOLUME_RENDERING_CLOSURE.md"
        ).read_text(encoding="utf-8")

    def test_closure_is_bound_to_the_deployed_release_and_evidence(self) -> None:
        self.assertIn(RELEASE_SHA, self.closure)
        self.assertIn(EVIDENCE_SHA256, self.closure)
        self.assertIn("Qualified slot/mode combinations: `24`", self.closure)
        self.assertIn("minimum `63`, maximum `600`", self.closure)
        self.assertIn("`16.7` to `16.8` ms", self.closure)
        self.assertIn("PHASE4H6_RUNTIME_EVIDENCE=PASS", self.closure)

    def test_production_and_manual_acceptance_are_recorded(self) -> None:
        for marker in (
            "byte-for-byte production content checks: PASS",
            "internal `/api/health`: PASS",
            "public `/api/health`: PASS",
            "sample-study catalog unchanged at four studies: PASS",
            "Manual production acceptance covered CT and MR",
            "error-free browser console",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.closure)

    def test_scope_remains_truthful_and_non_clinical(self) -> None:
        self.assertIn("Clinical validation: NOT CLAIMED", self.h6)
        self.assertIn("does not claim clinical validation", self.closure)
        self.assertIn("separate phase", self.closure)
        self.assertNotIn("clinically validated", self.closure.lower())
        self.assertNotIn("diagnostically accurate", self.closure.lower())

    def test_status_documents_no_longer_leave_phase4_pending(self) -> None:
        self.assertIn("Phase 4 complete", self.readme)
        self.assertIn(RELEASE_SHA, self.readme)
        closure_record = self.h6.split("## Closure record", 1)[1]
        self.assertNotIn("PENDING", closure_record)
        self.assertEqual(closure_record.count("PASS"), 4)


if __name__ == "__main__":
    unittest.main()
