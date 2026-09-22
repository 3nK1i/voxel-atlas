"""6H-A: synthetic service-selection tests; no DICOM, real studies, server or worker invocation."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys
import subprocess
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from voxelatlas.segmentation_surface_real_study_qualification import (  # noqa: E402
    QualificationServices, RealStudyQualificationError, qualify_real_study,
)


class RealStudyHarness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.study = 'a' * 32
        self.mapid = 'map-' + 'b' * 32
        study_root = self.root / 'studies' / self.study
        study_root.mkdir(parents=True)
        self.manifest = study_root / 'manifest.json'
        self.manifest.write_text('{"study_id":"' + self.study + '"}', encoding='utf-8')
        self.volume = study_root / 'derived' / 'volume.npy'
        self.volume.parent.mkdir(parents=True)
        np.save(self.volume, np.zeros((7, 8, 9), np.float32))
        self.label_path = self.root / 'segmentation' / 'label-maps' / self.mapid / 'labels.npy'
        self.label_path.parent.mkdir(parents=True)
        labels = np.zeros((7, 8, 9), np.uint16)
        labels[1:6, 2:7, 2:8] = 91
        np.save(self.label_path, labels)
        self.affine = np.eye(4, dtype=float)
        self.affine[:3, :3] = [[0, 0, -2], [0, 3, 0], [4, 0, 0]]
        self.affine[:3, 3] = [22, 30, 60]
        self.source = SimpleNamespace(
            study_dir=study_root, manifest_path=self.manifest, volume_path=self.volume,
            modality='CT', intensity_units='HU', source_descriptor_sha256='c' * 64,
            shape=tuple(labels.shape), array_index_to_patient_lps=self.affine.tolist(),
        )
        self.descriptor = {
            'source_study_id': self.study, 'source_modality': 'CT',
            'source_volume_descriptor_sha256': 'c' * 64,
            'source_volume_artifact_sha256': sha256(self.volume.read_bytes()).hexdigest(),
            'clinical_validation': 'not_claimed', 'shape': list(labels.shape),
            'array_index_to_patient_lps': self.affine.tolist(), 'present_labels': [0, 91],
            'artifact_sha256': sha256(self.label_path.read_bytes()).hexdigest(),
            'artifact_bytes': self.label_path.stat().st_size,
            'identity_sha256': 'd' * 64,
        }
        # MPR descriptor dimensions are synthetic and central slice index is
        # derived from label ROI in Patient LPS, not from volume array axes.
        world = np.array([[a, b, c] for a in (0, 6) for b in (0, 7) for c in (0, 8)]) @ self.affine[:3,:3].T + self.affine[:3,3]
        mi, ma = world.min(axis=0), world.max(axis=0)
        inverse = np.linalg.inv(self.affine[:3, :3])
        world_spacing = [1. / np.linalg.norm(inverse @ np.eye(3)[axis]) for axis in range(3)]
        planes = {}
        for name, n, h, v, reverse in (('axial', 2, 0, 1, False),
                                      ('coronal', 1, 0, 2, True),
                                      ('sagittal', 0, 1, 2, True)):
            counts = [int(round((ma[axis] - mi[axis]) / world_spacing[axis])) + 1 for axis in (n, h, v)]
            intervals = [(ma[axis] - mi[axis]) / (count - 1) for axis, count in zip((n, h, v), counts)]
            planes[name] = {
                'plane': name, 'normal_axis': 'xyz'[n], 'horizontal_axis': 'xyz'[h],
                'vertical_axis': 'xyz'[v], 'vertical_reverse': reverse,
                'slice_count': counts[0], 'slice_spacing_mm': float(intervals[0]),
                'position_range_mm': [float(mi[n]), float(ma[n])],
                'image_width': counts[1], 'image_height': counts[2],
                'horizontal_range_mm': [float(mi[h]), float(ma[h])],
                'vertical_range_mm': [float(mi[v]), float(ma[v])],
                'pixel_spacing_mm': [float(intervals[2]), float(intervals[1])],
            }
        self.mpr_descriptor = {'ready': True, 'modality': 'CT', 'intensity_units': 'HU',
                               'planes': planes}
        self.mpr = Mock()
        self.mpr._latest_manifest_path.return_value = self.manifest
        self.mpr.descriptor_latest.return_value = self.mpr_descriptor
        self.labels = Mock()
        self.labels.get.return_value = self.descriptor
        self.volume_service = Mock()
        self.volume_service.source_latest.return_value = self.source
        self.surface_service = Mock()
        self.surface_service.surface_latest.side_effect = lambda **kw: SimpleNamespace(quality=kw['quality'])
        self.services = QualificationServices(self.volume_service, self.labels, self.mpr,
                                              self.surface_service)
        self.before = (self.manifest.read_bytes(), self.volume.read_bytes(), self.label_path.read_bytes())

    def run_harness(self, **changes):
        kwargs = dict(data_dir=self.root, label_map_id=self.mapid, label_id=91, services=self.services)
        kwargs.update(changes)
        return qualify_real_study(**kwargs)

    def test_preflight_pins_source_and_three_physically_central_planes_without_writes(self):
        report = self.run_harness(expected_study_id=self.study)
        self.assertEqual(report['status'], 'preflight_ready')
        self.assertEqual(report['roi']['roi_shape'], [5, 5, 6])
        self.assertTrue(report['roi']['roi_within_6g_budget'])
        self.assertFalse(report['roi']['acquisition_boundary_contact'])
        self.assertEqual(set(report['mpr_selection']), {'axial', 'coronal', 'sagittal'})
        self.assertEqual(report['source_binding'], 'latest_manifest_canonical_descriptor_and_artifact_seals')
        self.surface_service.surface_latest.assert_not_called()
        self.assertEqual(self.before, (self.manifest.read_bytes(), self.volume.read_bytes(), self.label_path.read_bytes()))

    def test_wrong_source_study_or_volume_digest_fails_before_worker(self):
        with self.assertRaisesRegex(RealStudyQualificationError, 'expected latest'):
            self.run_harness(expected_study_id='e' * 32, execute=True)
        self.descriptor['source_volume_artifact_sha256'] = '0' * 64
        with self.assertRaisesRegex(RealStudyQualificationError, 'volume seal'):
            self.run_harness(execute=True)
        self.surface_service.surface_latest.assert_not_called()

    def test_mpr_manifest_mismatch_fails_before_worker(self):
        other = self.root / 'other-manifest.json'
        other.write_text('{}')
        self.mpr._latest_manifest_path.return_value = other
        with self.assertRaisesRegex(RealStudyQualificationError, 'MPR latest-study'):
            self.run_harness(execute=True)
        self.surface_service.surface_latest.assert_not_called()

    def test_wrong_mpr_world_bounds_fail_before_surface_worker(self):
        self.mpr_descriptor['planes']['sagittal']['horizontal_range_mm'] = [0., 21.]
        with self.assertRaisesRegex(ValueError, 'MPR plane bounds'):
            self.run_harness(execute=True)
        self.surface_service.surface_latest.assert_not_called()

    def test_label_roi_budget_returns_nonqualified_preflight_and_blocks_execute(self):
        with patch('voxelatlas.segmentation_surface_real_study_qualification.MAX_6G1_MASK_VOXELS', 10):
            report = self.run_harness()
            self.assertEqual(report['status'], 'analysis_budget_exceeded')
            with self.assertRaisesRegex(RealStudyQualificationError, 'analysis budget'):
                self.run_harness(execute=True)
        self.surface_service.surface_latest.assert_not_called()

    def test_missing_label_and_modified_label_artifact_are_rejected(self):
        with self.assertRaisesRegex(RealStudyQualificationError, 'not present'):
            self.run_harness(label_id=92)
        self.label_path.write_bytes(self.label_path.read_bytes() + b'x')
        with self.assertRaisesRegex(RealStudyQualificationError, 'artifact seal'):
            self.run_harness()

    def test_execute_supplies_refined_and_accurate_bounded_source_to_6g3(self):
        measured = {'status': 'needs_review', 'surfaces': {
            'accurate': {'status': 'sampled_evidence_only'},
            'refined': {'status': 'needs_review'}}}
        with patch('voxelatlas.segmentation_surface_real_study_qualification.bound_fidelity_report',
                   return_value=measured) as run_report:
            result = self.run_harness(execute=True, mesh_sample_limit=16, contour_sample_limit=8)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['fidelity'], measured)
        self.assertEqual(self.surface_service.surface_latest.call_count, 2)
        self.assertEqual([call.kwargs['quality'] for call in self.surface_service.surface_latest.call_args_list],
                         ['accurate', 'refined'])
        self.assertEqual(run_report.call_args.kwargs['mpr_study_id'], self.study)
        self.assertEqual(run_report.call_args.kwargs['source_study_id'], self.study)
        self.assertEqual(run_report.call_args.kwargs['mesh_sample_limit'], 16)
        self.assertEqual(run_report.call_args.kwargs['contour_sample_limit'], 8)
        self.assertEqual(run_report.call_args.kwargs['label_artifact_path'], self.label_path)
        self.assertEqual(self.before, (self.manifest.read_bytes(), self.volume.read_bytes(), self.label_path.read_bytes()))

    def test_refined_failure_not_silently_swallowed_or_replaced(self):
        self.surface_service.surface_latest.side_effect = [SimpleNamespace(quality='accurate'), ValueError('refined unavailable')]
        with patch('voxelatlas.segmentation_surface_real_study_qualification.bound_fidelity_report') as run_report:
            with self.assertRaisesRegex(ValueError, 'refined unavailable'):
                self.run_harness(execute=True)
        run_report.assert_not_called()

    def test_latest_study_flip_during_measurement_fails_closed(self):
        self.volume_service.source_latest.side_effect = [self.source, SimpleNamespace(study_dir=Path('f' * 32))]
        with patch('voxelatlas.segmentation_surface_real_study_qualification.bound_fidelity_report',
                   return_value={'status': 'sampled_evidence_only'}):
            with self.assertRaisesRegex(RealStudyQualificationError, 'changed during'):
                self.run_harness(execute=True)

    def test_cli_missing_local_study_does_not_echo_path_or_identifiers(self):
        command = [sys.executable, str(ROOT / 'scripts/qualify_phase6h_a_real_study.py'),
                   '--data-dir', str(self.root / 'private-unavailable'),
                   '--label-map-id', self.mapid, '--label-id', '91']
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('PHASE6H_A_STATUS=BLOCKED', result.stdout)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        self.assertNotIn(self.mapid, result.stdout + result.stderr)
        self.assertNotIn(self.study, result.stdout + result.stderr)

    def test_acquisition_boundary_contact_is_reported_without_completing_anatomy(self):
        labels = np.zeros((7, 8, 9), np.uint16)
        labels[:5, 2:7, 2:8] = 91
        np.save(self.label_path, labels)
        self.descriptor['artifact_sha256'] = sha256(self.label_path.read_bytes()).hexdigest()
        self.descriptor['artifact_bytes'] = self.label_path.stat().st_size
        result = self.run_harness()
        self.assertTrue(result['roi']['acquisition_boundary_contact'])
        self.assertNotIn('fidelity', result)


if __name__ == '__main__':
    unittest.main()
