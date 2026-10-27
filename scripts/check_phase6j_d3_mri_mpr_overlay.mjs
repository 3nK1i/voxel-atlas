#!/usr/bin/env node
// Synthetic browser checks. No patient data or model execution.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = path => readFileSync(resolve(root, path), 'utf8');

class Element {
  constructor() {
    this.dataset = {};
    this.textContent = '';
    this.disabled = false;
    this.hidden = false;
    this.style = {};
    this.attributes = {};
  }
  addEventListener() {}
  setAttribute(key, value) { this.attributes[key] = value; }
}
globalThis.HTMLElement = Element;

const panelSource = read('web/js/segmentation-workflow-panel.js');
const { SegmentationWorkflowPanel } = await import(
  'data:text/javascript,' + encodeURIComponent(panelSource)
);
const nodes = new Map();
const rootNode = new Element();
rootNode.querySelector = selector => {
  if (!nodes.has(selector)) nodes.set(selector, new Element());
  return nodes.get(selector);
};
const panel = new SegmentationWorkflowPanel(rootNode);
const readyMr = {
  study_id: 'a'.repeat(32),
  modality: 'MR',
  model_id: 'total_mr',
  presentation_only: true,
  mri_execution_authorized: false,
  mri_label_map_ready: true,
  state: 'available',
  can_start: false,
  can_use: true,
  label_map_id: 'map-' + 'd'.repeat(32),
  present_label_count: 50,
};
panel.render(readyMr);
assert.equal(nodes.get('#segmentationWorkflowPrimary').textContent, 'Use Segmentation');
assert.equal(nodes.get('#segmentationWorkflowPrimary').disabled, false);

panel.render({...readyMr, mri_label_map_ready: false, can_use: false, label_map_id: null, state: 'output_ready'});
assert.equal(nodes.get('#segmentationWorkflowPrimary').textContent, 'Start Segmentation');
assert.equal(nodes.get('#segmentationWorkflowPrimary').disabled, true);

const app = read('web/js/app.js');
assert.match(app, /mri_label_map_ready/);
assert.match(app, /activateSegmentationResult\(segmentationWorkflowSnapshot\.label_map_id\)/);
assert.match(app, /requestedLabelMapId !== segmentationWorkflowSnapshot\?\.label_map_id/);
assert.match(app, /descriptor\.provider_id !== \"totalsegmentator\"/);
assert.match(app, /isReadOnlyMri\(segmentationWorkflowSnapshot\)/);
assert.match(app, /\/api\/studies\/latest\/segmentation-overlay/);
const d3MprOnly = /D3 is MPR presentation only/.test(app);
const d4SurfaceReuse = /await refreshSegmentationSurfaceDescriptor\(descriptor\.label_map_id\)/.test(app);
assert.ok(d3MprOnly || d4SurfaceReuse);
if (d4SurfaceReuse) {
  assert.match(app, /descriptor\.source_modality !== "MR"/);
  assert.match(app, /descriptor\.model_id !== "total_mr"/);
}
assert.match(app, /descriptor\.source_modality === \"MR\"[\s\S]*segmentationCorrectionPanel\?\.clear\(\)/);
assert.match(read('web/index.html'), /phase6j-d3-r1(?:-phase6j-d4-r1)?/);

console.log('PHASE6J_D3_MRI_EXISTING_MAP_PRESENTATION=PASS');
console.log('PHASE6J_D3_MRI_EXECUTION_REMAINS_DISABLED=PASS');
console.log('PHASE6J_D3_MPR_OVERLAY_REUSE=PASS');
