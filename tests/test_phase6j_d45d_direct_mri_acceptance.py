"""Phase 6J-D4.5D qualification-only Direct MR acceptance contracts."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DirectMRFinalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.backend = (ROOT / "backend/voxelatlas/volume_surfaces.py").read_text(encoding="utf-8")
        self.app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")
        self.qualifier = (ROOT / "scripts/qualify_phase6j_d45d_real_mri.py").read_text(encoding="utf-8")
        self.doc = (ROOT / "docs/phase_history/PHASE6J_D45D_DIRECT_MRI_FINAL_ACCEPTANCE.md").read_text(encoding="utf-8")
        self.phase6i_b2 = (ROOT / "tests/test_phase6i_b2_existing_segmentation_mode.py").read_text(encoding="utf-8")

    def test_neutral_backend_default_stays_050_while_035_is_sample_only(self):
        self.assertIn("DEFAULT_MR_NORMALIZED_ISOVALUE = 0.50", self.backend)
        self.assertIn("QUALIFICATION_ISOVALUES = (0.35, 0.50, 0.65)", self.qualifier)
        self.assertIn("0.35", self.doc)
        self.assertIn("not promoted to a universal MRI default", self.doc)

    def test_real_qualifier_is_read_only_and_checks_source_immutability(self):
        lower = self.qualifier.lower()
        for forbidden in (
            "unlink(", "rmtree(", "write_bytes(", "write_text(", "np.save(",
            "tofile(", 'open("w', "open('w",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lower)
        self.assertIn("SOURCE_VOLUME=IMMUTABLE", self.qualifier)
        self.assertIn("file_sha256(source.volume_path)", self.qualifier)
        self.assertIn("before_sha", self.qualifier)

    def test_acceptance_qualifies_three_distinct_bounded_patient_lps_surfaces(self):
        self.assertIn("QUALIFICATION_ISOVALUES = (0.35, 0.50, 0.65)", self.qualifier)
        self.assertIn("MAX_VOLUME_SURFACE_VERTICES", self.qualifier)
        self.assertIn("MAX_VOLUME_SURFACE_TRIANGLES", self.qualifier)
        self.assertIn("MAX_VOLUME_SURFACE_PAYLOAD_BYTES", self.qualifier)
        self.assertIn('surface.coordinate_system != "patient_lps"', self.qualifier)
        self.assertIn("Direct MR qualification isovalues did not produce distinct geometry payloads", self.qualifier)
        self.assertIn("DIRECT_MR_PAYLOADS_DISTINCT=PASS", self.qualifier)
        self.assertIn("DIRECT_MR_GEOMETRY_BUDGETS=PASS", self.qualifier)

    def test_mri_remains_nonsemantic_and_segmentation_independent(self):
        self.assertIn('MRI_SURFACE_INTENSITY_UNITS = "normalized_signal"', self.backend)
        self.assertIn('"segmentation_required": False', self.backend)
        self.assertIn('"semantic_identity": "none"', self.backend)
        self.assertIn("non-semantic visualization", self.app)
        self.assertIn("DIRECT_MR_SEGMENTATION_REQUIRED=NO", self.qualifier)

    def test_ct_backward_contract_is_explicitly_preserved(self):
        self.assertIn("DEFAULT_CT_BONE_ISOVALUE_HU = 300.0", self.backend)
        self.assertIn('this.descriptor?.source_modality !== "CT"', self.viewer)
        self.assertIn('state.volumeSurface.descriptor?.source_modality === "CT"', self.app)
        self.assertIn("CT backward sanity", self.doc)
        self.assertIn("300 HU", self.doc)


    def test_legacy_phase6j_cache_assertions_accept_qualified_d45c_suffix(self):
        probes = (
            "scripts/check_phase6j_b1_mri_workflow.mjs",
            "scripts/check_phase6j_b2b_mri_study_workflows.mjs",
        )
        for relative_path in probes:
            with self.subTest(path=relative_path):
                legacy_probe = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("phase6j-d45c-r\\d+", legacy_probe)


    def test_phase6i_b2_regression_scope_tracks_modality_aware_direct_volume_helper(self):
        self.assertIn("function ensureAutomaticDirectVolumeSurface(", self.app)
        self.assertIn("function ensureAutomaticDirectVolumeSurface(", self.phase6i_b2)
        self.assertNotIn("function ensureAutomaticDirectCtSurface(", self.phase6i_b2)

    def test_d45d_is_acceptance_not_product_redesign(self):
        self.assertIn("qualification-only acceptance step", self.doc)
        self.assertIn("does not redesign or modify", self.doc)
        self.assertIn("D4.5 closes only when all three independent gates pass", self.doc)
        self.assertIn("Phase 6J-D5 workflow/lifecycle integration remains the next step", self.doc)


if __name__ == "__main__":
    unittest.main()
