#!/usr/bin/env node
// Same-study presentation lifecycle probe. No server, DICOM, GPU, or inference.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const modeSource = readFileSync(resolve(root, 'web/js/reconstruction-visualization-mode.js'), 'utf8');
const app = readFileSync(resolve(root, 'web/js/app.js'), 'utf8');
const index = readFileSync(resolve(root, 'web/index.html'), 'utf8');

assert.match(index, /phase6j-d5b-r1-phase6j-d5c-r1"/);
assert.match(app, /sourceId === "volume-derived"[\s\S]*?result\?\.mode !== "volume"[\s\S]*?!volumeSurfaceLayer\.current[\s\S]*?ensureAutomaticDirectVolumeSurface\(\)/);

const start = app.indexOf('function requestReconstructionSurfaceSourceSelection(sourceId, selected) {');
const end = app.indexOf('function setVolumeAvailability(available) {', start);
const selectionBlock = app.slice(start, end);
assert.doesNotMatch(selectionBlock, /requestSegmentationStart|segmentation-workflow\/start/);

const moduleUrl = 'data:text/javascript,' + encodeURIComponent(modeSource);
const { ReconstructionVisualizationModeController } = await import(moduleUrl);
const controller = new ReconstructionVisualizationModeController();
controller.setVolumeAvailable(true);
controller.setSurfaceSource('volume-derived', { available: true, resident: true, selected: true });
controller.setSurfaceSource('segmentation-derived', { available: true, resident: true, selected: true });

assert.equal(controller.requestMode('surface').accepted, true);
let snapshot = controller.snapshot();
assert.equal(snapshot.visibility.volume, false);
assert.equal(snapshot.visibility.surfaceSources['volume-derived'], true);
assert.equal(snapshot.visibility.surfaceSources['segmentation-derived'], true);

controller.selectSurfaceSource('volume-derived', false);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, 'surface');
assert.equal(snapshot.surfaceSources['volume-derived'].resident, true, 'hiding Direct must preserve resident geometry');
assert.equal(snapshot.visibility.surfaceSources['volume-derived'], false);
assert.equal(snapshot.visibility.surfaceSources['segmentation-derived'], true);

controller.selectSurfaceSource('volume-derived', true);
snapshot = controller.snapshot();
assert.equal(snapshot.visibility.surfaceSources['volume-derived'], true, 'reselect resident Direct without rebuilding');

assert.equal(controller.requestMode('combined').accepted, true);
snapshot = controller.snapshot();
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.visibility.surfaceSources['volume-derived'], true);
assert.equal(snapshot.visibility.surfaceSources['segmentation-derived'], true);

assert.equal(controller.requestMode('volume').accepted, true);
snapshot = controller.snapshot();
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.visibility.surfaceSources['volume-derived'], false);
assert.equal(snapshot.visibility.surfaceSources['segmentation-derived'], false);
assert.deepEqual([...snapshot.residentSurfaceSources].sort(), ['segmentation-derived', 'volume-derived'].sort());

assert.equal(controller.requestMode('surface').accepted, true);
snapshot = controller.snapshot();
assert.equal(snapshot.visibility.surfaceSources['volume-derived'], true);
assert.equal(snapshot.visibility.surfaceSources['segmentation-derived'], true);

console.log('PHASE6J_D5C_SAME_STUDY_COEXISTENCE=PASS');
console.log('PHASE6J_D5C_DIRECT_RESELECTION=RESIDENT_REUSED');
console.log('PHASE6J_D5C_MODE_TRANSITIONS=PRESENTATION_ONLY');
console.log('PHASE6J_D5C_MRI_INFERENCE=NOT_RUN');
console.log('PHASE6J_D5C_BROWSER_LIFECYCLE_OK=YES');
