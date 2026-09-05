import copy
import unittest
from scripts.check_phase4h6_evidence import validate_report, MODES, SLOTS


def good_report():
    return {'schema': 'voxelatlas-phase4h6-v1', 'build': 'phase4h6',
            'faults': {'windowErrors': 0, 'unhandledRejections': 0, 'contextLosses': 0},
            'captures': [{'slot': slot, 'runtime': {
                'modality': slot.split('-')[0], 'ready': True, 'contextLost': False,
                'shaderErrors': 0, 'qualityPolicy': 'balanced', 'dimensions': [256, 256, 112],
                'geometries': 2, 'textures': 1, 'programs': 2, 'overlayNodes': 30,
                'canvasWidth': 800, 'canvasHeight': 600, 'pixelRatio': 1,
            }, 'modes': {mode: {'continuousFrameIntervalMs': {'count': 60, 'p95Ms': 33.0}}
                         for mode in MODES}} for slot in SLOTS]}


class EvidenceTests(unittest.TestCase):
    def test_complete_report_and_nonmutation(self):
        report = good_report()
        original = copy.deepcopy(report)
        self.assertEqual(validate_report(report), [])
        self.assertEqual(report, original)

    def test_missing_evidence_is_not_pass(self):
        for value in (None, [], {}, {'captures': []}, {'captures': [None] * 4}):
            self.assertTrue(validate_report(value))

    def test_resource_growth_is_not_pass(self):
        for key in ('textures', 'geometries', 'programs', 'overlayNodes'):
            report = good_report()
            report['captures'][2]['runtime'][key] += 1
            self.assertTrue(validate_report(report), key)

    def test_faults_and_incomplete_modes(self):
        for key in ('windowErrors', 'unhandledRejections', 'contextLosses'):
            report = good_report()
            report['faults'][key] = 1
            self.assertTrue(validate_report(report))
        for bad in (None, float('nan'), -1, 101):
            report = good_report()
            report['captures'][0]['modes']['mip']['continuousFrameIntervalMs']['p95Ms'] = bad
            self.assertTrue(validate_report(report))
        report = good_report()
        del report['captures'][1]['modes']['slice']
        self.assertTrue(validate_report(report))

    def test_shader_and_workload_mismatch(self):
        for key, value in (('shaderErrors', 1), ('contextLost', True), ('qualityPolicy', 'maximum'),
                           ('dimensions', [512, 512, 80]), ('canvasWidth', 1200)):
            report = good_report()
            report['captures'][2]['runtime'][key] = value
            self.assertTrue(validate_report(report), key)


if __name__ == '__main__':
    unittest.main()
