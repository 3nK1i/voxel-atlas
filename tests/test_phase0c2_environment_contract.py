from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "scripts/check_phase0c2_environment.py"
REQUIREMENTS_PATH = ROOT / "requirements/medical-processing.txt"

EXPECTED_REQUIREMENTS = {
    "numpy",
    "scipy",
    "scikit-image",
    "SimpleITK",
    "trimesh",
    "pyvista",
    "matplotlib",
}


def load_environment_module():
    spec = importlib.util.spec_from_file_location("phase0c2_environment", CHECK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load Phase 0C2 environment checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def requirement_names(text: str) -> set[str]:
    names: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        name = line
        for marker in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
            name = name.split(marker, 1)[0]
        names.add(name.strip())
    return names


class Phase0C2EnvironmentContractTests(unittest.TestCase):
    def test_medical_processing_manifest_covers_existing_script_imports(self) -> None:
        text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        self.assertEqual(requirement_names(text), EXPECTED_REQUIREMENTS)

    def test_manifest_is_intentionally_unpinned_until_environment_qualification(self) -> None:
        text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        dependency_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertTrue(dependency_lines)
        for line in dependency_lines:
            with self.subTest(line=line):
                self.assertNotIn("==", line)

    def test_environment_checker_declares_core_tool_contract(self) -> None:
        module = load_environment_module()
        self.assertGreaterEqual(module.MIN_PYTHON, (3, 11))
        self.assertGreaterEqual(module.MIN_NODE_MAJOR, 20)
        self.assertEqual(set(module.MEDICAL_IMPORTS), EXPECTED_REQUIREMENTS)

    def test_environment_checker_can_parse_semver_major(self) -> None:
        module = load_environment_module()
        self.assertEqual(module.parse_node_major("v22.23.1"), 22)
        self.assertEqual(module.parse_node_major("v20.0.0"), 20)
        with self.assertRaises(ValueError):
            module.parse_node_major("not-a-node-version")

    def test_current_full_runner_chains_preservation_regression(self) -> None:
        runner = (ROOT / "scripts/run_phase0c2_checks.sh").read_text(encoding="utf-8")
        self.assertIn("bash scripts/run_phase0c1_checks.sh", runner)
        self.assertIn("test_phase0c2_environment_contract.py", runner)
        self.assertIn("check_phase0c2_environment.py --profile core", runner)

    def test_environment_documentation_marks_medical_profile_as_optional(self) -> None:
        doc = (ROOT / "docs/development/ENVIRONMENT.md").read_text(encoding="utf-8")
        self.assertIn("--profile core", doc)
        self.assertIn("--profile medical", doc)
        self.assertIn("does not install", doc.lower())


if __name__ == "__main__":
    unittest.main()
