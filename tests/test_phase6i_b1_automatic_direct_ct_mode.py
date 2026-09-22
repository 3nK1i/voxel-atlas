"""Phase 6I-B1 direct CT mode intent contracts: source-only, no patient data."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'web/js/app.js'
HTML = ROOT / 'web/index.html'
CTRL = ROOT / 'web/js/automatic-surface-mode.js'


class AutomaticDirectCtModeTests(unittest.TestCase):
    def test_mode_buttons_can_request_a_not_yet_resident_direct_ct_surface(self):
        app = APP.read_text()
        self.assertIn('automaticSurfaceMode.request(modeId)', app)
        self.assertIn('state.volumeSurface.descriptor?.available', app)
        self.assertIn('autoSurfacePendingMode', app)
        self.assertIn('requestVolumeSurfaceBuild()', app)
        self.assertIn('const directCtPreparatory = sourceId === "volume-derived"', app)
        self.assertIn('sourceId === "volume-derived" && Boolean(', app)
        self.assertIn('state.volumeSurface.descriptor.study_id === state.study?.study_id', app)
        self.assertIn('if (studyId !== state.study?.study_id) return null;', app)
        self.assertNotIn('startSegmentationWorkflow(', app.split('function ensureAutomaticDirectCtSurface(',1)[1].split('function setVolumeAvailability(',1)[0])

    def test_buttons_not_user_facing_but_existing_legacy_ids_stable(self):
        html = HTML.read_text()
        self.assertIn('class="volume-surface-actions" hidden', html)
        self.assertIn('id="volumeSurfaceBuild"', html)
        self.assertIn('id="volumeSurfaceClear"', html)
        self.assertIn('Direct CT surface', html)

    def test_new_scheduler_is_standalone_and_study_reset_invalidates_intent(self):
        app = APP.read_text()
        self.assertIn('automaticSurfaceMode?.invalidate()', app)
        self.assertIn('AutomaticSurfaceModeCoordinator', app)
        self.assertIn('autoSurfaceBuildPromise', app)
        self.assertIn('autoSurfaceBuildStudyId', app)
        self.assertTrue(CTRL.is_file())

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_async_lifecycle_in_node(self):
        proc = subprocess.run(
            ['node', '--input-type=module', '-'],
            input=r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const code = fs.readFileSync('web/js/automatic-surface-mode.js','utf8');
const {AutomaticSurfaceModeCoordinator} = await import(`data:text/javascript,${encodeURIComponent(code)}`);
const deferred = () => { let resolve, reject; const promise = new Promise((yes,no) => { resolve=yes; reject=no; }); return {promise, resolve, reject}; };
let resident = false, volumeAvailable = true, selectedMode = 'volume', calls = 0, pending = null, failures = [];
let work = deferred();
const coordinator = new AutomaticSurfaceModeCoordinator({
  requestMode: mode => {selectedMode=mode; return {accepted:true};},
  canActivate: mode => mode === 'volume' ? volumeAvailable : (resident && (mode === 'surface' || volumeAvailable)),
  ensureSurface: () => {calls++; return work.promise;},
  onPending: mode => {pending=mode;},
  onFailure: error => failures.push(error.message),
});
const first = coordinator.request('surface');
assert.equal(pending,'surface');
assert.equal(selectedMode,'volume');
coordinator.request('volume');
resident=true; work.resolve(true);
await first;
assert.equal(selectedMode,'volume','outdated build completion must not activate Surface');
assert.equal(pending,null);
const immediate = coordinator.request('combined');
assert.equal(immediate.accepted,true);
assert.equal(selectedMode,'combined');
resident=false; work=deferred();
const earlier=coordinator.request('surface');
const later=coordinator.request('combined');
resident=true; work.resolve(true);
await Promise.all([earlier,later]);
assert.equal(selectedMode,'combined','latest pending intent must win');
resident=false; work=deferred();
const beforeReset=coordinator.request('surface');
coordinator.invalidate();
resident=true; work.resolve(true);
await beforeReset;
assert.equal(selectedMode,'combined','study reset must invalidate pending mode');
resident=false; work=deferred();
const failing=coordinator.request('surface');
work.reject(new Error('qualified surface failed'));
await failing;
assert.deepEqual(failures,['qualified surface failed']);
assert.equal(selectedMode,'combined');
assert.equal(pending,null);
assert.equal(calls,5);
console.log('AUTOMATIC_MODE_ASYNC_TESTS=PASS');
''',
            text=True, capture_output=True, cwd=ROOT, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn('AUTOMATIC_MODE_ASYNC_TESTS=PASS', proc.stdout)


if __name__ == '__main__':
    unittest.main()
