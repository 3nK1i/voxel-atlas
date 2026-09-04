#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  PatientVolumeRayMarcher,
  aggregateMedicalProjection,
  listMedicalRenderingModes,
} from "../web/js/patient-volume-ray-marcher.js";


const samples = [-1000, -100, 40, 900];
assert.equal(aggregateMedicalProjection(samples, "mip"), 900);
assert.equal(aggregateMedicalProjection(samples, "minip"), -1000);
assert.equal(aggregateMedicalProjection(samples, "average"), -40);
assert.throws(() => aggregateMedicalProjection(samples, "dvr"), /front-to-back/);
assert.throws(() => aggregateMedicalProjection([], "mip"), /samples are invalid/);
assert.deepEqual(
  listMedicalRenderingModes().map(({ id, code }) => [id, code]),
  [["dvr", 0], ["mip", 1], ["minip", 2], ["average", 3]],
);

const descriptor = {
  ready: true,
  source_modality: "CT",
  source_intensity_units: "HU",
  source_value_range: [-1024, 2500],
  texture_dimensions: [512, 512, 112],
  texture_coordinate_to_patient_lps: [
    [512, 0, 0, -256],
    [0, 512, 0, -256],
    [0, 0, 112, -56],
    [0, 0, 0, 1],
  ],
  decode_offset: -1024,
  decode_scale: 3524 / 65535,
};

class FakeGeometry { dispose() {} }
class FakeMaterial {
  constructor(options) { Object.assign(this, options); }
  dispose() {}
}
class FakeMatrix4 { set(...elements) { this.elements = elements; return this; } }
class FakeMesh {
  constructor(geometry, material) {
    this.geometry = geometry;
    this.material = material;
    this.matrix = new FakeMatrix4();
  }
}
class FakeGroup {
  constructor() { this.children = []; this.userData = {}; }
  add(child) { this.children.push(child); child.parent = this; }
  remove(child) { this.children = this.children.filter((item) => item !== child); }
  updateMatrixWorld() {}
}
class FakeVector3 {
  constructor(x, y, z) { this.x = x; this.y = y; this.z = z; }
  set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
}
const THREE = {
  BackSide: "BackSide",
  BoxGeometry: FakeGeometry,
  GLSL3: "GLSL3",
  Group: FakeGroup,
  Matrix4: FakeMatrix4,
  Mesh: FakeMesh,
  NearestFilter: "NearestFilter",
  ShaderMaterial: FakeMaterial,
  Vector3: FakeVector3,
};

const texture = {};
const rayMarcher = new PatientVolumeRayMarcher({ three: THREE });
const resource = rayMarcher.create({ texture, descriptor });
const originalRoot = resource.root;
const originalMaterial = resource.material;
const originalTexture = resource.material.uniforms.uVolume.value;

for (const [modeId, code] of [["mip", 1], ["minip", 2], ["average", 3], ["dvr", 0]]) {
  const mode = rayMarcher.setRenderingMode(modeId);
  assert.equal(mode.id, modeId);
  assert.equal(resource.material.uniforms.uRenderingMode.value, code);
  assert.equal(rayMarcher.current.root, originalRoot);
  assert.equal(rayMarcher.current.material, originalMaterial);
  assert.equal(rayMarcher.current.material.uniforms.uVolume.value, originalTexture);
}

assert.equal(originalTexture, texture);
assert.throws(() => rayMarcher.setRenderingMode("surface"), /mode is invalid/);

console.log("SCALAR_PROJECTION_REFERENCE_VALUES=PASS");
console.log("MODE_SWITCH_USES_EXISTING_GPU_TEXTURE=YES");
console.log("PATIENT_VOLUME_RESOURCE_REUSED=YES");
console.log("PHASE4H3A_MEDICAL_PROJECTION_RENDERING_MODES=PASS");
