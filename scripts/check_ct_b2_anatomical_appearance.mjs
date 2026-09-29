import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(resolve(root,'web/js/segmentation-anatomical-appearance.js'),'utf8');
const {build3dAnatomicalColorOverrides,resolve3dAppearanceContext} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const original = new Map([
 [98,{labelId:98,name:'rib_left_7',groupId:'skeletal',colorHex:'#00ff00',opacity:.42}],
 [34,{labelId:34,name:'vertebrae_T10',groupId:'spine',colorHex:'#221100',opacity:1}],
 [86,{labelId:86,name:'autochthon_left',groupId:'muscles',colorHex:'#00ffff',opacity:.5}],
 [117,{labelId:117,name:'costal_cartilages',groupId:'skeletal',colorHex:'#bbffff',opacity:1}],
 [1,{labelId:1,name:'spleen',groupId:'organs',colorHex:'#aabbcc',opacity:1}],
 [250,{labelId:250,name:'unclassified',groupId:'unrecognized_group',colorHex:'#ffffff',opacity:1}],
]);
const snapshot = new Map(Array.from(original,([id,s])=>[id,{...s}]));
const presentation = { labelMapId:'ct-label-map-1', structures:original };
const desc = {ready:true,label_map_id:'ct-label-map-1'};
const appearance = resolve3dAppearanceContext('anatomical',desc,presentation);
assert.equal(appearance.ready,true);
assert.equal(appearance.overrides.get(98),'#d8c9a5');
assert.equal(appearance.overrides.get(34),'#d8c9a5');
assert.equal(appearance.overrides.get(86),'#a66c62');
assert.notEqual(appearance.overrides.get(117),appearance.overrides.get(98),'Cartilage must not be painted as bone');
assert.ok(appearance.overrides.has(1),'CT-B3A intentionally expands the anatomical preset to recognized organs');
assert.equal(appearance.overrides.has(250),false,'Unknown structures must retain scientific color');
assert.deepEqual(original,snapshot,'Shared palette or opacity changed; MPR must remain unchanged');
const scientific = resolve3dAppearanceContext('scientific',desc,presentation);
assert.equal(scientific.ready,true);
assert.equal(scientific.overrides.size,0,'Scientific must remove all temporary 3D overrides');
assert.deepEqual(original,snapshot,'Scientific must not modify saved custom colors');
const other = resolve3dAppearanceContext('anatomical',{ready:true,label_map_id:'other-study'},presentation);
assert.equal(other.ready,false);
assert.equal(other.overrides.size,0,'No cross-study color override');
assert.equal(resolve3dAppearanceContext('anatomical',null,presentation).ready,false);
assert.throws(()=>resolve3dAppearanceContext('incorrect',desc,presentation),RangeError);
const empty = build3dAnatomicalColorOverrides({structures:new Map()});
assert.equal(empty.size,0);
console.log('CTB2_PALETTE_CLASSIFICATION=PASS');
console.log('CTB2_SCIENTIFIC_REVERSIBILITY_AND_MPR_ISOLATION=PASS');
console.log('CTB2_LABEL_MAP_GATING=PASS');
const html = readFileSync(resolve(root,'web/index.html'),'utf8');
const app = readFileSync(resolve(root,'web/js/app.js'),'utf8');
const css = readFileSync(resolve(root,'web/css/styles.css'),'utf8');
assert.match(html,/<select id="segmentation3dAppearance"[^>]*disabled>/);
assert.match(html,/<option value="scientific">Scientific colors<\/option>/);
assert.match(html,/<option value="anatomical">Anatomical colors<\/option>/);
assert.match(html,/3D colors only; MPR colors are unchanged/);
assert.match(html,/phase6i-d-r1-ctb2-r1/);
assert.match(app,/segmentation-anatomical-appearance\.js\?v=ctb2-r1/);
assert.match(app,/segmentation-surface-viewer\.js\?v=[^"\n]*ctb2-r1/);
assert.match(app,/segmentation3dAppearance\.addEventListener\("change"/);
assert.match(app,/segmentationSurfaceLayer\.set3dColorOverrides\(overrides\)/);
assert.match(app,/segmentation3dAppearanceLabelMapId !== nextLabelMapId/);
assert.match(app,/segmentation3dAppearanceMode = "scientific"/);
assert.match(app,/syncSegmentation3dAppearance\(\);[\s\S]*?syncSegmentationCorrectionContext\(presentation\)/);
assert.match(css,/\.segmentation-appearance-control select:focus-visible/);
console.log('CTB2_UI_AND_LIFECYCLE_WIRING=PASS');
// Execute the actual UI-sync function from app.js in an isolated dependency
// harness, so the test covers real selector state and the 3D-only setter.
const functionStart = app.indexOf('function syncSegmentation3dAppearance() {');
const functionEnd = app.indexOf('\nfunction syncSegmentationCorrectionContext(', functionStart);
assert.ok(functionStart > 0 && functionEnd > functionStart);
const syncSource = app.slice(functionStart, functionEnd);
const makeSync = new Function('deps', `
  const { resolve3dAppearanceContext, state, segmentation3dAppearance,
    segmentation3dAppearanceNote, segmentationSurfaceLayer,
    segmentation3dAppearanceMode } = deps;
  ${syncSource}
  return syncSegmentation3dAppearance;
`);
const select = {disabled:true,value:'scientific'};
const note = {textContent:''};
const applied=[];
const layer = {set3dColorOverrides(map) {applied.push(new Map(map));}};
const state = {segmentationSurface:{descriptor:desc},segmentationOverlay:{presentation}};
makeSync({resolve3dAppearanceContext,state,segmentation3dAppearance:select,
  segmentation3dAppearanceNote:note,segmentationSurfaceLayer:layer,
  segmentation3dAppearanceMode:'anatomical'})();
assert.equal(select.disabled,false);
assert.equal(select.value,'anatomical');
assert.equal(applied.at(-1).get(98),'#d8c9a5');
assert.match(note.textContent,/MPR colors are unchanged/);
makeSync({resolve3dAppearanceContext,state,segmentation3dAppearance:select,
  segmentation3dAppearanceNote:note,segmentationSurfaceLayer:layer,
  segmentation3dAppearanceMode:'scientific'})();
assert.equal(select.value,'scientific');
assert.equal(applied.at(-1).size,0);
assert.deepEqual(original,snapshot);
const calledBefore=applied.length;
state.segmentationSurface.descriptor={ready:true,label_map_id:'mismatch'};
makeSync({resolve3dAppearanceContext,state,segmentation3dAppearance:select,
  segmentation3dAppearanceNote:note,segmentationSurfaceLayer:layer,
  segmentation3dAppearanceMode:'anatomical'})();
assert.equal(select.disabled,true);
assert.equal(applied.length,calledBefore,'Stale study applied overrides');
console.log('CTB2_EXECUTED_UI_SYNC=PASS');
