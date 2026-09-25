#!/usr/bin/env node
// Synthetic public-descriptor acceptance for the two existing UI pathways.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(resolve(root, 'web/js/mri-study-prevolume.js'), 'utf8');
const { prevolumeMriWorkflow: qualify } = await import('data:text/javascript,' + encodeURIComponent(source));
const uid = '1.2.840.10008.1.2.3';
const mr = {
  study_id: 'a'.repeat(32), modalities: ['MR'],
  primary_series_uid: uid, reconstruction_series_uid: uid,
  reconstruction_ready: true, volume_ready: false,
  series: [{ series_instance_uid: uid, modality: 'MR', instance_count: 3,
    geometry: { reconstruction_ready: true } }],
};
for (const pathway of ['existing-sample-activation', 'new-upload']) {
  const study = { ...mr, origin: pathway === 'existing-sample-activation' ? { kind: 'sample' } : null };
  const waiting = qualify(study);
  assert.equal(waiting.state, 'waiting', pathway);
  assert.equal(waiting.model_id, 'total_mr', pathway);
  assert.equal(waiting.can_start, false, pathway);
  assert.equal(waiting.source_qualified, false, pathway);
  assert.match(waiting.message, /canonical patient volume/, pathway);
  assert.equal(qualify({ ...study, volume_ready: true }), null, pathway);
  assert.equal(qualify(study, { volumeBuildFailed: true }).state, 'unsupported', pathway);
  assert.match(qualify(study, { volumeBuildFailed: true }).message, /construction failed/, pathway);
  assert.equal(qualify({ ...study, reconstruction_ready: false,
    reconstruction_series_uid: null, series: [{ ...study.series[0], geometry: { reconstruction_ready: false } }] }).state,
    'unsupported', pathway);
}
assert.equal(qualify({ ...mr, modalities: ['CT'], series: [{ ...mr.series[0], modality: 'CT' }] }), null);
assert.equal(qualify({ ...mr, modalities: ['CT', 'MR'], series: [{ ...mr.series[0], modality: 'CT' }] }), null);
assert.equal(qualify(null), null);
const app = readFileSync(resolve(root, 'web/js/app.js'), 'utf8');
const index = readFileSync(resolve(root, 'web/index.html'), 'utf8');
const panelCode = readFileSync(resolve(root, 'web/js/segmentation-workflow-panel.js'), 'utf8');
assert.match(app, /import \{ prevolumeMriWorkflow \} from "\.\/mri-study-prevolume\.js\?v=phase6j-b2b-r1"/);
assert.match(app, /state\.study = study;[\s\S]*?prevolumeMriWorkflow\(study\);[\s\S]*?setWorkflowForStudy\(study\);/);
assert.match(app, /async function requestSampleLoad\([\s\S]*?applyStudy\(payload\.study\)/);
assert.match(app, /async function uploadDicomFiles\([\s\S]*?applyStudy\(payload\.study\)/);
assert.match(app, /const pendingMr = prevolumeMriWorkflow\(state\.study\)/);
assert.match(app, /volumeBuildFailed: true/);
assert.match(index, /phase6j-b1-r1-phase6j-b2b-r1(?:-phase6j-c4c-r1)?(?:-phase6j-d3-r1)?"/);
assert.match(panelCode, /state === "waiting"/);
class Element {
  constructor() { this.dataset={}; this.textContent=''; this.disabled=false;
    this.hidden=false; this.style={}; this.attributes={}; }
  addEventListener() {}
  setAttribute(key,value) { this.attributes[key]=value; }
}
globalThis.HTMLElement = Element;
const { SegmentationWorkflowPanel } = await import('data:text/javascript,' + encodeURIComponent(panelCode));
const nodes=new Map();
const container=new Element();
container.querySelector=(selector)=>{
  if (!nodes.has(selector)) nodes.set(selector,new Element());
  return nodes.get(selector);
};
const panel=new SegmentationWorkflowPanel(container);
panel.render({ ...qualify(mr), state: 'available', can_use: true, label_map_id:'l1' });
panel.render(qualify(mr));
assert.equal(nodes.get('#segmentationWorkflowPrimary').textContent,'Start Segmentation');
assert.equal(nodes.get('#segmentationWorkflowPrimary').disabled,true);
assert.equal(nodes.get('#segmentationWorkflowBadge').textContent,'Waiting');
assert.equal(nodes.get('#segmentationWorkflowProvider').textContent,'TotalSegmentator · MRI (total_mr)');
console.log('PHASE6J_B2B_SAMPLE_AND_UPLOAD_CONTRACT=PASS');
console.log('PHASE6J_B2B_UNSUPPORTED_AND_CT_ISOLATION=PASS');
console.log('PHASE6J_B2B_PREVOLUME_UI=PASS');
