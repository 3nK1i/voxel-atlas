#!/usr/bin/env node
// Synthetic DOM contract. No server, DICOM, weights, or GPU execution.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const code = readFileSync(resolve(root, 'web/js/segmentation-workflow-panel.js'), 'utf8');
const app = readFileSync(resolve(root, 'web/js/app.js'), 'utf8');
const index = readFileSync(resolve(root, 'web/index.html'), 'utf8');
assert.match(index, /ctb3a-r1-phase6j-b1-r1(?:-phase6j-b2b-r1)?(?:-phase6j-c4c-r1)?(?:-phase6j-d3-r1)?(?:-phase6j-d4-r1)?(?:-phase6j-d45c-r\d+)?(?:-phase6j-d5b-r\d+)?(?:-phase6j-d5c-r\d+)?\"/);
assert.match(app, /segmentation-workflow-panel\.js\?v=phase6d0-r1-phase6j-b1-r1/);
assert.doesNotMatch(code, /MRI segmentation provider is deferred to Phase 7/);

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
  setAttribute(k, v) { this.attributes[k] = v; }
}
globalThis.HTMLElement = Element;
const { SegmentationWorkflowPanel } = await import('data:text/javascript,' + encodeURIComponent(code));
const nodes = new Map();
const panelRoot = new Element();
panelRoot.querySelector = (selector) => {
  if (!nodes.has(selector)) nodes.set(selector, new Element());
  return nodes.get(selector);
};
const panel = new SegmentationWorkflowPanel(panelRoot);
const base = {
  provider_id: 'totalsegmentator', provider_available: false,
  can_cancel: false, can_start: false, can_use: false,
};
panel.render({...base, modality: 'MR', model_id: 'total_mr', state: 'unavailable',
  message: 'MRI TotalSegmentator total_mr provider is not qualified for execution'});
assert.equal(nodes.get('#segmentationWorkflowProvider').textContent, 'TotalSegmentator · MRI (total_mr)');
assert.equal(nodes.get('#segmentationWorkflowPrimary').disabled, true);
assert.match(nodes.get('#segmentationWorkflowStatus').textContent, /not qualified/);
panel.render({...base, modality: 'CT', model_id: 'total', state: 'idle',
  provider_available: true, can_start: true, message: 'Segmentation has not been started'});
assert.equal(nodes.get('#segmentationWorkflowProvider').textContent, 'TotalSegmentator · CT');
assert.equal(nodes.get('#segmentationWorkflowPrimary').disabled, false);
console.log('PHASE6J_B1_MRI_UI_GATING=PASS');
console.log('PHASE6J_B1_CT_UI_REGRESSION=PASS');
