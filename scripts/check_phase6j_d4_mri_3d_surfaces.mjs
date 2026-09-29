#!/usr/bin/env node
// Phase 6J-D4 synthetic browser contract. No patient data or model execution.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = path => readFileSync(resolve(root, path), 'utf8');
const app = read('web/js/app.js');
const index = read('web/index.html');
const surfaceViewer = read('web/js/segmentation-surface-viewer.js');
const structurePanel = read('web/js/segmentation-structure-panel.js');

// D3's explicit MRI 3D block must be removed in D4.
assert.doesNotMatch(app, /D3 is MPR presentation only/);
assert.doesNotMatch(app, /descriptor\.source_modality === "MR" && descriptor\.model_id === "total_mr"\) \{\s*\/\/ D3/);

// The exact activated map is reused for the existing segmentation-surface endpoint.
assert.match(app, /await refreshSegmentationSurfaceDescriptor\(descriptor\.label_map_id\)/);
assert.match(app, /descriptor\.label_map_id !== segmentationWorkflowSnapshot\?\.label_map_id/);
assert.match(app, /descriptor\.source_modality !== "MR"/);
assert.match(app, /descriptor\.provider_id !== "totalsegmentator"/);
assert.match(app, /descriptor\.model_id !== "total_mr"/);

// Reuse existing explicit structure-to-surface semantics; do not auto-build all labels.
assert.match(structurePanel, /surfaceVisible: false/);
assert.match(structurePanel, /activateSurfaceForStructure/);
assert.match(surfaceViewer, /presentation_quality/);
assert.match(surfaceViewer, /patientLpsToViewerMatrix/);
assert.match(surfaceViewer, /Select visible structures to add refined 3D surfaces/);

// Surface / Combined capability remains driven by resident segmentation geometry.
assert.match(app, /canPrepareAutomaticSegmentationSurface/);
assert.match(app, /segmentationDerivedResident/);
assert.match(app, /setSurfaceSource\("segmentation-derived"/);
assert.match(index, /phase6j-d4-r1/);

console.log('PHASE6J_D4_MRI_3D_SURFACE_BINDING=PASS');
console.log('PHASE6J_D4_EXPLICIT_STRUCTURE_SELECTION=PASS');
console.log('PHASE6J_D4_SURFACE_AND_COMBINED_INTEGRATION=PASS');
console.log('MRI_INFERENCE=NOT_RUN');
