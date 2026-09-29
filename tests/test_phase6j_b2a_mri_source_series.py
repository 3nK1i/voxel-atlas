"""MRI qualification of the shared stored-source path; no DICOM pixels or ML."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.mri_source_qualification import (  # noqa: E402
    qualify_mri_stored_source, qualify_mri_study_manifest,
)
from voxelatlas.segmentation import CanonicalSegmentationSource, SegmentationUnavailableError  # noqa: E402
from voxelatlas.segmentation_workflow import SegmentationWorkflowService  # noqa: E402


def study_manifest(study_id: str, *, sample: bool = False) -> dict:
    uid = "1.2.840.10008.5.1.4.1.1.4.2026"
    return {
        "study_id": study_id, "reconstruction_series_uid": uid,
        "origin": {"kind": "sample"} if sample else None,
        "series": [{"series_instance_uid": uid, "modality": "MR", "instance_count": 3,
                    "geometry": {"reconstruction_ready": True, "dimensions": [4, 5, 3]}}],
        "volume": {
            "ready": True, "modality": "MR", "dtype": "float32",
            "axis_order": ["slice", "row", "column"], "shape": [3, 4, 5],
            "source_series_uid": uid, "source_instance_count": 3,
            "array_index_to_patient_lps": [[0, 0, 2, 10], [0, 1, 0, 20],
                                           [1, 0, 0, 30], [0, 0, 0, 1]],
        },
    }


class SourceTests(unittest.TestCase):
    def test_existing_sample_and_new_upload_share_same_qualified_contract(self):
        for sample in (True, False):
            with self.subTest(sample=sample):
                payload = study_manifest("a" * 32, sample=sample)
                valid, reason = qualify_mri_study_manifest(
                    payload, study_id="a" * 32, series_uid=payload["reconstruction_series_uid"])
                self.assertTrue(valid, reason)

    def test_incomplete_or_wrong_series_fail_closed(self):
        for alteration in (
            lambda p: p.update(reconstruction_series_uid="different"),
            lambda p: p["series"][0]["geometry"].update(reconstruction_ready=False),
            lambda p: p["series"][0].update(modality="CT"),
            lambda p: p["series"][0].update(instance_count=2),
            lambda p: p["series"][0]["geometry"].update(dimensions=[4, 5, 4]),
            lambda p: p["volume"].update(source_series_uid="different"),
            lambda p: p["volume"].update(dtype="uint16"),
            lambda p: p["volume"].update(array_index_to_patient_lps=[[0]*4]*4),
        ):
            payload = study_manifest("a" * 32)
            alteration(payload)
            with self.subTest(alteration=alteration):
                self.assertFalse(qualify_mri_study_manifest(
                    payload, study_id="a" * 32,
                    series_uid=study_manifest("a" * 32)["reconstruction_series_uid"])[0])

    def test_actual_source_blocks_unqualified_mri_job_and_preserves_ct(self):
        class Jobs:
            def __init__(self, source):
                self.sources = SimpleNamespace(latest=lambda: source)
                self.created = []
            def list_models(self):
                return [{"provider_id": "totalsegmentator", "model_id": model,
                         "available": True, "supported_modalities": [modality]}
                        for model, modality in (("total_mr", "MR"), ("total", "CT"))]
            def list_jobs(self):
                return []
            def create_job(self, **kwargs):
                self.created.append(kwargs)
                return {"job_id": "seg-" + "f" * 32}

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            payload = study_manifest("a" * 32, sample=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
            source = CanonicalSegmentationSource(
                study_id="a" * 32, study_instance_uid="1.2.3",
                source_series_uid=payload["reconstruction_series_uid"],
                modality="MR", volume_created_at_utc="2026-09-23T00:00:00Z",
                descriptor_sha256="0" * 64, artifact_sha256="1" * 64,
                manifest_path=path, study_dir=path.parent,
                volume_path=path.parent / "volume.npy",
                metadata_path=path.parent / "volume.json",
            )
            jobs = Jobs(source)
            service = SegmentationWorkflowService.__new__(SegmentationWorkflowService)
            service.provider_id, service.model_id = "totalsegmentator", "total"
            service.job_service = jobs
            service.label_map_service = SimpleNamespace(list=lambda **kwargs: [])
            service.python_executable = None
            service._lock = threading.RLock()
            snapshot = service.snapshot_latest()
            self.assertTrue(snapshot["source_qualified"])
            self.assertTrue(snapshot["can_start"])
            payload["series"][0]["geometry"]["reconstruction_ready"] = False
            path.write_text(json.dumps(payload), encoding="utf-8")
            snapshot = service.snapshot_latest()
            self.assertEqual(snapshot["state"], "unsupported")
            self.assertFalse(snapshot["can_start"])
            with self.assertRaises(SegmentationUnavailableError):
                service.request_start()
            self.assertEqual(jobs.created, [])
            jobs.sources = SimpleNamespace(latest=lambda: SimpleNamespace(study_id="a" * 32, modality="CT"))
            self.assertEqual(service.snapshot_latest()["model_id"], "total")
            self.assertTrue(service.snapshot_latest()["can_start"])

    def test_missing_or_corrupt_stored_manifest_is_not_qualified(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            source = SimpleNamespace(study_id="a" * 32, modality="MR",
                                     source_series_uid="1.2.3", manifest_path=path)
            self.assertFalse(qualify_mri_stored_source(source)[0])
            path.write_text("{", encoding="utf-8")
            self.assertFalse(qualify_mri_stored_source(source)[0])


if __name__ == "__main__":
    unittest.main()
