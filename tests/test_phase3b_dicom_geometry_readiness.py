from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.dicom_geometry import GeometryInstance, qualify_series_geometry
from voxelatlas.dicom_ingestion import (
    DicomHeader,
    DicomIngestionService,
    DicomStudyRepository,
)


class Part:
    def __init__(self, filename: str, payload: bytes):
        from io import BytesIO

        self.filename = filename
        self.file = BytesIO(payload)


def geometry_instance(
    name: str,
    z: float,
    *,
    instance_number: int | None = None,
    rows: int = 512,
    columns: int = 512,
    pixel_spacing: tuple[float, float] = (0.5, 0.5),
    orientation: tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
) -> GeometryInstance:
    return GeometryInstance(
        stored_filename=name,
        rows=rows,
        columns=columns,
        pixel_spacing=pixel_spacing,
        image_position_patient=(0.0, 0.0, z),
        image_orientation_patient=orientation,
        instance_number=instance_number,
        number_of_frames=1,
    )


def fake_header_reader(path: Path) -> DicomHeader | None:
    # study|series|sop|instance|z|rows|cols|spacing
    parts = path.read_bytes().decode("ascii").split("|")
    if len(parts) != 8:
        return None
    study, series, sop, instance, z, rows, cols, spacing = parts
    return DicomHeader(
        study_instance_uid=study,
        series_instance_uid=series,
        sop_instance_uid=sop,
        modality="CT",
        series_number=1,
        series_description="Head thin",
        manufacturer="Scanner",
        rows=int(rows),
        columns=int(cols),
        pixel_spacing=(float(spacing), float(spacing)),
        slice_thickness=1.0,
        spacing_between_slices=1.0,
        instance_number=int(instance),
        image_position_patient=(0.0, 0.0, float(z)),
        image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        number_of_frames=1,
    )


