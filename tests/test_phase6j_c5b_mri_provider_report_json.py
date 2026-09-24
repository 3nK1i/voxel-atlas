"""6J-C5B: provider report JSON parsing; synthetic data only, no inference."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from voxelatlas.mri_task_contract import TOTAL_SEGMENTATOR_MRI_STRUCTURES
from voxelatlas.mri_worker_execution import (MAX_REPORT_BYTES, MRIWorkerError,
                                              _read_report, _valid_provider)


class MRIProviderReportJSONTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / "report.json"
        self.input = self.root / "input.nii.gz"
        self.mask = self.root / "output.nii.gz"

    def provider_payload(self):
        return {
            "totalsegmentator_version": "2.18.0", "task": "total_mr",
            "modality": "MR", "device": "gpu", "multilabel": True,
            "output_type": "nifti", "roi_subset": None,
            "input": str(self.input), "output": str(self.mask),
            "num_classes": 50,
            "classes": {str(k): v for k, v in TOTAL_SEGMENTATOR_MRI_STRUCTURES.items()},
            "fast": False, "fastest": True, "runtime_seconds": 1.25,
        }

    def test_formatted_cli_report_is_parsed_and_validated(self):
        payload = self.provider_payload()
        self.report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        parsed = _read_report(self.report)
        self.assertEqual(parsed, payload)
        _valid_provider(parsed, self.input, self.mask, "fastest")

    def test_compact_json_remains_supported(self):
        payload = self.provider_payload()
        self.report.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        self.assertEqual(_read_report(self.report), payload)

    def test_malformed_trailing_json_is_rejected(self):
        self.report.write_text('{"task":"total_mr"}\n{"task":"total_mr"}\n', encoding="utf-8")
        with self.assertRaises(MRIWorkerError):
            _read_report(self.report)

    def test_non_object_and_invalid_encoding_are_rejected(self):
        for value in ('[]', 'null', '"string"', '{"task":'):
            with self.subTest(value=value):
                self.report.write_text(value, encoding="utf-8")
                with self.assertRaises(MRIWorkerError):
                    _read_report(self.report)
        self.report.write_bytes(b"\xff")
        with self.assertRaises(MRIWorkerError):
            _read_report(self.report)

    def test_link_empty_and_oversize_are_rejected(self):
        self.report.write_text('', encoding="utf-8")
        with self.assertRaises(MRIWorkerError):
            _read_report(self.report)
        self.report.write_bytes(b" " * (MAX_REPORT_BYTES + 1))
        with self.assertRaises(MRIWorkerError):
            _read_report(self.report)
        self.report.unlink()
        destination = self.root / 'destination.json'
        destination.write_text('{}', encoding='utf-8')
        self.report.symlink_to(destination)
        with self.assertRaises(MRIWorkerError):
            _read_report(self.report)

    def test_wrong_model_identity_is_still_rejected(self):
        payload = self.provider_payload()
        payload["task"] = "total"
        self.report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        with self.assertRaises(MRIWorkerError):
            _valid_provider(_read_report(self.report), self.input, self.mask, "fastest")


if __name__ == "__main__":
    unittest.main()
