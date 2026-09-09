from __future__ import annotations

from pathlib import Path
import unittest

from voxelatlas.segmentation import SegmentationValidationError
from voxelatlas.segmentation_qualification import (
    Phase5QualificationBudget,
    validate_phase5_closure,
)
from voxelatlas.segmentation_surfaces import SegmentationSurface
from voxelatlas.segmentation_overlays import SegmentationOverlayImage


ROOT = Path(__file__).resolve().parents[1]


class Phase5GSegmentationClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.label_map = {
            "label_map_id": "map-" + "1" * 32,
            "source_study_id": "2" * 32,
            "source_modality": "CT",
            "provider_id": "totalsegmentator",
            "provider_version": "2.18.0",
            "model_id": "total",
            "model_version": "2.18.0",
            "artifact_sha256": "3" * 64,
            "coordinate_system": "patient_lps",
            "shape": [3, 4, 5],
            "array_index_to_patient_lps": [
                [0.0, 0.0, 2.0, -10.0],
                [0.0, 1.0, 0.0, 20.0],
                [3.0, 0.0, 0.0, 30.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "present_labels": [0, 91],
            "nonzero_voxels": 7,
            "resampled": False,
            "interpolation": "none",
            "clinical_validation": "not_claimed",
        }
        self.overlay = {
            "ready": True,
            "label_map_id": self.label_map["label_map_id"],
            "label_map_sha256": self.label_map["artifact_sha256"],
            "source_study_id": self.label_map["source_study_id"],
            "coordinate_system": "patient_lps",
            "sampling": "nearest_neighbor",
            "present_label_count": 1,
            "clinical_validation": "not_claimed",
        }
        self.mpr = {
            "ready": True,
            "modality": "CT",
            "patient_bounds_lps_mm": {
                "x": [-10.0, -2.0], "y": [20.0, 23.0], "z": [30.0, 36.0]
            },
            "planes": {
                "axial": {"slice_count": 4, "image_width": 5, "image_height": 3},
                "coronal": {"slice_count": 5, "image_width": 5, "image_height": 4},
                "sagittal": {"slice_count": 6, "image_width": 4, "image_height": 3},
            },
        }
        self.images = {
            name: SegmentationOverlayImage(
                plane=name,
                index=1,
                position_mm=0.0,
                width=int(plane["image_width"]),
                height=int(plane["image_height"]),
                label_map_id=self.label_map["label_map_id"],
                pixels=b"\0" * (int(plane["image_width"]) * int(plane["image_height"]) * 4),
            )
            for name, plane in self.mpr["planes"].items()
        }
        self.surface = SegmentationSurface(
            label_map_id=self.label_map["label_map_id"],
            label_id=91,
            quality="preview",
            extraction="voxel_boundary_faces",
            coordinate_system="patient_lps",
            stride=1,
            vertex_count=8,
            triangle_count=12,
            bounds_lps_mm=(-10.0, 20.0, 30.0, -2.0, 23.0, 36.0),
            payload_sha256="4" * 64,
            payload=b"mesh",
        )
        self.quality = {
            "label_map_id": self.label_map["label_map_id"],
            "label_map_sha256": self.label_map["artifact_sha256"],
            "source_study_id": self.label_map["source_study_id"],
            "label_id": 91,
            "voxel_count": 7,
            "warning_count": 3,
            "source_label_map": "immutable",
            "clinical_validation": "not_claimed",
        }

    def qualify(self, **changes):
        values = {
            "label_map": self.label_map,
            "overlay_descriptor": self.overlay,
            "mpr_descriptor": self.mpr,
            "overlay_images": self.images,
            "surface": self.surface,
            "quality_report": self.quality,
            "timings_seconds": {"metadata": 0.01, "overlays": 0.02, "surface": 0.03},
            "model_candidates": [self.label_map],
            "budget": Phase5QualificationBudget(1.0, 1.0, 1.0),
        }
        values.update(changes)
        return validate_phase5_closure(**values)

    def test_complete_patient_lps_chain_qualifies_without_clinical_claim(self) -> None:
        report = self.qualify()
        self.assertEqual(report["status"], "qualified")
        self.assertEqual(report["geometry_chain"], "pass")
        self.assertEqual(report["overlay_plane_count"], 3)
        self.assertEqual(report["model_comparison_candidate_count"], 1)
        self.assertEqual(report["model_comparison_ranking"], "not_claimed")
        self.assertEqual(report["source_label_map"], "immutable")
        self.assertEqual(report["clinical_validation"], "not_claimed")

    def test_cross_study_overlay_is_rejected(self) -> None:
        overlay = dict(self.overlay, source_study_id="5" * 32)
        with self.assertRaisesRegex(SegmentationValidationError, "study identity"):
            self.qualify(overlay_descriptor=overlay)

    def test_surface_outside_patient_bounds_is_rejected(self) -> None:
        surface = SegmentationSurface(**{
            **self.surface.__dict__,
            "bounds_lps_mm": (-100.0, 20.0, 30.0, -2.0, 23.0, 36.0),
        })
        with self.assertRaisesRegex(SegmentationValidationError, "surface bounds"):
            self.qualify(surface=surface)

    def test_surface_may_reach_the_canonical_half_voxel_cell_envelope(self) -> None:
        surface = SegmentationSurface(**{
            **self.surface.__dict__,
            "bounds_lps_mm": (-11.0, 19.5, 28.5, -1.0, 23.5, 37.5),
        })
        report = self.qualify(surface=surface)
        self.assertEqual(report["geometry_chain"], "pass")
        self.assertEqual(report["surface_containment"], "canonical_voxel_cell_bounds")

    def test_wrong_overlay_dimensions_are_rejected(self) -> None:
        images = dict(self.images)
        images["axial"] = SegmentationOverlayImage(**{
            **images["axial"].__dict__, "width": 99
        })
        with self.assertRaisesRegex(SegmentationValidationError, "overlay dimensions"):
            self.qualify(overlay_images=images)

    def test_performance_budget_is_enforced(self) -> None:
        with self.assertRaisesRegex(SegmentationValidationError, "performance budget"):
            self.qualify(timings_seconds={"metadata": 2.0, "overlays": 0.02, "surface": 0.03})

    def test_model_candidates_are_deterministic_and_never_ranked(self) -> None:
        second = dict(
            self.label_map,
            label_map_id="map-" + "6" * 32,
            provider_id="provider-b",
            model_id="model-b",
        )
        report = self.qualify(model_candidates=[second, self.label_map])
        self.assertEqual(report["model_comparison_candidate_count"], 2)
        self.assertEqual(
            [item["provider_id"] for item in report["model_comparison_candidates"]],
            ["provider-b", "totalsegmentator"],
        )
        self.assertEqual(report["model_comparison_ranking"], "not_claimed")


class Phase5GUIContractTests(unittest.TestCase):
    def test_phase5g_ui_contract_checker(self) -> None:
        import subprocess

        result = subprocess.run(
            ["node", "scripts/check_phase5g_ui.mjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