class Phase3BDicomGeometryReadinessTests(unittest.TestCase):
    def test_geometric_ordering_uses_patient_position_not_instance_number(self) -> None:
        result = qualify_series_geometry(
            [
                geometry_instance("slice-c.dcm", 2.0, instance_number=1),
                geometry_instance("slice-a.dcm", 0.0, instance_number=99),
                geometry_instance("slice-b.dcm", 1.0, instance_number=50),
            ]
        )
        self.assertTrue(result.reconstruction_ready)
        self.assertEqual(
            result.ordered_instance_filenames,
            ("slice-a.dcm", "slice-b.dcm", "slice-c.dcm"),
        )
        self.assertEqual(result.dimensions, (512, 512, 3))
        self.assertEqual(result.spacing_mm, (0.5, 0.5, 1.0))
        self.assertEqual(result.orientation_label, "axial")
        self.assertEqual(result.slice_normal, (0.0, 0.0, 1.0))

    def test_oblique_orientation_is_supported_when_geometry_is_consistent(self) -> None:
        # Row along X; column tilted equally through Y/Z.
        orientation = (1.0, 0.0, 0.0, 0.0, 2**-0.5, 2**-0.5)
        result = qualify_series_geometry(
            [
                GeometryInstance(
                    stored_filename=f"slice-{index}.dcm",
                    rows=256,
                    columns=256,
                    pixel_spacing=(0.8, 0.8),
                    image_position_patient=(0.0, -index * 2**-0.5, index * 2**-0.5),
                    image_orientation_patient=orientation,
                    instance_number=index,
                    number_of_frames=1,
                )
                for index in range(3)
            ]
        )
        self.assertTrue(result.reconstruction_ready)
        self.assertEqual(result.orientation_label, "oblique")
        self.assertAlmostEqual(result.slice_spacing_mm or 0.0, 1.0, places=6)

    def test_inconsistent_matrix_blocks_reconstruction_readiness(self) -> None:
        result = qualify_series_geometry(
            [
                geometry_instance("a.dcm", 0.0),
                geometry_instance("b.dcm", 1.0, rows=256),
            ]
        )
        self.assertFalse(result.reconstruction_ready)
        self.assertIn("inconsistent_matrix", {issue.code for issue in result.issues})

    def test_inconsistent_orientation_blocks_reconstruction_readiness(self) -> None:
        result = qualify_series_geometry(
            [
                geometry_instance("a.dcm", 0.0),
                geometry_instance(
                    "b.dcm",
                    1.0,
                    orientation=(0.0, 1.0, 0.0, 1.0, 0.0, 0.0),
                ),
            ]
        )
        self.assertFalse(result.reconstruction_ready)
        self.assertIn("inconsistent_orientation", {issue.code for issue in result.issues})

    def test_in_plane_slice_drift_blocks_simple_volume_reconstruction(self) -> None:
        result = qualify_series_geometry(
            [
                geometry_instance("a.dcm", 0.0),
                GeometryInstance(
                    stored_filename="b.dcm",
                    rows=512,
                    columns=512,
                    pixel_spacing=(0.5, 0.5),
                    image_position_patient=(0.25, 0.0, 1.0),
                    image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
                    instance_number=2,
                    number_of_frames=1,
                ),
            ]
        )
        self.assertFalse(result.reconstruction_ready)
        self.assertIn("in_plane_slice_drift", {issue.code for issue in result.issues})

    def test_duplicate_geometric_position_blocks_reconstruction_readiness(self) -> None:
        result = qualify_series_geometry(
            [geometry_instance("a.dcm", 0.0), geometry_instance("b.dcm", 0.0)]
        )
        self.assertFalse(result.reconstruction_ready)
        self.assertIn("duplicate_slice_position", {issue.code for issue in result.issues})

    def test_irregular_spacing_and_large_gap_are_reported(self) -> None:
        result = qualify_series_geometry(
            [
                geometry_instance("a.dcm", 0.0),
                geometry_instance("b.dcm", 1.0),
                geometry_instance("c.dcm", 2.0),
                geometry_instance("d.dcm", 5.0),
            ]
        )
        self.assertFalse(result.reconstruction_ready)
        codes = {issue.code for issue in result.issues}
        self.assertIn("irregular_slice_spacing", codes)
        self.assertIn("slice_gap_detected", codes)

    def test_missing_patient_geometry_is_not_reconstruction_ready(self) -> None:
        result = qualify_series_geometry(
            [
                GeometryInstance(
                    stored_filename="a.dcm",
                    rows=512,
                    columns=512,
                    pixel_spacing=(0.5, 0.5),
                    image_position_patient=None,
                    image_orientation_patient=None,
                    instance_number=1,
                    number_of_frames=1,
                ),
                GeometryInstance(
                    stored_filename="b.dcm",
                    rows=512,
                    columns=512,
                    pixel_spacing=(0.5, 0.5),
                    image_position_patient=None,
                    image_orientation_patient=None,
                    instance_number=2,
                    number_of_frames=1,
                ),
            ]
        )
        self.assertFalse(result.reconstruction_ready)
        codes = {issue.code for issue in result.issues}
        self.assertIn("missing_image_position", codes)
        self.assertIn("missing_image_orientation", codes)

    def test_ingestion_persists_geometry_and_orders_instances_geometrically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DicomIngestionService(
                data_dir=Path(tmp),
                max_upload_mib=8,
                header_reader=fake_header_reader,
            )
            descriptor = service.ingest(
                [
                    Part("c.dcm", b"study|series|sop-c|1|2|512|512|0.5"),
                    Part("a.dcm", b"study|series|sop-a|99|0|512|512|0.5"),
                    Part("b.dcm", b"study|series|sop-b|50|1|512|512|0.5"),
                ]
            )
            self.assertTrue(descriptor.reconstruction_ready)
            self.assertEqual(descriptor.reconstruction_series_uid, "series")
            series = descriptor.series[0]
            self.assertTrue(series.geometry.reconstruction_ready)
            self.assertEqual(
                tuple(item.sop_instance_uid for item in series.instances),
                ("sop-a", "sop-b", "sop-c"),
            )

            manifest = json.loads(
                (Path(tmp) / "studies" / descriptor.study_id / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 2)
            self.assertTrue(manifest["reconstruction_ready"])
            self.assertEqual(
                manifest["series"][0]["geometry"]["ordered_instance_filenames"],
                ["instance-000002.dcm", "instance-000003.dcm", "instance-000001.dcm"],
            )

    def test_public_geometry_exposes_readiness_but_not_internal_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DicomIngestionService(
                data_dir=Path(tmp),
                max_upload_mib=8,
                header_reader=fake_header_reader,
            )
            descriptor = service.ingest(
                [
                    Part("a.dcm", b"study|series|sop-a|1|0|512|512|0.5"),
                    Part("b.dcm", b"study|series|sop-b|2|1|512|512|0.5"),
                ]
            )
            public = descriptor.public_dict()
            encoded = json.dumps(public)
            self.assertTrue(public["reconstruction_ready"])
            self.assertEqual(public["series"][0]["geometry"]["orientation_label"], "axial")
            self.assertNotIn("ordered_instance_filenames", encoded)
            self.assertNotIn("stored_filename", encoded)

    def test_legacy_phase3a_manifest_is_qualified_on_restore_without_reupload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            study_dir = Path(tmp) / "studies" / "legacy"
            study_dir.mkdir(parents=True)
            payload = {
                "schema_version": 1,
                "study_id": "legacy",
                "study_instance_uid": "study",
                "created_at_utc": "2026-09-01T00:00:00+00:00",
                "study_date": "20260901",
                "study_description": "Head CT",
                "modalities": ["CT"],
                "file_count": 2,
                "skipped_file_count": 0,
                "series_count": 1,
                "primary_series_uid": "series",
                "series": [
                    {
                        "series_instance_uid": "series",
                        "modality": "CT",
                        "series_number": 1,
                        "series_description": "Head",
                        "manufacturer": "Scanner",
                        "manufacturer_model": None,
                        "rows": 512,
                        "columns": 512,
                        "pixel_spacing": [0.5, 0.5],
                        "slice_thickness": 1.0,
                        "spacing_between_slices": 1.0,
                        "instance_count": 2,
                        "instances": [
                            {
                                "stored_filename": "instance-000001.dcm",
                                "sop_instance_uid": "a",
                                "sha256": "x",
                                "size_bytes": 1,
                                "instance_number": 2,
                                "image_position_patient": [0.0, 0.0, 1.0],
                                "image_orientation_patient": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
                            },
                            {
                                "stored_filename": "instance-000002.dcm",
                                "sop_instance_uid": "b",
                                "sha256": "y",
                                "size_bytes": 1,
                                "instance_number": 1,
                                "image_position_patient": [0.0, 0.0, 0.0],
                                "image_orientation_patient": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
                            },
                        ],
                    }
                ],
            }
            (study_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            public = DicomStudyRepository(Path(tmp)).latest_manifest()
            self.assertIsNotNone(public)
            self.assertTrue(public["reconstruction_ready"])
            self.assertEqual(public["reconstruction_series_uid"], "series")
            self.assertEqual(public["series"][0]["geometry"]["slice_spacing_mm"], 1.0)

    def test_workspace_reports_geometry_readiness_without_claiming_volume_exists(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn("Geometry ready - volume reconstruction pending", js)
        self.assertIn("Geometry needs review before reconstruction", js)
        self.assertIn("geometry.orientation_label", js)
        self.assertIn("geometry.slice_spacing_mm", js)
        self.assertIn("DICOM volume not loaded", html)
        self.assertNotIn("Patient volume ready", js)


if __name__ == "__main__":
    unittest.main()
