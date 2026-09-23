"""C2 offline, synthetic MRI assets only: no DICOM, GPU, network, or actual weights."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from voxelatlas.mri_weights_qualification import (  # noqa: E402
    MRIAssetError, MRI_DATASETS, download_commands, mri_environment, paths_for,
    prepare_mri_root, qualify_installed_mri_mapping, seal_mri_weights,
    verify_mri_weights,
)


class MRIAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "data"
        self.data.mkdir()
        self.paths = paths_for(self.data)

    def populate(self):
        prepare_mri_root(self.paths)
        for name in MRI_DATASETS.values():
            folder = self.paths.weights / name
            (folder / "nnUNetTrainer__nnUNetPlans__3d_fullres" / "fold_0").mkdir(parents=True)
            for key, content in (("dataset.json", b"{}"), ("plans.json", b"{}")):
                (folder / key).write_bytes(content)
            (folder / "nnUNetTrainer__nnUNetPlans__3d_fullres" / "fold_0" / "checkpoint_final.pth").write_bytes(b"synthetic checkpoint")

    def test_manifest_seals_all_four_and_detects_mutation(self):
        self.populate()
        sealed = seal_mri_weights(self.paths)
        self.assertEqual(sealed, verify_mri_weights(self.paths))
        self.assertEqual(sealed, seal_mri_weights(self.paths))
        self.assertEqual(sealed["task"], "total_mr")
        self.assertEqual(sealed["mode_ids"], {"default": [850, 851], "fast": [852], "fastest": [853]})
        self.assertEqual(len(sealed["datasets"]), 4)
        self.assertEqual(len(sealed["files"]), 12)
        self.assertNotIn(str(self.data), str(sealed))
        (self.paths.weights / MRI_DATASETS[850] / "plans.json").write_bytes(b"changed")
        with self.assertRaises(MRIAssetError):
            verify_mri_weights(self.paths)
        with self.assertRaises(MRIAssetError):
            seal_mri_weights(self.paths)

    def test_missing_extra_link_and_metadata_fail_closed(self):
        self.populate()
        missing = self.paths.weights / MRI_DATASETS[853] / "plans.json"
        missing.unlink()
        with self.assertRaises(MRIAssetError):
            seal_mri_weights(self.paths)
        missing.write_bytes(b"{}")
        (self.paths.weights / "Dataset291_ct").mkdir()
        with self.assertRaises(MRIAssetError):
            seal_mri_weights(self.paths)
        (self.paths.weights / "Dataset291_ct").rmdir()
        folder = self.paths.weights / MRI_DATASETS[851]
        (folder / "unsafe-link").symlink_to("/tmp/placeholder")
        with self.assertRaises(MRIAssetError):
            seal_mri_weights(self.paths)
        (folder / "unsafe-link").unlink()
        self.assertEqual(seal_mri_weights(self.paths)["task"], "total_mr")
        self.paths.manifest.write_text("{}", encoding="utf-8")
        with self.assertRaises(MRIAssetError):
            verify_mri_weights(self.paths)

    def test_missing_weights_and_ct_directory_isolation(self):
        ct = self.data / "segmentation" / "providers" / "totalsegmentator" / "2.18.0"
        ct.mkdir(parents=True)
        marker = ct / "ct-manifest.txt"
        marker.write_text("ct-unchanged", encoding="utf-8")
        with self.assertRaises(MRIAssetError):
            verify_mri_weights(self.paths)
        prepare_mri_root(self.paths)
        self.assertNotEqual(ct.parent, self.paths.root.parent)
        self.assertEqual(marker.read_text(encoding="utf-8"), "ct-unchanged")
        self.assertFalse(self.paths.manifest.exists())

    def test_downloader_contract_and_isolated_environment(self):
        commands = download_commands("/controlled/mri/bin/python")
        self.assertEqual([command[-1] for command in commands], ["total_mr", "total_fast_mr"])
        self.assertTrue(all(command[1:4] == ("-I", "-m", "totalsegmentator.bin.totalseg_download_weights") for command in commands))
        self.assertTrue(all("total" != command[-1] for command in commands))
        env = mri_environment(self.paths)
        self.assertEqual(env["nnUNet_results"], str(self.paths.weights))
        self.assertIn("totalsegmentator-mri", env["TOTALSEG_HOME_DIR"])
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")
        with self.assertRaises(MRIAssetError):
            download_commands("bad\npython")

    def test_installed_mapping_requires_exact_ids_folders_and_version(self):
        valid = {"schema": 1, "version": "2.18.0", "mode_ids": [[850, 851], 852, 853], "folders_match": True, "download_ids_match": True}
        calls = []
        def runner(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return SimpleNamespace(returncode=0, stdout=json.dumps(valid), stderr="private")
        self.assertTrue(qualify_installed_mri_mapping("/mri/bin/python", runner=runner))
        self.assertEqual(calls[0][0][:3], ["/mri/bin/python", "-I", "-c"])
        self.assertEqual(calls[0][1]["shell"], False)
        for update in ({"version": "2.19.0"}, {"mode_ids": [[291, 292], 852, 853]},
                       {"folders_match": False}, {"download_ids_match": False}, {"schema": True}):
            self.assertFalse(qualify_installed_mri_mapping("python", runner=lambda *a, **k: SimpleNamespace(
                returncode=0, stdout=json.dumps({**valid, **update}), stderr="private")))
        self.assertFalse(qualify_installed_mri_mapping("python", runner=lambda *a, **k: SimpleNamespace(
            returncode=1, stdout="", stderr="/private/patient")))
        def fail(*a, **k):
            raise subprocess.TimeoutExpired("python", 1)
        self.assertFalse(qualify_installed_mri_mapping("python", runner=fail))


if __name__ == "__main__":
    unittest.main()
