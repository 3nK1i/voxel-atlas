import assert from 'node:assert/strict';
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';

const root = process.cwd();
const appearance = await import(pathToFileURL(`${root}/web/js/segmentation-anatomical-appearance.js`).href);
const mriDisplay = await import(pathToFileURL(`${root}/web/js/mri-workflow-display.js`).href);

const structures = new Map([
  [1, {labelId: 1, name: 'lung_left', groupId: 'respiratory'}],
  [2, {labelId: 2, name: 'vertebrae', groupId: 'spine'}],
  [3, {labelId: 3, name: 'intervertebral_discs', groupId: 'spine'}],
  [4, {labelId: 4, name: 'brain', groupId: 'nervous_system'}],
  [5, {labelId: 5, name: 'spinal_cord', groupId: 'nervous_system'}],
]);
const presentation = {labelMapId: 'map-semantic', structures};

const semanticMr = appearance.resolve3dAppearanceContext('anatomical', {
  ready: true, label_map_id: 'map-semantic', source_modality: 'MR',
  provider_id: 'totalsegmentator', model_id: 'total_mr',
}, presentation);
assert.equal(semanticMr.ready, true);
assert.equal(semanticMr.overrides.size, 5);

const directMr = appearance.resolve3dAppearanceContext('anatomical', {
  ready: true, label_map_id: 'map-semantic', source_modality: 'MR',
  provider_id: 'voxelatlas', model_id: 'direct_mr',
}, presentation);
assert.equal(directMr.ready, false);
assert.equal(directMr.overrides.size, 0);

const ctPresentation = {labelMapId: 'map-ct', structures: new Map([
  [1, {labelId: 1, name: 'liver', groupId: 'organs'}],
  [2, {labelId: 2, name: 'vertebrae_C1', groupId: 'spine'}],
])};
const semanticCt = appearance.resolve3dAppearanceContext('anatomical', {
  ready: true, label_map_id: 'map-ct', source_modality: 'CT',
  provider_id: 'totalsegmentator', model_id: 'total',
}, ctPresentation);
assert.equal(semanticCt.ready, true);
assert.equal(semanticCt.overrides.size, 2);
const legacyCt = appearance.resolve3dAppearanceContext('anatomical', {
  ready: true, label_map_id: 'map-ct',
}, ctPresentation);
assert.equal(legacyCt.ready, true, 'existing CT appearance descriptor contract changed');
assert.equal(legacyCt.overrides.size, 2);

const enabledMr = {modality: 'MR', model_id: 'total_mr', presentation_only: false,
  study_id: 'study-a', source_series_uid: 'series-a'};
assert.equal(mriDisplay.isMriWorkflow(enabledMr), true);
assert.equal(mriDisplay.isReadOnlyMri(enabledMr), false);
assert.equal(mriDisplay.isReadOnlyMri({...enabledMr, presentation_only: true}), true);
assert.equal(mriDisplay.workflowMatchesStudy(enabledMr, {
  study_id: 'study-a', reconstruction_series_uid: 'series-a',
  series: [{series_instance_uid: 'series-a', modality: 'MR'}],
}), true);
assert.equal(mriDisplay.workflowMatchesStudy(enabledMr, {
  study_id: 'study-a', reconstruction_series_uid: 'series-b',
  series: [{series_instance_uid: 'series-b', modality: 'MR'}],
}), false);

const html = fs.readFileSync(`${root}/web/index.html`, 'utf8');
const css = fs.readFileSync(`${root}/web/css/styles.css`, 'utf8');
const panel = fs.readFileSync(`${root}/web/js/segmentation-workflow-panel.js`, 'utf8');
const app = fs.readFileSync(`${root}/web/js/app.js`, 'utf8');
const primary = html.match(/<button id="segmentationWorkflowPrimary"[^>]+>/)?.[0] ?? '';
const cancel = html.match(/<button id="segmentationWorkflowCancel"[^>]+>/)?.[0] ?? '';
assert.match(primary, /segmentation-workflow-action/);
assert.match(cancel, /segmentation-workflow-action/);
assert.doesNotMatch(cancel, /is-danger/);
assert.equal((css.match(/\.segmentation-workflow-action\s*\{/g) ?? []).length, 1,
  'workflow action footprint must have one canonical base style');
assert.match(css, /\.segmentation-workflow-action:hover:not\(:disabled\)/);
assert.match(css, /\.segmentation-workflow-action:focus-visible/);
assert.match(css, /\.segmentation-workflow-action:active:not\(:disabled\)/);
assert.match(css, /\.segmentation-workflow-action:disabled/);
assert.doesNotMatch(css, /\.segmentation-workflow-cancel:not\(:disabled\)/);
for (const label of ['Start Segmentation', 'Use Segmentation', 'Retry', 'Cancel']) {
  assert.match(panel, new RegExp(label.replace(' ', '\\s*')));
}
assert.match(app, /captureStudyLifecycle\(\)/);
assert.match(app, /studyLifecycleMatches\(lifecycle\)/);
assert.match(app, /workflowMatchesStudy\(workflow, state\.study\)/);

console.log('postdeploy MRI enablement browser contract: PASS');
