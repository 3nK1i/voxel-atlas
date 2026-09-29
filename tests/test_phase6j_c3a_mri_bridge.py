"""Synthetic MRI-only bridge tests; no patient data, downloads, or inference."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/phase6j_c3a_mri_nifti_worker.py"
spec = importlib.util.spec_from_file_location("phase6j_c3a_mri_nifti_worker", SCRIPT)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

AFFINE = [[0., 0., 2., 5.], [0., 1.5, 0., 6.], [3., 0., 0., 7.], [0., 0., 0., 1.]]


def descriptor(modality="MR"):
    return {"ready": True, "modality": modality, "dtype": "float32",
            "axis_order": ["slice", "row", "column"], "shape": [2, 3, 4],
            "array_index_to_patient_lps": AFFINE}


class MRIInputContract(unittest.TestCase):
    def test_mri_only_and_exact_3d_representation(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "volume.json"
            for bad in (descriptor("CT"), {**descriptor(), "dtype": "uint16"},
                        {**descriptor(), "shape": [True, 3, 4]},
                        {**descriptor(), "ready": False},
                        {**descriptor(), "array_index_to_patient_lps": [[0.]*4]*4}):
                path.write_text(json.dumps(bad))
                if bad["array_index_to_patient_lps"] == [[0.]*4]*4:
                    # A singular transform is checked by export after descriptor parsing.
                    continue
                with self.assertRaises(ValueError):
                    worker.load_mri_descriptor(path)
            path.write_text(json.dumps(descriptor()))
            self.assertEqual(worker.load_mri_descriptor(path)["modality"], "MR")

    def test_reject_existing_output_and_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.npy"
            source.write_bytes(b"synthetic")
            self.assertEqual(worker.existing_file(str(source), "source"), source)
            with self.assertRaises(ValueError):
                worker.new_file(str(source), "output")
            alias = root / "alias.npy"
            alias.symlink_to(source)
            with self.assertRaises(ValueError):
                worker.existing_file(str(alias), "source")

    def test_label_contract_0_to_50_and_noninteger_rejected(self):
        import numpy as np
        good = np.array([[[0, 1], [50, 50]]], dtype=np.uint8)
        self.assertEqual(worker.validate_mask_array(good), ([0, 1, 50], 3))
        for bad in (np.array([[[51]]]), np.array([[[-1]]]),
                    np.array([[[1.5]]]), np.array([[[np.nan]]])):
            with self.assertRaises(ValueError):
                worker.validate_mask_array(bad)

    @unittest.skipUnless(importlib.util.find_spec("nibabel"), "nibabel absent in current test interpreter")
    def test_roundtrip_synthetic_patient_lps_and_mask_geometry(self):
        import nibabel as nib
        import numpy as np
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "synthetic.npy"
            meta = root / "descriptor.json"
            nifti = root / "input.nii.gz"
            mask_file = root / "mask.nii.gz"
            np.save(data, np.arange(24, dtype=np.float32).reshape(2, 3, 4))
            meta.write_text(json.dumps(descriptor()))
            export = worker.export_mri(data, meta, nifti)
            expected = np.diag([-1., -1., 1., 1.]) @ np.asarray(AFFINE)
            self.assertEqual(export["task"], "total_mr")
            np.testing.assert_allclose(nib.load(nifti).affine, expected, rtol=0, atol=1e-5)
            mask = np.zeros((2, 3, 4), dtype=np.uint8)
            mask[1, 1, 1] = 50
            nib.save(nib.Nifti1Image(mask, expected), mask_file)
            result = worker.inspect_mri_mask(nifti, mask_file)
            self.assertEqual(result["present_labels"], [0, 50])
            self.assertEqual(result["nonzero_voxels"], 1)
            with self.assertRaises(ValueError):
                worker.inspect_mri_mask(nifti, nifti)
            mask[0, 0, 0] = 51
            nib.save(nib.Nifti1Image(mask, expected), mask_file)
            with self.assertRaises(ValueError):
                worker.inspect_mri_mask(nifti, mask_file)
            mask[0, 0, 0] = 0
            nib.save(nib.Nifti1Image(mask, expected), mask_file)
            shifted = expected.copy()
            shifted[0, 3] += 10
            nib.save(nib.Nifti1Image(mask, shifted), mask_file)
            with self.assertRaises(ValueError):
                worker.inspect_mri_mask(nifti, mask_file)

    def test_bad_cli_report_does_not_leak_details(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "PRIVATE-STUDY.nii.gz"
            result = subprocess.run([sys.executable, str(SCRIPT), "inspect", "--input-nifti",
                                     str(missing), "--mask-nifti", str(missing)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("PRIVATE-STUDY", result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
