#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  PatientVolumeRayMarcher,
  constrainPatientSliceSettings,
  listMedicalRenderingModes,
  listSlabProjectionMethods,
} from "../web/js/patient-volume-ray-marcher.js";


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
  patient_bounds_lps_mm: [-256, -256, -56, 256, 256, 56],
  decode_offset: -1024,
  decode_scale: 3524 / 65535,
};

assert.deepEqual(
  listMedicalRenderingModes().map(({ id, code }) => [id, code]),
  [
    ["dvr", 0], ["mip", 1], ["minip", 2], ["average", 3],
    ["slice", 4], ["thick-slab", 5],
  ],
);
assert.deepEqual(
  listSlabProjectionMethods().map(({ id, code }) => [id, code]),
  [["mip", 1], ["minip", 2], ["average", 3]],
);

const axial = constrainPatientSliceSettings(descriptor, {
  plane: "axial",
  positionLpsMm: 80,
  slabThicknessMm: 20,
  slabProjection: "average",
  sampleSpacingMm: 1.5,
});
assert.equal(axial.axisIndex, 2);
assert.equal(axial.positionLpsMm, 56);
assert.equal(axial.slabThicknessMm, 20);
assert.equal(axial.slabProjection, "average");
assert.equal(axial.sampleSpacingMm, 1.5);

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
const root = resource.root;
const material = resource.material;

rayMarcher.setRenderingMode("slice");
rayMarcher.setSliceRendering({
  plane: "coronal",
  positionLpsMm: -30,
  slabThicknessMm: 5,
  slabProjection: "mip",
  sampleSpacingMm: 1,
});
assert.equal(material.uniforms.uSlicePlaneAxis.value, 1);
assert.equal(material.uniforms.uSlicePositionLpsMm.value, -30);
assert.equal(material.uniforms.uVolume.value, texture);
assert.equal(rayMarcher.current.root, root);
assert.equal(rayMarcher.current.material, material);

rayMarcher.setRenderingMode("thick-slab");
const slab = rayMarcher.setSliceRendering({
  plane: "sagittal",
  positionLpsMm: 12,
  slabThicknessMm: 10,
  slabProjection: "minip",
  sampleSpacingMm: 0.8,
});
assert.equal(slab.axisIndex, 0);
assert.equal(material.uniforms.uSlabProjectionMode.value, 2);
assert.equal(material.uniforms.uSlabThicknessMm.value, 10);
assert.equal(material.uniforms.uVolume.value, texture);

console.log("PATIENT_LPS_SLICE_SETTINGS=PASS");
console.log("THICK_SLAB_PHYSICAL_MM=PASS");
console.log("SLICE_SLAB_REUSES_GPU_TEXTURE=YES");
console.log("PHASE4H3B_SLICE_AND_THICK_SLAB=PASS");
