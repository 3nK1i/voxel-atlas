import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const appearanceSource = readFileSync(resolve(root, 'web/js/segmentation-anatomical-appearance.js'), 'utf8');
const viewerSource = readFileSync(resolve(root, 'web/js/segmentation-surface-viewer.js'), 'utf8');
const presentationSource = readFileSync(resolve(root, 'web/js/reconstruction-surface-presentation.js'), 'utf8');
const appSource = readFileSync(resolve(root, 'web/js/app.js'), 'utf8');
const html = readFileSync(resolve(root, 'web/index.html'), 'utf8');

const asModule = (source) => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const appearance = await import(asModule(appearanceSource));
const surfacePresentation = await import(asModule(presentationSource));

// Load the actual segmentation surface layer with pure dependency shims. The test
// uses resident in-memory materials only: no backend, patient data, geometry build,
// or segmentation inference is invoked.
const withoutImports = viewerSource.replace(
  /^import\s*\{[\s\S]*?\}\s*from\s*"[^"]+";\s*$/gm,
  '',
);
globalThis.__voxelatlasColorIntegration = surfacePresentation;
const viewerShim = `
const { applySegmentationSurfaceMaterialProfile, createSegmentationSurfaceMaterial,
  getSurfacePresentationProfile } = globalThis.__voxelatlasColorIntegration;
const resolveStructureInteraction = (presentation, labelId) => ({
  effectiveSurfaceVisible: Boolean(presentation?.structures?.get(labelId)?.surfaceVisible),
  explodedOffsetLpsMm: [0, 0, 0], clippingEnabled: true,
});
const patientLpsOffsetToViewer = () => [0, 0, 0];
const applySurfaceClippingToMaterial = () => {};
const segmentationViewerWinding = (indices) => indices;
`;
const { PatientSegmentationSurfaceLayer } = await import(asModule(viewerShim + withoutImports));
delete globalThis.__voxelatlasColorIntegration;

class Color {
  constructor(value) { this.value = value; }
  set(value) { this.value = value; }
}
class Material {
  constructor(options) {
    Object.assign(this, options);
    this.color = new Color(options.color);
    this.emissive = new Color(options.emissive);
  }
  dispose() {}
}
const three = {
  BufferGeometry: class {},
  Mesh: class {},
  MeshStandardMaterial: Material,
  Group: class {
    constructor() { this.userData = {}; this.visible = true; }
    add() {}
    remove() {}
  },
  FrontSide: 0,
  DoubleSide: 2,
};

const layer = new PatientSegmentationSurfaceLayer({
  three,
  parent: { add() {} },
  fetchImpl: async () => { throw new Error('Network is forbidden in the semantic-color integration test'); },
  requestRender: () => {},
});

function installResidentSemanticSurface({ descriptor, structure }) {
  layer.setDescriptor({
    ready: true,
    coordinate_system: 'patient_lps',
    label_map_id: descriptor.label_map_id,
    present_labels: [structure.labelId],
  });
  const presentation = {
    labelMapId: descriptor.label_map_id,
    structures: new Map([[structure.labelId, structure]]),
    selectedLabelId: structure.labelId,
  };
  layer.presentation = presentation;
  layer.desiredLabels = new Set([structure.labelId]);
  const material = surfacePresentation.createSegmentationSurfaceMaterial(
    three,
    structure,
    'presentation',
    true,
  );
  layer.items.set(structure.labelId, {
    labelId: structure.labelId,
    material,
    geometry: { dispose() {} },
    mesh: { visible: true, position: { set() {} }, userData: {} },
  });
  return { presentation, material };
}

// Execute the actual app-level synchronization function against the actual viewer layer.
const syncStart = appSource.indexOf('function syncSegmentation3dAppearance() {');
const syncEnd = appSource.indexOf('\nfunction syncSegmentationCorrectionContext(', syncStart);
assert.ok(syncStart > 0 && syncEnd > syncStart, 'Unable to locate the application appearance sync');
const syncSource = appSource.slice(syncStart, syncEnd);
const buildSync = new Function('deps', `
  const { resolve3dAppearanceContext, state, segmentation3dAppearance,
    segmentation3dAppearanceNote, segmentationSurfaceLayer,
    segmentation3dAppearanceMode } = deps;
  ${syncSource}
  return syncSegmentation3dAppearance;
`);

function runSync(mode, descriptor, presentation) {
  const select = { disabled: true, value: 'scientific' };
  const note = { textContent: '' };
  const state = {
    segmentationSurface: { descriptor },
    segmentationOverlay: { presentation },
  };
  buildSync({
    resolve3dAppearanceContext: appearance.resolve3dAppearanceContext,
    state,
    segmentation3dAppearance: select,
    segmentation3dAppearanceNote: note,
    segmentationSurfaceLayer: layer,
    segmentation3dAppearanceMode: mode,
  })();
  return { select, note };
}

