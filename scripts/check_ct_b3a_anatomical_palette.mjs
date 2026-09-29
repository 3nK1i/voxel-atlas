import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(resolve(root, 'web/js/segmentation-anatomical-appearance.js'), 'utf8');
const { build3dAnatomicalColorOverrides, resolve3dAppearanceContext } =
  await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const taxonomy = readFileSync(resolve(root, 'backend/voxelatlas/segmentation_structures.py'), 'utf8');
const matches = Array.from(taxonomy.matchAll(/^\s{4}(\d+): "([^"]+)",?$/gm));
assert.equal(matches.length, 117, 'Expected the full pinned TotalSegmentator total-task taxonomy');
function groupFor(id) {
  if (id >= 10 && id <= 14 || id === 16) return 'respiratory';
  if (id >= 25 && id <= 50) return 'spine';
  if (id >= 51 && id <= 68) return 'cardiovascular';
  if (id >= 69 && id <= 78 || id >= 91 && id <= 117) return 'skeletal';
  if (id === 79 || id === 90) return 'nervous_system';
  if (id >= 80 && id <= 89) return 'muscles';
  if (id >= 1 && id <= 24) return 'organs';
  return 'other';
}
const structures = new Map(matches.map(([, idText, name]) => {
  const labelId = Number(idText);
  return [labelId, { labelId, name, groupId: groupFor(labelId), colorHex: '#00ff00', opacity: .7 }];
}));
const original = new Map(Array.from(structures, ([id, s]) => [id, {...s}]));
const presentation = { labelMapId: 'ct-b3a-test', structures };
const overrides = build3dAnatomicalColorOverrides(presentation);
assert.equal(overrides.size, 117, 'The canonical 117-label total-task taxonomy must be covered without fallback colors');
for (const [id, color] of overrides) {
  assert.match(color, /^#[0-9a-f]{6}$/i);
  assert.notEqual(color.toLowerCase(), '#00ff00', `Scientific color leaked for label ${id}`);
}
const boneColor = overrides.get(98);
for (const id of [25, 26, 43, 69, 71, 73, 75, 77, 91, 92, 104, 116]) {
  assert.equal(overrides.get(id), boneColor, `Expected canonical bone color at label ${id}`);
}
assert.notEqual(overrides.get(117), boneColor, 'Costal cartilage must not be misrepresented as bone');
assert.notEqual(overrides.get(5), boneColor, 'Liver must not receive bone color');
assert.notEqual(overrides.get(10), boneColor, 'Lung must not receive bone color');
assert.notEqual(overrides.get(51), boneColor, 'Heart must not receive bone color');
assert.notEqual(overrides.get(5), overrides.get(1), 'Liver and spleen need differentiated anatomical colors');
assert.notEqual(overrides.get(52), overrides.get(62), 'Arterial and venous presentation must be distinguished');
console.log('CTB3A_CANONICAL_CT_ANATOMICAL_COVERAGE=PASS');

const unknown = {labelId:250,name:'unknown_organ',groupId:'organs',colorHex:'#12cd56',opacity:.3};
structures.set(250, unknown);
assert.equal(build3dAnatomicalColorOverrides(presentation).has(250), false, 'Unknown labels must not be assigned invented anatomy');
assert.equal(structures.get(250).colorHex, '#12cd56');
assert.deepEqual(new Map(Array.from(structures, ([id, s]) => [id, {...s}])).get(5), original.get(5), 'Shared color/opacity must be unchanged');
const ready = {ready:true,label_map_id:'ct-b3a-test'};
const anatomical = resolve3dAppearanceContext('anatomical', ready, presentation);
assert.equal(anatomical.ready, true);
assert.equal(anatomical.overrides.size, 117);
assert.equal(resolve3dAppearanceContext('scientific', ready, presentation).overrides.size, 0);
assert.equal(resolve3dAppearanceContext('anatomical', {ready:true,label_map_id:'another-study'}, presentation).overrides.size, 0);
assert.deepEqual(new Map(Array.from(structures, ([id, s]) => [id, {...s}])).get(98), original.get(98), 'Scientific colors and opacity must not be mutated');
console.log('CTB3A_MPR_PALETTE_AND_LABEL_MAP_ISOLATION=PASS');

const app = readFileSync(resolve(root, 'web/js/app.js'), 'utf8');
const html = readFileSync(resolve(root, 'web/index.html'), 'utf8');
assert.match(app, /segmentation-anatomical-appearance\.js\?v=ctb2-r1-ctb3a-r1/);
assert.match(html, /\/js\/app\.js\?v=[^"\n]*ctb2-r1-ctb3a-r1/);
assert.match(app, /segmentationSurfaceLayer\.set3dColorOverrides\(overrides\)/);
console.log('CTB3A_BROWSER_CACHE_AND_EXISTING_3D_OVERRIDE_WIRING=PASS');
