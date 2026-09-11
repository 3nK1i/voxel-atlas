from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase6FFFinalRealStudyInteractionQualificationTests(unittest.TestCase):
    def test_qualification_only_files_exist(self) -> None:
        expected = (
            "docs/phase_history/PHASE6F_F_FINAL_REAL_STUDY_INTERACTION_QUALIFICATION_AND_CLOSURE.md",
            "scripts/check_phase6f_f_architecture.py",
            "scripts/qualify_phase6f_f_real_study.py",
            "scripts/run_phase6f_f_checks.sh",
            "scripts/run_phase6f_f_previous_regression.py",
            "tests/test_phase6f_f_final_real_study_interaction_qualification.py",
        )
        for relative in expected:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_final_architecture_probe_covers_complete_interaction_stack(self) -> None:
        path = ROOT / "scripts/check_phase6f_f_architecture.py"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        for token in (
            "show-all",
            "hide-all",
            "restore-isolation",
            "structure.opacity",
            "clippingEnabled",
            "explodedSeparationMm",
            "MAX_ANATOMICAL_GROUP_EXPLODE_MM = 40",
            "accurate fallback",
            "requestReconstructionPresentationProfile",
            "applyCombinedPresentationBalance",
        ):
            self.assertIn(token, text)

    def test_real_study_qualifier_delegates_to_read_only_phase6e_source_gate(self) -> None:
        path = ROOT / "scripts/qualify_phase6f_f_real_study.py"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("qualify_phase6e_f_real_study.py", text)
        self.assertIn("PHASE6F_F_REAL_STUDY_SOURCE_GATE_OK=YES", text)
        for forbidden in (
            "write_text(",
            "write_bytes(",
            "unlink(",
            "rmdir(",
            "shutil.rmtree",
            "shutil.copy",
            "shutil.move",
            "requests.",
            "httpx.",
        ):
            self.assertNotIn(forbidden, text)

    def test_runner_filters_only_superseded_phase_boundary_assertions(self) -> None:
        path = ROOT / "scripts/run_phase6f_f_checks.sh"
        text = path.read_text(encoding="utf-8")
        self.assertIn("run_unittest_module_excluding", text)
        for method in (
            "test_phase6f_d_stays_inside_roadmap_boundary",
            "test_6fb_does_not_enable_later_interaction_features",
            "test_phase6f_a_foundation_keeps_later_interaction_features_out_of_scope",
        ):
            self.assertIn(method, text)
        self.assertIn("SUPERSEDED_ASSERTION_FILTER=PASS", text)

    def test_real_study_wrapper_preserves_surface_runtime_symlink_identity(self) -> None:
        path = ROOT / "scripts/qualify_phase6f_f_real_study.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn("surface_python = Path(args.surface_python).expanduser()", text)
        self.assertNotIn("expanduser().resolve()", text)

    def test_runner_is_qualification_only_and_uses_current_base(self) -> None:
        path = ROOT / "scripts/run_phase6f_f_checks.sh"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("4d589c2a44704d7be9039786d535b670461b8460", text)
        self.assertIn("QUALIFICATION_ONLY_DELTA=YES", text)
        self.assertIn("PHASE6F_PRODUCTION_RENDERING_CHANGES=NO", text)
        self.assertIn("MANUAL_INTERACTION_MATRIX=RUN_SEPARATELY", text)
        self.assertIn("DIRECT_CT_300_HU_SLAB_INVESTIGATION=DEFERRED_POST_PHASE6F", text)

    def test_manual_matrix_covers_all_phase6f_interactions_and_round_trips(self) -> None:
        doc = ROOT / "docs/phase_history/PHASE6F_F_FINAL_REAL_STUDY_INTERACTION_QUALIFICATION_AND_CLOSURE.md"
        self.assertTrue(doc.is_file())
        text = doc.read_text(encoding="utf-8")
        for token in (
            "Show / Hide / Isolate / Restore",
            "42%",
            "Follow Directional Cut",
            "Explode anatomy",
            "Fidelity",
            "Presentation",
            "Surface",
            "Combined",
            "accurate fallback",
            "MPR",
            "no geometry request",
        ):
            self.assertIn(token, text)

    def test_phase_boundary_keeps_direct_ct_slab_fix_and_phase6g_outside_6ff(self) -> None:
        doc = ROOT / "docs/phase_history/PHASE6F_F_FINAL_REAL_STUDY_INTERACTION_QUALIFICATION_AND_CLOSURE.md"
        text = doc.read_text(encoding="utf-8")
        self.assertIn("300-HU slab/occlusion", text)
        self.assertIn("after Phase 6F closure", text)
        self.assertIn("Phase 6G", text)
        self.assertIn("not clinical validation", text.lower())

    def test_previous_regression_wrapper_reuses_6fe_gate(self) -> None:
        path = ROOT / "scripts/run_phase6f_f_previous_regression.py"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("run_phase6f_e_previous_regression.py", text)
        self.assertIn("PHASE6F_F_PREVIOUS_REGRESSION=PASS", text)


if __name__ == "__main__":
    unittest.main()
