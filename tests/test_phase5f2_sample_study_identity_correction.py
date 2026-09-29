from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.dicom_ingestion import DicomIngestionService, DicomStudyRepository  # noqa: E402
from voxelatlas.sample_catalog import (  # noqa: E402
    SAMPLE_CATALOG_SCHEMA_VERSION,
    SampleStudyCatalogService,
    compute_sample_payload_contract,
)


STUDY_WITH_MAP = "a" * 32
STUDY_WITHOUT_MAP = "b" * 32


@dataclass
class Descriptor:
    study_id: str

    def public_dict(self) -> dict[str, object]:
        return {"study_id": self.study_id, "origin": {"kind": "sample"}}


class ReusableDicomService:
    def __init__(self, candidates: list[str]) -> None:
        self.candidates = candidates
        self.activated: list[str] = []
        self.ingested = False
        self.find_arguments: dict[str, object] | None = None

    def find_matching_sample_studies(self, **kwargs):
        self.find_arguments = kwargs
        return list(self.candidates)

    def activate_study(self, study_id: str):
        self.activated.append(study_id)
        return Descriptor(study_id).public_dict()

    def ingest(self, _parts):
        self.ingested = True
        return Descriptor("c" * 32)

    def annotate_study_origin(self, study_id: str, origin: dict[str, object]):
        return Descriptor(study_id).public_dict() | {"origin": origin}


class LabelMaps:
    def list(self, *, study_id: str):
        return [{"label_map_id": "map-" + "1" * 32}] if study_id == STUDY_WITH_MAP else []


def install_sample(data_dir: Path) -> None:
    dicom = data_dir / "sample_studies" / "head-ct" / "dicom"
    dicom.mkdir(parents=True)
    (dicom / "a.dcm").write_bytes(b"DICOM-A")
    (dicom / "b.dcm").write_bytes(b"DICOM-B")
    digest, count, size, _ = compute_sample_payload_contract(dicom)
    payload = {
        "schema_version": SAMPLE_CATALOG_SCHEMA_VERSION,
        "sample_id": "head-ct",
        "title": "Head CT",
        "summary": "Deidentified demonstration study.",
        "modality": "CT",
        "body_region": "Head",
        "source_label": "Public imaging archive",
        "source_url": "https://example.org/source",
        "license_label": "Source terms",
        "license_url": "https://example.org/license",
        "payload_sha256": digest,
        "file_count": count,
        "size_bytes": size,
        "order": 1,
        "featured": True,
        "installed_at_utc": "2026-09-09T10:00:00+00:00",
    }
    (dicom.parent / "sample.json").write_text(json.dumps(payload), encoding="utf-8")


class Phase5F2SampleIdentityTests(unittest.TestCase):
    def test_reopening_sample_reuses_matching_study_and_prefers_label_map_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            install_sample(data_dir)
            dicom = ReusableDicomService([STUDY_WITHOUT_MAP, STUDY_WITH_MAP])
            service = SampleStudyCatalogService(
                data_dir=data_dir,
                dicom_service=dicom,
                label_map_service=LabelMaps(),
            )
            result = service.load_sample("head-ct")

        self.assertTrue(result["reused"])
        self.assertEqual(result["study"]["study_id"], STUDY_WITH_MAP)
        self.assertEqual(dicom.activated, [STUDY_WITH_MAP])
        self.assertFalse(dicom.ingested)
        self.assertEqual(dicom.find_arguments["sample_id"], "head-ct")
        self.assertEqual(len(dicom.find_arguments["instance_inventory"]), 2)

    def test_new_sample_still_uses_normal_ingestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            install_sample(data_dir)
            dicom = ReusableDicomService([])
            service = SampleStudyCatalogService(data_dir=data_dir, dicom_service=dicom)
            result = service.load_sample("head-ct")

        self.assertFalse(result["reused"])
        self.assertTrue(dicom.ingested)
        self.assertEqual(result["study"]["study_id"], "c" * 32)

    def test_repository_matches_only_verified_origin_and_instance_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            repository = DicomStudyRepository(data_dir)
            study_root = data_dir / "studies" / STUDY_WITH_MAP
            study_root.mkdir(parents=True)
            inventory = (("1" * 64, 7), ("2" * 64, 9))
            manifest = {
                "study_id": STUDY_WITH_MAP,
                "origin": {"kind": "sample", "sample_id": "head-ct"},
                "series": [
                    {"instances": [
                        {"sha256": inventory[0][0], "size_bytes": inventory[0][1]},
                        {"sha256": inventory[1][0], "size_bytes": inventory[1][1]},
                    ]}
                ],
            }
            (study_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            matches = repository.find_matching_sample_studies(
                sample_id="head-ct", instance_inventory=inventory
            )
            mismatch = repository.find_matching_sample_studies(
                sample_id="head-ct", instance_inventory=(("1" * 64, 8),)
            )

        self.assertEqual(matches, [STUDY_WITH_MAP])
        self.assertEqual(mismatch, [])

    def test_identity_correction_does_not_relax_patient_data_or_cross_study_rules(self) -> None:
        source = (ROOT / "backend" / "voxelatlas" / "sample_catalog.py").read_text(
            encoding="utf-8"
        )
        repository = (ROOT / "backend" / "voxelatlas" / "dicom_ingestion.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("instance_inventory", source)
        self.assertIn("find_matching_sample_studies", repository)
        self.assertIn("activate_study", repository)
        self.assertNotIn("segmentation/label-maps", source)

    def test_ready_reused_sample_restores_mpr_and_volume_rendering(self) -> None:
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        activation = (
            ROOT / "web" / "js" / "sample-study-activation.js"
        ).read_text(encoding="utf-8")

        self.assertIn("classifySampleStudyActivation", activation)
        self.assertIn('return "restore"', activation)
        self.assertIn('activation === "restore"', app)
        restore_branch = app.split('activation === "restore"', 1)[1].split(
            'activation === "construct"', 1
        )[0]
        self.assertIn("await restoreReadyPatientVolume", restore_branch)
        restoration = app.split(
            "async function restoreReadyPatientVolume", 1
        )[1].split("async function refreshLatestStudy", 1)[0]
        self.assertIn("await ensureMprReady()", restoration)
        self.assertIn("await ensureVolumeRenderingFoundation()", restoration)


if __name__ == "__main__":
    unittest.main()
