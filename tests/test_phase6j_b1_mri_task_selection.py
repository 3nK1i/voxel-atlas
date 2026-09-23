"""6J-B1: synthetic modality routing, MRI source, taxonomy, and CT isolation."""

from __future__ import annotations

from pathlib import Path
import sys
import threading
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.mri_task_contract import (  # noqa: E402
    MRI_TASK_CLASS_COUNT,
    MRI_TASK_ID,
    MRI_TASK_SOURCE_MAPPING_SHA256,
    TOTAL_SEGMENTATOR_MRI_STRUCTURES,
    model_for_source_modality,
    qualify_mri_canonical_descriptor,
)
from voxelatlas.segmentation_structures import (  # noqa: E402
    TOTAL_SEGMENTATOR_TOTAL_STRUCTURES,
    build_structure_catalog,
)
from voxelatlas.segmentation_workflow import SegmentationWorkflowService  # noqa: E402


def descriptor(modality="MR"):
    return {
        "ready": True, "modality": modality, "dtype": "float32",
        "axis_order": ["slice", "row", "column"], "shape": [2, 4, 6],
        "array_index_to_patient_lps": [
            [0.0, 0.0, 0.75, 10.0],
            [0.0, 0.5, 0.0, 20.0],
            [2.0, 0.0, 0.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }


class FakeJobs:
    def __init__(self, modality="CT", *, mr_available=False):
        self.sources = SimpleNamespace(latest=lambda: SimpleNamespace(study_id="a" * 32, modality=modality))
        self.models = [
            {"provider_id": "totalsegmentator", "model_id": "total", "available": True,
             "supported_modalities": ["CT"]},
        ]
        if mr_available:
            self.models.append({
                "provider_id": "totalsegmentator", "model_id": "total_mr", "available": True,
                "supported_modalities": ["MR"],
            })
        self.created = []

    def list_models(self):
        return self.models

    def list_jobs(self):
        return []

    def create_job(self, **kwargs):
        self.created.append(kwargs)
        return {"job_id": "seg-" + "c" * 32}


def workflow(modality="CT", *, mr_available=False):
    # Pure in-memory public workflow tests; no patient data or job execution.
    service = SegmentationWorkflowService.__new__(SegmentationWorkflowService)
    service.provider_id = "totalsegmentator"
    service.model_id = "total"
    service.job_service = FakeJobs(modality, mr_available=mr_available)
    service.label_map_service = SimpleNamespace(list=lambda **kwargs: [])
    service.python_executable = None
    service._lock = threading.RLock()
    return service


class MRIContractTests(unittest.TestCase):
    def test_pinned_50_label_identity_is_distinct_from_ct(self):
        self.assertEqual(MRI_TASK_ID, "total_mr")
        self.assertEqual(MRI_TASK_CLASS_COUNT, 50)
        self.assertEqual(sorted(TOTAL_SEGMENTATOR_MRI_STRUCTURES), list(range(1, 51)))
        self.assertEqual(len(set(TOTAL_SEGMENTATOR_MRI_STRUCTURES.values())), 50)
        self.assertEqual(TOTAL_SEGMENTATOR_MRI_STRUCTURES[10], "lung_left")
        self.assertEqual(TOTAL_SEGMENTATOR_TOTAL_STRUCTURES[10], "lung_upper_lobe_left")
        self.assertEqual(TOTAL_SEGMENTATOR_MRI_STRUCTURES[50], "brain")
        self.assertEqual(len(MRI_TASK_SOURCE_MAPPING_SHA256), 64)

    def test_canonical_mr_qualification_and_invalid_geometry(self):
        self.assertEqual(qualify_mri_canonical_descriptor(descriptor()),
                         (True, "MRI canonical volume representation is eligible for provider qualification"))
        for invalid in (
            descriptor("CT"),
            {**descriptor(), "ready": False},
            {**descriptor(), "dtype": "uint8"},
            {**descriptor(), "shape": [2, True, 4]},
            {**descriptor(), "array_index_to_patient_lps": [
                [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 1]]},
            {**descriptor(), "array_index_to_patient_lps": [
                [0, 0, float("nan"), 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]},
        ):
            with self.subTest(invalid=invalid):
                self.assertFalse(qualify_mri_canonical_descriptor(invalid)[0])

    def test_task_selection_keeps_ct_and_non_totalsegmentator_models(self):
        self.assertEqual(model_for_source_modality(provider_id="totalsegmentator", default_model_id="total", modality="CT"), "total")
        self.assertEqual(model_for_source_modality(provider_id="totalsegmentator", default_model_id="total", modality="MR"), "total_mr")
        self.assertEqual(model_for_source_modality(provider_id="other", default_model_id="whole-body", modality="MR"), "whole-body")

    def test_mr_taxonomy_names_groups_and_invalid_label(self):
        result = build_structure_catalog(provider_id="totalsegmentator", model_id="total_mr",
                                         present_labels=[10, 19, 24, 40, 50],
                                         palette={x: "#123abc" for x in (10, 19, 24, 40, 50)})
        self.assertEqual([s["name"] for s in result["structures"]],
                         ["lung_left", "vertebrae", "inferior_vena_cava", "gluteus_maximus_left", "brain"])
        self.assertEqual([s["group_id"] for s in result["structures"]],
                         ["respiratory", "spine", "cardiovascular", "muscles", "nervous_system"])
        with self.assertRaisesRegex(ValueError, "total_mr task contract"):
            build_structure_catalog(provider_id="totalsegmentator", model_id="total_mr",
                                    present_labels=[51], palette={51: "#123abc"})
        ct = build_structure_catalog(provider_id="totalsegmentator", model_id="total",
                                     present_labels=[10], palette={10: "#123abc"})
        self.assertEqual(ct["structures"][0]["name"], "lung_upper_lobe_left")

    def test_mr_stays_unavailable_without_mri_provider_and_ct_stays_ready(self):
        mr = workflow("MR")
        snapshot = mr.snapshot_latest()
        self.assertEqual(snapshot["model_id"], "total_mr")
        self.assertEqual(snapshot["state"], "unavailable")
        self.assertFalse(snapshot["can_start"])
        self.assertIn("not qualified", snapshot["provider_reason"])
        self.assertEqual(mr.job_service.created, [])
        ct = workflow("CT")
        ct_snapshot = ct.snapshot_latest()
        self.assertEqual(ct_snapshot["model_id"], "total")
        self.assertEqual(ct_snapshot["state"], "idle")
        self.assertTrue(ct_snapshot["can_start"])

    def test_mr_selects_only_mr_job_when_future_provider_is_registered(self):
        mr = workflow("MR", mr_available=True)
        start = mr.request_start()
        self.assertEqual(start.workflow["model_id"], "total_mr")
        self.assertEqual(len(mr.job_service.created), 1)
        self.assertEqual(mr.job_service.created[0]["model_id"], "total_mr")
        self.assertEqual(mr.job_service.created[0]["source_study_id"], "a" * 32)
        ct = workflow("CT", mr_available=True)
        ct.request_start()
        self.assertEqual(ct.job_service.created[0]["model_id"], "total")


if __name__ == "__main__":
    unittest.main()
