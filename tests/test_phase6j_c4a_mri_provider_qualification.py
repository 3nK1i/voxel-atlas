"""C4A source-scoped MRI descriptor contract, synthetic qualification only."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.app import create_app
from voxelatlas.config import AppSettings, ConfigurationError, load_settings
from voxelatlas.mri_provider_qualification import (
    MRIProviderQualification, build_mri_model_descriptor, qualify_mri_provider,
)
from voxelatlas.mri_runtime_qualification import MRI_MAPPING_JSON_SHA256
from voxelatlas.segmentation import (
    SegmentationModelRegistry, SegmentationUnavailableError,
    SegmentationValidationError, build_default_segmentation_registry,
)


def runtime(**overrides):
    data = {"runtime_qualified": True, "execution_ready": False,
            "task": "total_mr", "task_modality": "MR", "task_class_count": 50,
            "task_mapping_sha256": MRI_MAPPING_JSON_SHA256,
            "totalsegmentator_version": "2.18.0"}
    data.update(overrides)
    return SimpleNamespace(**data)


class MRIProviderC4ATests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name)
        self.python = sys.executable
        self.good = dict(data_dir=self.data, python_executable=self.python,
                         runtime_qualifier=lambda _: runtime(),
                         installed_mapping_check=lambda _: True,
                         weights_check=lambda _: {"task": "total_mr", "mode_ids": {
                             "default": [850, 851], "fast": [852], "fastest": [853]},
                             "manifest_sha256": "a" * 64})

    def test_registration_is_distinct_unavailable_mr_identity(self):
        result = qualify_mri_provider(**self.good)
        self.assertEqual(result.status_code, "study_binding_pending")
        self.assertTrue(result.runtime_qualified and result.weights_qualified)
        self.assertFalse(result.source_qualified or result.prerequisites_qualified or result.execution_authorized)
        descriptor = build_mri_model_descriptor(data_dir=self.data, python_executable=self.python,
                                                qualification=result)
        self.assertEqual(descriptor.identity, ("totalsegmentator", "total_mr"))
        self.assertEqual(descriptor.supported_modalities, ("MR",))
        self.assertFalse(descriptor.available)
        self.assertEqual(descriptor.provider_version, "2.18.0")
        self.assertIn("execution", descriptor.availability_reason)
        registry = build_default_segmentation_registry()
        ct_before = registry.descriptor("totalsegmentator", "total").public_dict()
        registry.register_descriptor(descriptor)
        self.assertEqual(ct_before, registry.descriptor("totalsegmentator", "total").public_dict())
        self.assertEqual(len(registry.list_public()), 2)
        with self.assertRaises(SegmentationUnavailableError):
            registry.provider("totalsegmentator", "total_mr")
        with self.assertRaises(SegmentationValidationError):
            registry.register_descriptor(descriptor)

    def test_missing_config_and_invalid_runtime_fail_closed(self):
        result = qualify_mri_provider(data_dir=self.data, python_executable=None)
        self.assertEqual(result.status_code, "runtime_not_configured")
        self.assertFalse(result.execution_authorized)
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "runtime_qualifier": lambda _: runtime(task="total")})).status_code, "runtime_unqualified")
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "runtime_qualifier": lambda _: runtime(execution_ready=True)})).status_code, "runtime_unqualified")
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "runtime_qualifier": lambda _: runtime(task_mapping_sha256="0" * 64)})).status_code, "runtime_unqualified")
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "installed_mapping_check": lambda _: False})).status_code, "mapping_unqualified")
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "runtime_qualifier": lambda _: (_ for _ in ()).throw(RuntimeError("private-path"))
        })).reason, "MRI runtime is not qualified")

    def test_missing_or_changed_weights_fail_closed(self):
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "weights_check": lambda _: (_ for _ in ()).throw(ValueError("private-path"))
        })).status_code, "weights_unqualified")
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "weights_check": lambda _: {"task": "total", "mode_ids": {}, "manifest_sha256": "a" * 64}
        })).status_code, "weights_unqualified")
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "weights_check": lambda _: {"task": "total_mr", "mode_ids": {
                "default": [850, 851], "fast": [852], "fastest": [853]},
                "manifest_sha256": "not-sha"}
        })).status_code, "weights_unqualified")

    def test_source_specific_qualification_never_authorizes_worker(self):
        mr = SimpleNamespace(modality="MR")
        qualified = qualify_mri_provider(**(self.good | {
            "source": mr, "source_check": lambda _: (True, "qualified")}))
        self.assertTrue(qualified.prerequisites_qualified and qualified.source_qualified)
        self.assertFalse(qualified.execution_authorized)
        self.assertEqual(qualified.status_code, "prerequisites_qualified_execution_blocked")
        model = build_mri_model_descriptor(data_dir=self.data, python_executable=self.python,
                                           qualification=qualified)
        self.assertFalse(model.available)
        ct = SimpleNamespace(modality="CT")
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "source": ct, "source_check": lambda _: (True, "qualified")
        })).status_code, "source_unqualified")
        self.assertEqual(qualify_mri_provider(**(self.good | {
            "source": mr, "source_check": lambda _: (False, "private-data")
        })).reason, "The selected MRI source is not qualified")
        with self.assertRaises(ValueError):
            build_mri_model_descriptor(data_dir=self.data, python_executable=self.python,
                                       qualification=MRIProviderQualification("invalid", "invalid",
                                                                            execution_authorized=True))

    def test_app_registers_non_executable_mr_and_keeps_default_ct(self):
        settings = AppSettings(environment="test", session_secret="x" * 48,
            secure_cookies=False, session_cookie_name="va_c4a", allowed_hosts=("localhost", "127.0.0.1"),
            data_dir=self.data, max_upload_mib=512, auth_username=None, auth_password_hash=None,
            session_ttl_minutes=60)
        app = create_app(settings=settings)
        registry = app.state.segmentation_service.registry
        ct = registry.descriptor("totalsegmentator", "total")
        mr = registry.descriptor("totalsegmentator", "total_mr")
        self.assertEqual(ct.supported_modalities, ("CT",))
        self.assertFalse(ct.available)
        self.assertEqual(mr.supported_modalities, ("MR",))
        self.assertFalse(mr.available)
        self.assertEqual(len(app.state.segmentation_service.list_models()), 2)
        with self.assertRaises(SegmentationUnavailableError):
            registry.provider("totalsegmentator", "total_mr")

    def test_existing_ct_provider_is_preserved_when_configured(self):
        from voxelatlas.segmentation import SegmentationModelDescriptor, SegmentationExecutionRequirements
        ct = SegmentationModelDescriptor(
            provider_id="totalsegmentator", provider_version="2.18.0",
            model_id="total", model_version="2.18.0", display_name="CT total",
            task="multi_structure", capabilities=("anatomical_segmentation",),
            supported_modalities=("CT",), available=True, availability_reason=None,
            execution=SegmentationExecutionRequirements(supported_devices=("cuda",)),
        )
        provider = SimpleNamespace(descriptor=ct)
        settings = AppSettings(environment="test", session_secret="x" * 48,
            secure_cookies=False, session_cookie_name="va_c4a", allowed_hosts=("localhost", "127.0.0.1"),
            data_dir=self.data, max_upload_mib=512, auth_username=None, auth_password_hash=None,
            session_ttl_minutes=60, segmentation_worker_python=self.python)
        with patch("voxelatlas.app.TotalSegmentatorProvider", return_value=provider) as factory:
            app = create_app(settings=settings)
        factory.assert_called_once()
        registry = app.state.segmentation_service.registry
        self.assertIs(registry.provider("totalsegmentator", "total"), provider)
        self.assertTrue(registry.descriptor("totalsegmentator", "total").available)
        self.assertFalse(registry.descriptor("totalsegmentator", "total_mr").available)
        with self.assertRaises(SegmentationUnavailableError):
            registry.provider("totalsegmentator", "total_mr")

    def test_mri_runtime_configuration_is_separate_from_ct(self):
        with patch.dict("os.environ", {"VOXELATLAS_ENV": "test", "VOXELATLAS_MRI_PYTHON": self.python,
                                      "VOXELATLAS_SEGMENTATION_PYTHON": ""}, clear=True):
            settings = load_settings()
            self.assertEqual(settings.mri_worker_python, self.python)
            self.assertIsNone(settings.segmentation_worker_python)
        with patch.dict("os.environ", {"VOXELATLAS_ENV": "test",
                                      "VOXELATLAS_MRI_PYTHON": "bad\nvalue"}, clear=True):
            with self.assertRaises(ConfigurationError):
                load_settings()


if __name__ == "__main__":
    unittest.main()
