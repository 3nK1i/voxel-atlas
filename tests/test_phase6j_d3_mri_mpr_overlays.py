"""Phase 6J-D3: existing persisted MRI label maps become MPR-presentable.

Synthetic only: no patient data, provider execution, MRI inference, or production import.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from voxelatlas.dicom_mpr import CanonicalMprService
from voxelatlas.segmentation_overlays import SegmentationOverlayService
from voxelatlas.segmentation_workflow import SegmentationWorkflowService
from test_phase5d_synchronized_mpr_segmentation_overlay import (
    AFFINE,
    LABEL_MAP_ID,
    STUDY_ID,
    StubLabelMapService,
    write_volume,
)
from test_phase6j_c4c_mri_workflow_presentation import (
    UID,
    Jobs,
    record,
    source_fixture,
)


MRI_MAP_ID = "map-" + "d" * 32
TERMINAL_SHA = "9" * 64


def mri_map(source, job_id: str, **overrides) -> dict[str, object]:
    descriptor: dict[str, object] = {
        "label_map_id": MRI_MAP_ID,
        "state": "ready",
        "source_study_id": source.study_id,
        "source_study_instance_uid": source.study_instance_uid,
        "source_series_uid": source.source_series_uid,
        "source_modality": "MR",
        "source_volume_descriptor_sha256": source.descriptor_sha256,
        "source_volume_artifact_sha256": source.artifact_sha256,
        "segmentation_job_id": job_id,
        "segmentation_terminal_provenance_sha256": TERMINAL_SHA,
        "provider_id": "totalsegmentator",
        "provider_version": "2.18.0",
        "model_id": "total_mr",
        "model_version": "2.18.0",
        "task": "total_mr",
        "class_count": 50,
        "present_labels": [0, 50],
        "clinical_validation": "not_claimed",
    }
    descriptor.update(overrides)
    return descriptor


def workflow_service(root: Path, maps: list[dict[str, object]]):
    source = source_fixture(root)
    jobs = Jobs(source)
    service = SegmentationWorkflowService.__new__(SegmentationWorkflowService)
    service.provider_id = "totalsegmentator"
    service.model_id = "total"
    service.job_service = jobs
    service.label_map_service = SimpleNamespace(list=lambda **_kwargs: list(maps))
    service.python_executable = "/dummy/ct/import"
    service._lock = threading.RLock()
    service._finalizing_jobs = set()
    service.mri_presentation_only = True
    return source, jobs, service


class MRIWorkflowPresentationTests(unittest.TestCase):
    def test_source_bound_persisted_mri_map_becomes_available_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, jobs, service = workflow_service(root, [])
            job = record(source, state="succeeded")
            job["terminal_provenance_sha256"] = TERMINAL_SHA
            jobs.records = [job]
            service.label_map_service = SimpleNamespace(
                list=lambda **_kwargs: [mri_map(source, str(job["job_id"]))]
            )

            snapshot = service.snapshot_latest()

        self.assertEqual(snapshot["state"], "available")
        self.assertEqual(snapshot["label_map_id"], MRI_MAP_ID)
        self.assertEqual(snapshot["present_label_count"], 1)
        self.assertTrue(snapshot["mri_label_map_ready"])
        self.assertTrue(snapshot["can_use"])
        self.assertFalse(snapshot["can_start"])
        self.assertFalse(snapshot["mri_execution_authorized"])
        self.assertTrue(snapshot["presentation_only"])
        self.assertEqual(jobs.created, [])
        self.assertEqual(jobs.executed, [])

    def test_mri_map_requires_exact_current_source_job_and_total_mr_contract(self):
        mismatches = (
            {"source_study_id": "b" * 32},
            {"source_study_instance_uid": "9.9.9"},
            {"source_series_uid": "1.2.999"},
            {"source_modality": "CT"},
            {"source_volume_descriptor_sha256": "e" * 64},
            {"source_volume_artifact_sha256": "e" * 64},
            {"segmentation_job_id": "seg-" + "2" * 32},
            {"segmentation_terminal_provenance_sha256": "8" * 64},
            {"provider_id": "other"},
            {"model_id": "total"},
            {"task": "total"},
            {"class_count": 117},
            {"clinical_validation": "claimed"},
        )
        for override in mismatches:
            with self.subTest(override=override), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source, jobs, service = workflow_service(root, [])
                job = record(source, state="succeeded")
                job["terminal_provenance_sha256"] = TERMINAL_SHA
                jobs.records = [job]
                service.label_map_service = SimpleNamespace(
                    list=lambda **_kwargs: [mri_map(source, str(job["job_id"]), **override)]
                )

                snapshot = service.snapshot_latest()

                self.assertEqual(snapshot["state"], "output_ready")
                self.assertFalse(snapshot["mri_label_map_ready"])
                self.assertFalse(snapshot["can_use"] or snapshot["can_start"])
                self.assertIsNone(snapshot["label_map_id"])

    def test_active_matching_mri_job_keeps_status_precedence_over_persisted_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, jobs, service = workflow_service(root, [])
            succeeded = record(source, state="succeeded")
            succeeded["terminal_provenance_sha256"] = TERMINAL_SHA
            active = record(source, state="running", job_id="seg-" + "3" * 32)
            active["terminal_provenance_sha256"] = "7" * 64
            jobs.records = [active, succeeded]
            service.label_map_service = SimpleNamespace(
                list=lambda **_kwargs: [mri_map(source, str(succeeded["job_id"]))]
            )

            snapshot = service.snapshot_latest()

        self.assertEqual(snapshot["state"], "running")
        self.assertFalse(snapshot["mri_label_map_ready"])
        self.assertFalse(snapshot["can_use"])
        self.assertIsNone(snapshot["label_map_id"])


class MRIOverlayReuseTests(unittest.TestCase):
    def test_total_mr_map_reuses_patient_lps_mpr_overlay_and_mri_taxonomy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            study_dir = root / "studies" / STUDY_ID
            volume_json = study_dir / "derived" / "volume.json"
            volume = json.loads(volume_json.read_text(encoding="utf-8"))
            volume["modality"] = "MR"
            volume["intensity_units"] = "arbitrary"
            volume_json.write_text(json.dumps(volume), encoding="utf-8")
            manifest_path = study_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["modalities"] = ["MR"]
            manifest["study_description"] = "Synthetic MR"
            manifest["volume"] = volume
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            labels = np.zeros((3, 2, 4), dtype=np.uint16)
            labels[1, 0, 1] = 50
            map_dir = root / "segmentation" / "label-maps" / LABEL_MAP_ID
            map_dir.mkdir(parents=True)
            np.save(map_dir / "labels.npy", labels, allow_pickle=False)
            descriptor = {
                "label_map_id": LABEL_MAP_ID,
                "state": "ready",
                "source_study_id": STUDY_ID,
                "source_modality": "MR",
                "provider_id": "totalsegmentator",
                "provider_version": "2.18.0",
                "model_id": "total_mr",
                "model_version": "2.18.0",
                "coordinate_system": "patient_lps",
                "representation": "label_map",
                "artifact_format": "npy",
                "artifact_sha256": "a" * 64,
                "artifact_bytes": int(labels.nbytes),
                "shape": [3, 2, 4],
                "dtype": "uint16",
                "axis_order": ["slice", "row", "column"],
                "array_index_to_patient_lps": AFFINE,
                "present_labels": [0, 50],
                "nonzero_voxels": 1,
                "clinical_validation": "not_claimed",
            }
            service = SegmentationOverlayService(
                data_dir=root,
                mpr_service=CanonicalMprService(data_dir=root),
                label_map_service=StubLabelMapService(descriptor),
            )

            overlay = service.descriptor_latest(label_map_id=LABEL_MAP_ID)
            image = service.render_latest("axial", index=1, label_map_id=LABEL_MAP_ID)

        self.assertTrue(overlay["ready"])
        self.assertEqual(overlay["source_modality"], "MR")
        self.assertEqual(overlay["model_id"], "total_mr")
        self.assertEqual(overlay["present_labels"], [50])
        structures = overlay["structure_catalog"]["structures"]
        self.assertEqual(len(structures), 1)
        self.assertEqual(structures[0]["name"], "brain")
        self.assertEqual(structures[0]["display_name"], "Brain")
        self.assertEqual(structures[0]["group_id"], "nervous_system")
        rgba = np.frombuffer(image.pixels, dtype=np.uint8).reshape(image.height, image.width, 4)
        self.assertEqual(int(np.count_nonzero(rgba[..., 3])), 1)


if __name__ == "__main__":
    unittest.main()
