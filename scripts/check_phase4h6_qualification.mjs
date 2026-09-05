#!/usr/bin/env node
// Deterministic contracts use Three/DOM test doubles, not a real GPU.
import assert from 'node:assert/strict';
import { QualificationFrames, QUALIFICATION_MODES, isQualificationLocation,
  sanitizeRuntimeSnapshot, installRenderingQualification } from '../web/js/rendering-qualification.js';
import { PatientVolumeRayMarcher } from '../web/js/patient-volume-ray-marcher.js';

const frames = new QualificationFrames();
assert.equal(frames.snapshot().dvr.continuousFrameIntervalMs.p95Ms, null);
for (let i = 0; i < 20000; i++) frames.record(i * 16, 2, 'dvr', true, true);
assert.equal(frames.snapshot().dvr.totalRenderedFrames, 20000);
assert.equal(frames.snapshot().dvr.submittedCpuMs.count, 600);
assert.equal(frames.snapshot().dvr.continuousFrameIntervalMs.count, 600);
assert.equal(frames.snapshot().dvr.continuousFrameIntervalMs.p95Ms, 16);
frames.pause();
frames.record(1000000, 2, 'dvr', true, true);
assert.equal(frames.snapshot().dvr.continuousFrameIntervalMs.maximumMs, 16, 'idle time excluded');
frames.record(1001000, 2, 'dvr', true, true);
assert.equal(frames.snapshot().dvr.continuousFrameIntervalMs.maximumMs, 1000, 'foreground stall retained');
frames.record(1002000, 2, 'mip', true, true);
assert.equal(frames.snapshot().mip.continuousFrameIntervalMs.count, 0, 'mode-switch gap excluded');
frames.record(1003000, 2, 'mip', true, false);
frames.record(1004000, 2, 'mip', true, true);
assert.equal(frames.snapshot().mip.continuousFrameIntervalMs.count, 0, 'hidden-tab gap excluded');
frames.reset();
assert.equal(frames.snapshot().dvr.totalRenderedFrames, 0);

assert.ok(isQualificationLocation(new URL('http://127.0.0.1:8000/workspace?qualification=phase4h6')));
for (const url of ['https://em.eiatech.ma/workspace?qualification=phase4h6',
  'http://localhost/workspace', 'http://localhost.evil.test/?qualification=phase4h6',
  'file://localhost/workspace?qualification=phase4h6']) assert.equal(isQualificationLocation(new URL(url)), false);
const safe = sanitizeRuntimeSnapshot({ modality: 'CT', dimensions: [8,8,8], patientName: 'PRIVATE',
  revision: 'PRIVATE', ready: true, textures: 1, qualityPolicy: 'balanced' });
assert.ok(!JSON.stringify(safe).includes('PRIVATE'));
assert.equal(safe.geometries, null);

class Target {
  constructor() { this.listeners = new Map(); }
  addEventListener(name, fn) { this.listeners.set(name, fn); }
  removeEventListener(name) { this.listeners.delete(name); }
}
const win = new Target();
win.location = new URL('http://localhost/?qualification=phase4h6');
win.document = new Target();
const domElement = new Target();
const diagnostics = installRenderingQualification({window: win, renderer: {domElement}, readSnapshot: () => safe});
assert.throws(() => win.voxelatlasH6.capture('PATIENT_NAME'));
assert.throws(() => win.voxelatlasH6.capture('MR-1'));
for(let i=0;i<30;i++) win.voxelatlasH6.capture('CT-1');
assert.equal(win.voxelatlasH6.report().captures.length, 1, 'bounded capture slots');
win.listeners.get('error')({message:'PRIVATE'});
domElement.listeners.get('webglcontextlost')();
diagnostics.resetWindow();
assert.equal(win.voxelatlasH6.report().faults.windowErrors, 1, 'faults persist across studies');
assert.equal(win.voxelatlasH6.report().faults.contextLosses, 1);
assert.ok(!JSON.stringify(win.voxelatlasH6.report()).includes('PRIVATE'));
diagnostics.dispose();
assert.equal(win.voxelatlasH6, undefined);
assert.equal(win.listeners.size + win.document.listeners.size + domElement.listeners.size, 0);

