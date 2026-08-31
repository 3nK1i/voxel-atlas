from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "scripts/check_phase0c1_baseline_integrity.py"


def load_integrity_module():
    spec = importlib.util.spec_from_file_location("phase0c1_integrity", CHECK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load Phase 0C1 integrity checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Phase0C1BaselineContractTests(unittest.TestCase):
    def test_preserved_prototype_fingerprints_match_handoff(self) -> None:
        module = load_integrity_module()
        self.assertEqual(module.verify_preserved_files(), [])

    def test_current_web_baseline_has_required_assets(self) -> None:
        required = (
            ROOT / "web/index.html",
            ROOT / "web/css/styles.css",
            ROOT / "web/js/app.js",
            ROOT / "web/assets/models/skull.glb",
            ROOT / "web/assets/models/skull_full.glb",
            ROOT / "web/assets/models/skull_open.glb",
        )
        for path in required:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"missing {path.relative_to(ROOT)}")
                self.assertGreater(path.stat().st_size, 0)

    def test_current_glb_assets_have_glb_magic(self) -> None:
        glbs = (
            ROOT / "web/assets/models/skull.glb",
            ROOT / "web/assets/models/skull_full.glb",
            ROOT / "web/assets/models/skull_open.glb",
            ROOT / "prototypes/v2b3a/assets/skull_full.glb",
            ROOT / "prototypes/v2b3b/assets/skull_full.glb",
        )
        for path in glbs:
            with self.subTest(path=path):
                with path.open("rb") as handle:
                    self.assertEqual(handle.read(4), b"glTF")

    def test_gitignore_protects_raw_medical_data_and_secrets(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for entry in ("data/", "*.dcm", "*.nii", "*.nii.gz", "*.nrrd", ".env"):
            with self.subTest(entry=entry):
                self.assertIn(entry, gitignore)

    def test_legacy_prototype_smoke_scripts_remain_present(self) -> None:
        for relative in (
            "scripts/check_v2b3a_prototype.py",
            "scripts/check_v2b3b_prototype.py",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())


if __name__ == "__main__":
    unittest.main()
