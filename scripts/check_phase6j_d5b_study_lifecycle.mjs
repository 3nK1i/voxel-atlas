#!/usr/bin/env node
// Phase 6J-D5B static browser lifecycle contract. No server, DICOM, GPU, or MRI inference.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(resolve(root, 'web/js/app.js'), 'utf8');
const index = readFileSync(resolve(root, 'web/index.html'), 'utf8');
const volumeViewer = readFileSync(resolve(root, 'web/js/volume-surface-viewer.js'), 'utf8');
const segmentationViewer = readFileSync(resolve(root, 'web/js/segmentation-surface-viewer.js'), 'utf8');

assert.match(index, /phase6j-d45c-r2-phase6j-d5b-r1"/);
assert.match(app, /let studyLifecycleGeneration = 0;/);
assert.match(app, /function invalidateStudyScopedAsyncState\(\)[\s\S]*?studyLifecycleGeneration \+= 1;[\s\S]*?mprDescriptorPromise = null;[\s\S]*?segmentationOverlayDescriptorPromise = null;[\s\S]*?segmentationSurfaceDescriptorPromise = null;[\s\S]*?volumeSurfaceDescriptorPromise = null;[\s\S]*?volumeBuildPromise = null;/);
assert.match(app, /function applyStudy\(study\)[\s\S]*?invalidateStudyScopedAsyncState\(\);[\s\S]*?state\.study = study;[\s\S]*?setMprVolumeState\(study\);/);
assert.match(app, /async function ensureCanonicalVolume\(study\)[\s\S]*?payload\.study\.study_id !== studyId[\s\S]*?if \(volumeBuildPromise === request\) volumeBuildPromise = null;/);
assert.match(app, /async function ensureMprReady\(\)[\s\S]*?captureStudyLifecycle\(\)[\s\S]*?studyLifecycleMatches\(lifecycle\)[\s\S]*?if \(mprDescriptorPromise === request\) mprDescriptorPromise = null;/);
assert.match(app, /async function refreshSegmentationOverlayDescriptor\(labelMapId\)[\s\S]*?studyLifecycleMatches\(lifecycle\)[\s\S]*?if \(segmentationOverlayDescriptorPromise === request\) segmentationOverlayDescriptorPromise = null;/);
assert.match(app, /async function refreshSegmentationSurfaceDescriptor\(labelMapId\)[\s\S]*?studyLifecycleMatches\(lifecycle\)[\s\S]*?if \(segmentationSurfaceDescriptorPromise === request\) segmentationSurfaceDescriptorPromise = null;/);
assert.match(volumeViewer, /generation !== this\.generation \|\| controller\.signal\.aborted/);
assert.match(segmentationViewer, /generation !== this\.generation \|\| controller\.signal\.aborted/);

const lifecycleStart = app.indexOf('function invalidateStudyScopedAsyncState() {');
const lifecycleEnd = app.indexOf('function syncSegmentation3dAppearance()', lifecycleStart);
const lifecycleBlock = app.slice(lifecycleStart, lifecycleEnd);
assert.doesNotMatch(lifecycleBlock, /requestSegmentationStart|segmentation-workflow\/start|fetch\(/);

console.log('PHASE6J_D5B_STUDY_TRANSITION_INVALIDATION=PASS');
console.log('PHASE6J_D5B_STALE_ASYNC_COMPLETIONS=GUARDED');
console.log('PHASE6J_D5B_RESIDENT_SURFACE_LAYERS=GENERATION_BOUND');
console.log('PHASE6J_D5B_MRI_INFERENCE=NOT_RUN');
console.log('PHASE6J_D5B_BROWSER_LIFECYCLE_OK=YES');
