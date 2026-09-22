"""Phase 6I-B2: source-bound segmentation mode intent, opt-in UI, no segmentation job."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'web/js/app.js')
GATE = ROOT / 'web/js/existing-segmentation-mode.js'
HTML = ROOT / 'web/index.html'
CSS = ROOT / 'web/css/styles.css'


class ExistingSegmentationModeTests(unittest.TestCase):
    def test_existing_label_map_gates_automatic_presentation_without_starting_segmentation(self):
        app = APP.read_text()
        self.assertIn('ExistingSegmentationSurfaceGate', app)
        self.assertIn('function canPrepareAutomaticSegmentationSurface(', app)
        self.assertIn('function ensureAutomaticSelectedSurface(', app)
        self.assertIn('function ensureAutomaticSegmentationSurface(', app)
        self.assertIn('segmentationSurfaceGate?.notify(surfaceStatus)', app)
        self.assertIn('segmentationSurfaceGate?.invalidate()', app)
        self.assertIn('state.segmentationSurface.descriptor?.source_study_id === state.study?.study_id', app)
        self.assertIn('state.segmentationSurface.enabled', app)
        self.assertIn('state.reconstructionVisualization.surfaceSourceSelection["segmentation-derived"]', app)
        self.assertIn('segmentationSurfaceLayer.desiredLabels.size > 0', app)
        block = app.split('function ensureAutomaticSegmentationSurface(', 1)[1].split('function ensureAutomaticDirectCtSurface(', 1)[0]
        self.assertNotIn('requestSegmentationStart(', block)
        self.assertNotIn('/segmentation-workflow/start', block)
        self.assertNotIn('requestVolumeSurfaceBuild()', block)

    def test_segmentation_source_can_be_selected_before_geometry_is_resident(self):
        app = APP.read_text()
        self.assertIn('const segmentationPreparatory = sourceId === "segmentation-derived"', app)
        self.assertIn('sourceState?.resident || directCtPreparatory || segmentationPreparatory', app)
        self.assertIn('sourceId === "segmentation-derived" && Boolean(', app)
        self.assertIn('segmentationSurfaceGate?.invalidate()', app)
        self.assertIn('segmentationSurfaceLayer?.setPresentationVisible(snapshot.visibility.surfaceSources["segmentation-derived"])', app)

    def test_use_segmentation_is_only_restyled_not_rewired(self):
        html = HTML.read_text()
        css = CSS.read_text()
        self.assertEqual(html.count('id="segmentationWorkflowPrimary"'), 1)
        self.assertIn('segmentation-workflow-primary', html)
        self.assertIn('.segmentation-workflow-panel[data-state="available"] .segmentation-workflow-primary:not(:disabled)', css)
        self.assertIn('.segmentation-workflow-primary:focus-visible', css)
        self.assertIn('onPrimary: () => void requestSegmentationStart()', APP.read_text())

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_gate_and_mode_coordinator_preserve_latest_intent(self):
        proc = subprocess.run(['node', '--input-type=module', '-'], input=r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const read=async path=>import(`data:text/javascript,${encodeURIComponent(fs.readFileSync(path,'utf8'))}`);
const {ExistingSegmentationSurfaceGate}=await read('web/js/existing-segmentation-mode.js');
const {AutomaticSurfaceModeCoordinator}=await read('web/js/automatic-surface-mode.js');
const {ReconstructionVisualizationModeController}=await read('web/js/reconstruction-visualization-mode.js');
const controller=new ReconstructionVisualizationModeController();
controller.setVolumeAvailable(true);
let selected=true, visible=true, desired=true, resident=false, starts=0;
const gate=new ExistingSegmentationSurfaceGate({
  readIdentity:()=>selected&&visible ? 'studyA/mapA' : null,
  hasResident:()=>resident,
  hasDesiredStructures:()=>desired,
  startSurface:()=>{starts++;return Promise.resolve();},
});
const coordinator=new AutomaticSurfaceModeCoordinator({
  requestMode:mode=>controller.requestMode(mode),
  canActivate:mode=>mode==='surface'?controller.snapshot().canSurface:controller.snapshot().canCombined,
  ensureSurface:()=>gate.request(),
});
const first=coordinator.request('surface');
assert.equal(controller.snapshot().mode,'volume');
const second=coordinator.request('combined');
assert.equal(starts,1,'same existing label map must not start two surface loads');
resident=true;
controller.setSurfaceSource('segmentation-derived',{available:true,resident:true,selected:true});
gate.notify({state:'qualified',requestedCount:1,readyCount:1});
assert.equal((await first).reason,'superseded');
assert.equal((await second).accepted,true);
assert.equal(controller.snapshot().mode,'combined');
assert.equal(starts,1);
controller.requestMode('volume');
assert.equal(controller.snapshot().visibility.surfaceSources['segmentation-derived'],false);
assert.equal(resident,true,'hiding surface preserves resident geometry');
resident=false;
controller.setSurfaceSource('segmentation-derived',{available:true,resident:false,selected:false});
const pending=coordinator.request('surface');
selected=false; gate.invalidate(); coordinator.invalidate();
resident=true;
controller.setSurfaceSource('segmentation-derived',{available:true,resident:true,selected:false});
assert.equal((await pending).accepted,false);
assert.equal(controller.snapshot().mode,'volume');
console.log('B2_MODE_INTEGRATION=PASS');
''', cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('B2_MODE_INTEGRATION=PASS', proc.stdout)

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_identity_bound_gate_lifecycle_in_node(self):
        proc = subprocess.run(['node', '--input-type=module', '-'], input=r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source=fs.readFileSync('web/js/existing-segmentation-mode.js','utf8');
const {ExistingSegmentationSurfaceGate}=await import(`data:text/javascript,${encodeURIComponent(source)}`);
let identity='study1/map1', eligible=true, desired=1, resident=false, starts=0;
const gate = new ExistingSegmentationSurfaceGate({
  readIdentity:()=>eligible ? identity : null,
  hasResident:()=>resident,
  hasDesiredStructures:()=>desired>0,
  startSurface:()=>{starts++; return Promise.resolve(null);},
});
const first=gate.request();
const duplicate=gate.request();
assert.equal(first,duplicate,'same label map reuses pending request');
assert.equal(starts,1);
gate.notify({state:'loading',requestedCount:1,readyCount:0});
resident=true;
gate.notify({state:'qualified',requestedCount:1,readyCount:1});
assert.equal(await first,true);
assert.equal(await gate.request(),true,'resident is reused');
assert.equal(starts,1);
resident=false; identity='study2/map2';
const stale=gate.request();
identity='study3/map3'; gate.notify({state:'loading',requestedCount:1});
assert.equal(await stale,false,'changed study/labelmap invalidates old request');
const failing=gate.request();
gate.notify({state:'error',requestedCount:1,failedCount:1});
assert.equal(await failing,false,'terminal surface failure does not hang mode selection');
const cancelled=gate.request(); gate.invalidate();
assert.equal(await cancelled,false,'mode switch or deselection invalidates pending mode intent');
assert.equal(starts,4);
desired=0;
assert.equal(await gate.request(),false,'does not guess a structure or launch whole label-map work');
assert.equal(starts,4);
desired=1; eligible=false;
assert.equal(await gate.request(),false,'unavailable/disabled label map cannot start work');
console.log('EXISTING_SEGMENTATION_GATE=PASS');
''', cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('EXISTING_SEGMENTATION_GATE=PASS', proc.stdout)

if __name__ == '__main__':
    unittest.main()
