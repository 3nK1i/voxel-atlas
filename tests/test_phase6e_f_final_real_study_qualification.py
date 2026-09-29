from __future__ import annotations

from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/phase_history/PHASE6E_F_FINAL_REAL_STUDY_QUALIFICATION_AND_CLOSURE.md"
QUALIFIER = ROOT / "scripts/qualify_phase6e_f_real_study.py"
ARCH = ROOT / "scripts/check_phase6e_f_architecture.py"
RUNNER = ROOT / "scripts/run_phase6e_f_checks.sh"
PREVIOUS = ROOT / "scripts/run_phase6e_f_previous_regression.py"


class Phase6EFFinalRealStudyQualificationTests(unittest.TestCase):
    def test_phase6e_f_is_qualification_only(self):
        source = ARCH.read_text(encoding="utf-8")
        self.assertIn("QUALIFICATION_ONLY_ALLOWED_PATHS", source)
        self.assertIn("web/js/app.js", source)
        self.assertIn("web/js/reconstruction-surface-presentation.js", source)
        self.assertIn("web/js/reconstruction-combined-presentation.js", source)
        self.assertIn("backend/voxelatlas/volume_surfaces.py", source)
        self.assertIn("backend/voxelatlas/segmentation_surfaces.py", source)
        self.assertIn("PHASE6E_F_ARCHITECTURE=PASS", source)

    def test_real_study_qualifier_binds_ct_direct_surface_and_segmentation(self):
        source = QUALIFIER.read_text(encoding="utf-8")
        self.assertIn("VolumeRenderingService", source)
        self.assertIn("VolumeSurfaceService", source)
        self.assertIn("SegmentationLabelMapService", source)
        self.assertIn("SegmentationSurfaceService", source)
        self.assertIn("DEFAULT_CT_BONE_ISOVALUE_HU", source)
        self.assertIn("REFINED_SURFACE_QUALITY", source)
        self.assertIn("SOURCE_VOLUME=IMMUTABLE", source)
        self.assertIn("SOURCE_LABEL_MAP=IMMUTABLE", source)
        self.assertIn("GEOMETRY_CHAIN=PATIENT_LPS", source)
        self.assertIn("PHASE6E_F_REAL_STUDY_QUALIFICATION_OK=YES", source)

    def test_real_study_qualifier_preserves_surface_runtime_symlink_path(self):
        spec = importlib.util.spec_from_file_location("phase6e_f_qualifier", QUALIFIER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "python3.12"
            target.write_text("runtime", encoding="utf-8")
            runtime = root / "surface-runtime" / "bin" / "python"
            runtime.parent.mkdir(parents=True)
            runtime.symlink_to(target)

            normalized = module._runtime_executable_path(runtime)

            self.assertEqual(normalized, runtime.absolute())
            self.assertNotEqual(normalized, target.resolve())

    def test_real_study_qualifier_keeps_visual_judgment_manual(self):
        source = QUALIFIER.read_text(encoding="utf-8")
        self.assertIn("FIDELITY_VISUAL_REVIEW=MANUAL_REQUIRED", source)
        self.assertIn("PRESENTATION_VISUAL_REVIEW=MANUAL_REQUIRED", source)
        self.assertIn("COMBINED_THREE_LAYER_VISUAL_REVIEW=MANUAL_REQUIRED", source)
        self.assertIn("CLINICAL_VALIDATION=NOT_CLAIMED", source)

    def test_closure_doc_records_complete_manual_matrix_and_boundaries(self):
        doc = DOC.read_text(encoding="utf-8")
        for token in (
            "40937d706a7b54f3f23f882c9195ab5ed4992dc8",
            "Fidelity",
            "Presentation",
            "Volume",
            "Surface",
            "Combined",
            "Direct CT",
            "Segmentation",
            "300 HU",
            "Network",
            "opacity",
            "Patient LPS",
            "6F",
            "6G",
            "Clinical validation is not claimed",
        ):
            self.assertIn(token, doc)

    def test_runner_separates_automated_real_study_and_manual_gates(self):
        runner = RUNNER.read_text(encoding="utf-8")
        self.assertIn("PHASE6E_F_AUTOMATED_CHECKS_OK=YES", runner)
        self.assertIn("REAL_STUDY_QUALIFICATION=RUN_SEPARATELY", runner)
        self.assertIn("MANUAL_PRESENTATION_MATRIX=RUN_SEPARATELY", runner)
        self.assertIn("PHASE6E_CLOSURE=AFTER_REAL_STUDY_AND_MANUAL_PASS", runner)
        self.assertIn("PHASE6F_ADVANCED_INTERACTION=NOT_ENABLED", runner)
        self.assertIn("CLINICAL_VALIDATION=NOT_CLAIMED", runner)

    def test_previous_regression_excludes_current_phase_contracts(self):
        source = PREVIOUS.read_text(encoding="utf-8")
        self.assertIn("test_phase6e_f_final_real_study_qualification.", source)
        self.assertIn("test_phase6e_e_combined_mode_visual_balancing.", source)
        self.assertIn("PHASE6E_F_PREVIOUS_REGRESSION=PASS", source)


if __name__ == "__main__":
    unittest.main()