let geometryCreated=0, geometryDisposed=0, materialCreated=0, materialDisposed=0;
class Geometry { constructor(){geometryCreated++;} dispose(){geometryDisposed++;} }
class Material {
  constructor(options){materialCreated++;Object.assign(this,options);}
  dispose(){materialDisposed++;}
}
class Matrix { set(...values){this.values=values;return this;} }
class Vector {
  constructor(...values){this.set(...values);}
  set(...values){[this.x,this.y,this.z]=values;return this;}
}
class Mesh { constructor(){this.matrix=new Matrix();} }
class Group {
  constructor(){this.children=[];this.userData={};}
  add(child){this.children.push(child);child.parent=this;}
  remove(child){this.children=this.children.filter((x)=>x!==child);child.parent=null;}
  updateMatrixWorld(){}
}
const three={BoxGeometry:Geometry,ShaderMaterial:Material,Matrix4:Matrix,Vector3:Vector,Mesh,Group,
  NearestFilter:1,GLSL3:3,BackSide:1};
const descriptor={ready:true,source_modality:'CT',source_intensity_units:'HU',source_value_range:[-1024,2500],
  texture_dimensions:[512,512,112],decode_offset:-1024,decode_scale:3524/65535,
  texture_coordinate_to_patient_lps:[[512,0,0,-256],[0,512,0,-256],[0,0,112,-56],[0,0,0,1]],
  patient_bounds_lps_mm:[-256,-256,-56,256,256,56]};
const original=JSON.stringify(descriptor);
const marcher=new PatientVolumeRayMarcher({three});
const scene=new Group();
let uploads=0;
const texture={set needsUpdate(value){if(value)uploads++;},dispose(){throw new Error('Texture owned by manager');}};
const first=marcher.create({descriptor,texture});scene.add(first.root);
assert.throws(()=>marcher.create({texture,descriptor:{...descriptor,texture_coordinate_to_patient_lps:null}}));
assert.equal(marcher.current,first,'invalid replacement must not dispose the current valid volume');
assert.equal(geometryDisposed,0);
for(let cycle=0;cycle<100;cycle++) {
  const resource=marcher.create({descriptor:{...descriptor,source_modality:cycle%2?'MR':'CT'},texture});
  scene.add(resource.root);
  const uploadCount=uploads;
  for (const mode of QUALIFICATION_MODES) {
    marcher.setRenderingMode(mode);
    marcher.setOpacity(0.6);
    marcher.setSamplingRate(cycle%2?512:128);
    marcher.setTransferPreset(null,{windowWidth:400,windowCenter:40});
    for(const plane of ['axial','coronal','sagittal']) for(const method of ['mip','minip','average']) {
      marcher.setSliceRendering({plane,positionLpsMm:0,slabThicknessMm:20,slabProjection:method});
      marcher.setClippingPlanes({[plane]:{enabled:true,minimumLpsMm:-10,maximumLpsMm:10}});
    }
    assert.equal(marcher.current.material,resource.material);
    assert.equal(resource.material.uniforms.uVolume.value,texture);
  }
  assert.equal(uploads,uploadCount,'controls must not re-upload canonical texture');
  assert.equal(scene.children.length,1,'old root removed on study replacement');
  assert.equal(geometryCreated-geometryDisposed,1);
  assert.equal(materialCreated-materialDisposed,1);
}
marcher.dispose();marcher.dispose();
assert.equal(scene.children.length,0);
assert.equal(geometryCreated,geometryDisposed);
assert.equal(materialCreated,materialDisposed);
assert.equal(JSON.stringify(descriptor),original,'source descriptor unchanged');
console.log('BOUNDED_FRAME_EVIDENCE=PASS');
console.log('LOCAL_ONLY_PRIVACY_AND_LISTENER_CLEANUP=PASS');
console.log('INVALID_REPLACEMENT_PRESERVES_CURRENT_VOLUME=PASS');
console.log('REPEATED_RENDERER_LIFECYCLE_100_CYCLES=PASS');
console.log('CONTROL_CHANGES_TEXTURE_REUPLOADS=0');
console.log('PHASE4H6_DETERMINISTIC_QUALIFICATION=PASS');
