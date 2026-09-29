"""Stabilization B1A: source-supported, read-only region association and login copy."""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load_diagnostic():
    path = ROOT / "scripts/diagnose_post6f_direct_ct_surface.py"
    spec = importlib.util.spec_from_file_location("voxelatlas_direct_ct_diagnostic_b1a", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StabilizationB1AContractTests(unittest.TestCase):
    def test_high_density_regions_link_to_distinct_broad_support_regions(self):
        diagnostic = load_diagnostic()
        source = np.full((8, 14, 16), -1000, dtype=np.float32)
        # Broad region A: larger, containing two separated high-HU areas.
        source[1:7, 1:9, 1:9] = 0
        source[2:5, 2:7, 2:6] = 450
        source[5:7, 7:8, 7:8] = 450
        # Broad region B: disjoint, thin, externally positioned high-HU sheet.
        source[1:7, 11:13, 2:14] = 0
        source[1:7, 11:13, 3:13] = 450
        original = source.copy()
        report = diagnostic.associate_isovalue_components(
            source, isovalue=300, body_threshold=-500, maximum=12,
        )
        self.assertEqual(report["high_component_count"], 3)
        self.assertEqual(report["body_support_component_count"], 2)
        associations = report["associations"]
        self.assertEqual(len(associations), 3)
        self.assertEqual(associations[0]["body_support_rank"], 2)
        self.assertEqual(associations[1]["body_support_rank"], 1)
        self.assertEqual(associations[2]["body_support_rank"], 1)
        self.assertTrue(all(item["association"] == "unique" for item in associations))
        self.assertTrue(np.array_equal(source, original), "Diagnostic must not alter its source")

    def test_invalid_threshold_order_fails_closed(self):
        diagnostic = load_diagnostic()
        volume = np.zeros((3, 3, 3), dtype=np.float32)
        for high, body in ((-500, 300), (300, 300), (float("nan"), -500)):
            with self.subTest(high=high, body=body):
                with self.assertRaises(ValueError):
                    diagnostic.associate_isovalue_components(
                        volume, isovalue=high, body_threshold=body, maximum=12,
                    )

    def test_no_anatomical_classification_or_removal_is_claimed(self):
        diagnostic = load_diagnostic()
        volume = np.full((5, 5, 5), -1000, dtype=np.float32)
        volume[1:4, 1:4, 1:4] = 500
        result = diagnostic.associate_isovalue_components(
            volume, isovalue=300, body_threshold=-500, maximum=12,
        )
        self.assertEqual(result["high_component_count"], 1)
        self.assertEqual(result["body_support_component_count"], 1)
        self.assertEqual(result["associations"][0]["body_support_rank"], 1)
        self.assertNotIn("patient", result)
        self.assertNotIn("remove", result)

    def test_cli_reports_associations_on_synthetic_memmap_without_source_change(self):
        diagnostic = load_diagnostic()
        with tempfile.TemporaryDirectory() as tmp:
            studies = Path(tmp) / "studies" / ("a" * 32)
            (studies / "derived").mkdir(parents=True)
            source = np.full((8, 14, 16), -1000, dtype=np.float32)
            source[1:7, 1:9, 1:9] = 0
            source[2:5, 2:7, 2:6] = 450
            source[1:7, 11:13, 2:14] = 0
            source[1:7, 11:13, 3:13] = 450
            np.save(studies / "derived/volume.npy", source, allow_pickle=False)
            (studies / "manifest.json").write_text(json.dumps({
                "volume": {
                    "ready": True,
                    "artifact_path": "derived/volume.npy",
                    "shape": list(source.shape),
                    "array_index_to_patient_lps": np.eye(4).tolist(),
                },
            }))
            artifact = studies / "derived/volume.npy"
            before = artifact.read_bytes()
            output = io.StringIO()
            with patch.object(sys, "argv", [
                "diagnose_post6f_direct_ct_surface.py",
                "--data-dir", tmp,
                "--study-id", "a" * 32,
                "--max-components", "2",
            ]), redirect_stdout(output):
                self.assertEqual(diagnostic.main(), 0)
            self.assertIn("COMPONENT_ASSOCIATION high_rank=1", output.getvalue())
            self.assertIn("body_support_rank=2", output.getvalue())
            self.assertIn("COMPONENT_ANATOMICAL_CLASSIFICATION=NOT_CLAIMED", output.getvalue())
            self.assertIn("ARBITRARY_LARGEST_COMPONENT_REMOVAL=NOT_APPLIED", output.getvalue())
            self.assertEqual(artifact.read_bytes(), before)

    def test_login_heading_is_product_name_without_auth_copy_change(self):
        html = (ROOT / "web/login.html").read_text(encoding="utf-8")
        self.assertIn('<h1 id="loginTitle">VoxelAtlas</h1>', html)
        self.assertIn('<span id="loginSubmitLabel">Login</span>', html)
        self.assertIn('id="loginForm"', html)
        self.assertIn('id="loginSubtitle"', html)


if __name__ == "__main__":
    unittest.main()