const ctDescriptor = {
  ready: true,
  label_map_id: 'ct-semantic-map',
  source_modality: 'CT',
  provider_id: 'totalsegmentator',
  model_id: 'total',
};
const ctStructure = {
  labelId: 5,
  name: 'liver',
  groupId: 'organs',
  colorHex: '#31ff52',
  opacity: 0.72,
  visible: true,
  surfaceVisible: true,
};
const { presentation: ctPresentation, material: ctMaterial } = installResidentSemanticSurface({
  descriptor: ctDescriptor,
  structure: ctStructure,
});
const ctScientific = ctStructure.colorHex;
const ctAnatomical = appearance.build3dAnatomicalColorOverrides(ctPresentation).get(5);
assert.ok(ctAnatomical && ctAnatomical !== ctScientific);
let result = runSync('anatomical', ctDescriptor, ctPresentation);
assert.equal(result.select.disabled, false);
assert.equal(ctMaterial.color.value, ctAnatomical, 'Resident semantic CT mesh did not acquire anatomical color');
assert.equal(ctStructure.colorHex, ctScientific, 'CT MPR/shared scientific color was mutated');
result = runSync('scientific', ctDescriptor, ctPresentation);
assert.equal(ctMaterial.color.value, ctScientific, 'CT Scientific mode did not restore the original structure color');
assert.equal(ctStructure.colorHex, ctScientific);

const mrDescriptor = {
  ready: true,
  label_map_id: 'mr-semantic-map',
  source_modality: 'MR',
  provider_id: 'totalsegmentator',
  model_id: 'total_mr',
};
const mrStructure = {
  labelId: 1,
  name: 'lung_left',
  groupId: 'respiratory',
  colorHex: '#ff4b31',
  opacity: 0.64,
  visible: true,
  surfaceVisible: true,
};
const { presentation: mrPresentation, material: mrMaterial } = installResidentSemanticSurface({
  descriptor: mrDescriptor,
  structure: mrStructure,
});
const mrScientific = mrStructure.colorHex;
const mrAnatomical = appearance.build3dAnatomicalColorOverrides(mrPresentation).get(1);
assert.ok(mrAnatomical && mrAnatomical !== mrScientific);
result = runSync('anatomical', mrDescriptor, mrPresentation);
assert.equal(result.select.disabled, false);
assert.equal(mrMaterial.color.value, mrAnatomical, 'Resident semantic MRI mesh did not acquire anatomical color');
assert.equal(mrStructure.colorHex, mrScientific, 'MRI MPR/shared scientific color was mutated');
result = runSync('scientific', mrDescriptor, mrPresentation);
assert.equal(mrMaterial.color.value, mrScientific, 'MRI Scientific mode did not restore the original structure color');

const directMr = appearance.resolve3dAppearanceContext('anatomical', {
  ...mrDescriptor,
  provider_id: 'voxelatlas',
  model_id: 'direct_mr',
}, mrPresentation);
assert.equal(directMr.ready, false);
assert.equal(directMr.overrides.size, 0, 'Direct MR acquired semantic anatomical colors');

// Production-delivery regression: every browser asset changed or relied upon by
// this hotfix must get a new immutable URL token. Starlette StaticFiles is mounted
// directly, so reusing old module URLs can leave an already-open browser on stale JS/CSS.
const HOTFIX_TOKEN = 'postdeploy-mri-colors-r1';
assert.match(html, new RegExp(`styles\\.css\\?v=[^"\\n]*${HOTFIX_TOKEN}`), 'Hotfix CSS cache token is missing');
assert.match(html, new RegExp(`app\\.js\\?v=[^"\\n]*${HOTFIX_TOKEN}`), 'Hotfix app cache token is missing');
for (const moduleName of [
  'mri-workflow-display.js',
  'segmentation-anatomical-appearance.js',
  'segmentation-surface-viewer.js',
  'segmentation-workflow-panel.js',
]) {
  const escaped = moduleName.replace('.', '\\.');
  assert.match(appSource, new RegExp(`${escaped}\\?v=[^"\\n]*${HOTFIX_TOKEN}`), `${moduleName} cache token is missing`);
}

console.log('POSTDEPLOY_CT_ANATOMICAL_RESIDENT_MESH=PASS');
console.log('POSTDEPLOY_MRI_ANATOMICAL_RESIDENT_MESH=PASS');
console.log('POSTDEPLOY_DIRECT_MR_SEMANTIC_COLOR_EXCLUSION=PASS');
console.log('POSTDEPLOY_SCIENTIFIC_REVERSIBILITY=PASS');
console.log('POSTDEPLOY_FRONTEND_CACHE_REVISION=PASS');
