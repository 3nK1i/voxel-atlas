"""C4C: read-only MRI workflow snapshots. Synthetic job records, no inference."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from voxelatlas.segmentation import CanonicalSegmentationSource, SegmentationUnavailableError
from voxelatlas.segmentation_workflow import SegmentationWorkflowService
from test_phase6j_b2a_mri_source_series import study_manifest

A, B = 'a' * 32, 'b' * 32
UID = '1.2.840.10008.5.1.4.1.1.4.2026'


class Jobs:
    def __init__(self, source):
        self.source = source
        self.sources = SimpleNamespace(latest=lambda: self.source)
        self.records = []
        self.created = []
        self.executed = []
        self.cancelled = []
    def list_models(self):
        return [dict(provider_id='totalsegmentator', model_id='total_mr',
                     supported_modalities=['MR'], available=False,
                     availability_reason='MRI runtime is not configured'),
                dict(provider_id='totalsegmentator', model_id='total',
                     supported_modalities=['CT'], available=True)]
    def list_jobs(self):
        return list(self.records)
    def get_job(self, job_id):
        return next(item for item in self.records if item['job_id'] == job_id)
    def create_job(self, **kwargs):
        self.created.append(kwargs)
        raise AssertionError('Read-only MRI workflow attempted job creation')
    def run_job(self, job_id):
        self.executed.append(job_id)
        raise AssertionError('Read-only MRI workflow attempted execution')
    def cancel_job(self, job_id):
        self.cancelled.append(job_id)
        self.get_job(job_id)['state'] = 'cancelled'


def source_fixture(root: Path):
    path = root / 'manifest.json'
    path.write_text(json.dumps(study_manifest(A)), encoding='utf-8')
    return CanonicalSegmentationSource(
        study_id=A, study_instance_uid='1.2.3', source_series_uid=UID, modality='MR',
        volume_created_at_utc='2026-09-23T00:00:00Z', descriptor_sha256='0' * 64,
        artifact_sha256='1' * 64, manifest_path=path, study_dir=root,
        volume_path=root / 'volume.npy', metadata_path=root / 'volume.json',
    )


def record(source, *, state='running', job_id='seg-' + '1'*32, **overrides):
    provenance = dict(source_study_id=source.study_id, source_study_instance_uid=source.study_instance_uid,
        source_series_uid=source.source_series_uid, source_modality='MR',
        canonical_volume_created_at_utc=source.volume_created_at_utc,
        canonical_volume_descriptor_sha256=source.descriptor_sha256,
        canonical_volume_artifact_sha256=source.artifact_sha256,
        provider_id='totalsegmentator', model_id='total_mr')
    provenance.update(overrides)
    return dict(job_id=job_id, state=state, provenance=provenance,
                progress=dict(percent=12.5, message='PRIVATE: /patient/secret.dcm'))


class MRIWorkflowC4CTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        self.source = source_fixture(self.data)
        self.jobs = Jobs(self.source)
        self.service = SegmentationWorkflowService.__new__(SegmentationWorkflowService)
        self.service.provider_id, self.service.model_id = 'totalsegmentator', 'total'
        self.service.job_service = self.jobs
        self.service.label_map_service = SimpleNamespace(list=lambda **kwargs: [dict(
            source_study_id=A, provider_id='totalsegmentator', model_id='total',
            label_map_id='map-'+'b'*32, present_labels=[0, 1])])
        self.service.python_executable = '/dummy/ct/import'
        self.service._lock = threading.RLock()
        self.service._finalizing_jobs = set()
        self.service.mri_presentation_only = True

    def test_active_matching_mri_job_is_read_only_and_study_bound(self):
        self.jobs.records = [record(self.source)]
        snap = self.service.snapshot_latest()
        self.assertEqual((snap['model_id'], snap['state']), ('total_mr', 'running'))
        self.assertEqual(snap['source_series_uid'], UID)
        self.assertTrue(snap['can_cancel'])
        self.assertFalse(snap['can_start'] or snap['can_use'])
        self.assertTrue(snap['presentation_only'])
        self.assertEqual(snap['progress']['percent'], 12.5)
        self.assertNotIn('patient', str(snap).lower())
        with self.assertRaises(SegmentationUnavailableError):
            self.service.request_start()
        self.assertEqual(self.jobs.created, [])
        self.service.execute_requested(self.jobs.records[0]['job_id'])
        self.assertEqual(self.jobs.executed, [])
        self.assertEqual(self.service.cancel_latest()['state'], 'cancelled')
        self.assertEqual(self.jobs.cancelled, ['seg-'+'1'*32])

    def test_other_study_modality_series_and_hash_never_appear_or_cancel(self):
        mismatches = (dict(source_study_id=B), dict(source_study_instance_uid='changed'),
            dict(source_series_uid='1.2.999'), dict(source_modality='CT'),
            dict(canonical_volume_created_at_utc='changed'),
            dict(canonical_volume_descriptor_sha256='e'*64),
            dict(canonical_volume_artifact_sha256='e'*64),
            dict(provider_id='other'), dict(model_id='total'))
        for override in mismatches:
            with self.subTest(override=override):
                self.jobs.records = [record(self.source, **override)]
                snap = self.service.snapshot_latest()
                self.assertEqual(snap['state'], 'unavailable')
                self.assertIsNone(snap['job_id'])
                self.assertFalse(snap['can_start'] or snap['can_cancel'] or snap['can_use'])
                self.service.cancel_latest()
                self.assertEqual(self.jobs.cancelled, [])

    def test_switch_source_and_same_study_new_volume_invalidates_job(self):
        self.jobs.records = [record(self.source)]
        # The canonical source is frozen: reflect new volume identity using dataclass replacement.
        from dataclasses import replace
        self.jobs.source = replace(self.source, artifact_sha256='f'*64)
        self.assertIsNone(self.service.snapshot_latest()['job_id'])
        self.jobs.source = SimpleNamespace(study_id=B, modality='CT')
        snap = self.service.snapshot_latest()
        self.assertEqual(snap['model_id'], 'total')
        self.assertTrue(snap['can_use'])
        self.assertFalse(snap.get('presentation_only', False))

    def test_terminal_mri_job_does_not_trigger_ct_import_or_promise_map(self):
        for state in ('succeeded', 'failed', 'cancelled', 'cancelling'):
            with self.subTest(state=state):
                self.jobs.records = [record(self.source, state=state)]
                snap = self.service.snapshot_latest()
                self.assertEqual(snap['model_id'], 'total_mr')
                self.assertFalse(snap['can_start'] or snap['can_use'])
                self.assertIsNone(snap['label_map_id'])
                self.assertIn(snap['state'], ('output_ready', 'failed', 'cancelled', 'cancelling'))
                with self.assertRaises(SegmentationUnavailableError):
                    self.service.request_start()
                self.service.execute_requested(self.jobs.records[0]['job_id'])
                self.assertEqual(self.jobs.executed, [])

    def test_unqualified_series_blocks_even_matching_job(self):
        self.jobs.records = [record(self.source)]
        bad = study_manifest(A)
        bad['series'][0]['geometry']['reconstruction_ready'] = False
        self.source.manifest_path.write_text(json.dumps(bad), encoding='utf-8')
        snap = self.service.snapshot_latest()
        self.assertEqual(snap['state'], 'unsupported')
        self.assertFalse(snap['can_start'] or snap['can_cancel'])

    def test_default_app_wires_read_only_without_registering_executable_adapter(self):
        code = (ROOT / 'backend/voxelatlas/app.py').read_text(encoding='utf-8')
        self.assertIn('mri_presentation_only=True', code)
        self.assertNotIn('from .mri_job_binding import', code)
        self.assertNotIn('MRIStudyBoundProvider(', code)


if __name__ == '__main__':
    unittest.main()
