#!/usr/bin/env node
// Executes extracted production clipping functions with synthetic Patient-LPS ranges.
// No server, patient file, or clinical validation is involved.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const app = readFileSync(new URL('../web/js/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../web/index.html', import.meta.url), 'utf8');
const get = name => {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `missing ${name}`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next < 0 ? undefined : next);
};
const constants = app.slice(app.indexOf('const CLIPPING_PLANES ='), app.indexOf('const clippingRegistry ='));
assert.ok(constants.includes('reversed: true'));
const state = { clipping: Object.fromEntries(['axial','coronal','sagittal'].map(p => [p, {enabled:false,startPercent:0,endPercent:100}])),
  mpr:{descriptor:{planes:{ axial:{position_range_mm:[-40,40]}, coronal:{position_range_mm:[-120,80]}, sagittal:{position_range_mm:[-60,60]} }}} };
const controls = new Map();
for (const plane of Object.keys(state.clipping)) {
  const holder={dataset:{clippingActive:'false'}};
  const makeSlider = value => ({value:String(value),disabled:true,attributes:{},setAttribute(k,v){this.attributes[k]=v}});
  controls.set(plane,{start:makeSlider(0),end:makeSlider(100),status:{dataset:{active:'false'},textContent:'Full range'},
    startPosition:{textContent:''},endPosition:{textContent:''},startPercent:{textContent:''},endPercent:{textContent:''},
    range:{closest(){return holder},style:{setProperty(){}}},holder});
}
const directionalCutPanel={dataset:{}};
const clippingResetButton={disabled:true};
let surfaceRequest, segmentationRequest, volumeRequest, overlayCount=0;
const runner=new Function('state','clippingRegistry','directionalCutPanel','clippingResetButton','readRequests',`${constants}
  const CLIPPING_MINIMUM_GAP_PERCENT=0.1;
  const volumeLayer={available:true};
  const volumeRayMarcher={current:true,setClippingPlanes(request){readRequests(request,'volume');return request}};
  const volumeSurfaceLayer={setClippingPlanes(request){readRequests(request,'direct')}};
  const segmentationSurfaceLayer={setClippingPlanes(request){readRequests(request,'segmentation')}};
  const updateMprClippingOverlays=()=>{};
  const requestViewerRender=()=>{};
  const syncSliceRenderingControlsFromMpr=()=>{};
  ${['clamp','clippingPlaneRange','clippingRangeIsActive','setClippingControlsEnabled','clippingBoundaryLpsMm','clippingRequest',
    'applyPatientClipping','syncClippingControlsFromMpr','updateClippingBoundaryFromControl','resetPatientClipping'].map(get).join('\n')}
  return {clippingRangeIsActive,clippingRequest,setClippingControlsEnabled,syncClippingControlsFromMpr,updateClippingBoundaryFromControl,resetPatientClipping};`);
const api=runner(state,controls,directionalCutPanel,clippingResetButton,(request,layer)=>{
  if(layer==='volume') volumeRequest=request;
  if(layer==='direct') surfaceRequest=request;
  if(layer==='segmentation') segmentationRequest=request;
});
const request=()=>JSON.parse(JSON.stringify(api.clippingRequest()));
api.syncClippingControlsFromMpr();
for (const [p,c] of controls) {
  assert.equal(c.start.disabled,false,`${p}: full-range start must be movable`);
  assert.equal(c.end.disabled,false,`${p}: full-range end must be movable`);
  assert.equal(c.status.textContent,'Full range');
  assert.equal(request()[p].enabled,false);
}
assert.equal(clippingResetButton.disabled,false);
for(const [plane,c] of controls) {
  c.start.value='20';api.updateClippingBoundaryFromControl(plane,'start');
  assert.equal(request()[plane].enabled,true,`${plane}: lower bound activates`);
  assert.equal(c.status.textContent,'Active');
  c.end.value='80';api.updateClippingBoundaryFromControl(plane,'end');
  assert.equal(request()[plane].enabled,true,`${plane}: both bounds activate`);
  assert.ok(request()[plane].maximumLpsMm>request()[plane].minimumLpsMm);
  assert.equal(c.end.disabled,false);
  c.start.value='0';api.updateClippingBoundaryFromControl(plane,'start');
  assert.equal(request()[plane].enabled,true,`${plane}: upper bound alone activates`);
  c.end.value='100';api.updateClippingBoundaryFromControl(plane,'end');
  assert.equal(request()[plane].enabled,false,`${plane}: full range deactivates`);
}
for(const [plane,c] of controls){c.start.value='12';api.updateClippingBoundaryFromControl(plane,'start');c.end.value='74';api.updateClippingBoundaryFromControl(plane,'end')}
const all=request();assert.ok(Object.values(all).every(p=>p.enabled));
assert.deepEqual(Object.values(all).map(p=>p.minimumLpsMm<p.maximumLpsMm),[true,true,true]);
// Posterior (start) is the higher LPS Y bound; preserve existing coronal reversal.
assert.equal(all.coronal.minimumLpsMm,-68);
assert.equal(all.coronal.maximumLpsMm,56);
assert.deepEqual(JSON.parse(JSON.stringify(surfaceRequest)),all);
assert.deepEqual(JSON.parse(JSON.stringify(segmentationRequest)),all);
assert.deepEqual(JSON.parse(JSON.stringify(volumeRequest)),all);
api.resetPatientClipping();
assert.ok(Object.values(request()).every(p=>!p.enabled));
assert.ok([...controls.values()].every(c=>c.status.textContent==='Full range'));
api.setClippingControlsEnabled(false);
assert.ok([...controls.values()].every(c=>c.start.disabled&&c.end.disabled));
assert.ok(!html.includes('type="checkbox" data-clip-enabled='));
assert.equal((html.match(/class="clip-plane-state"/g)||[]).length,3);
assert.ok(html.includes('id="mprClippingOverlayToggle"'));
console.log('PHASE6I_C_BOTH_BOUNDS_PER_PLANE=PASS');
console.log('PHASE6I_C_ALL_THREE_LPS_INTERSECTION_REQUESTS=PASS');
console.log('PHASE6I_C_FULL_RANGE_RESET_AND_NO_HIDDEN_CLIPPING=PASS');
