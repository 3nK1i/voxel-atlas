#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  PatientVolumeRayMarcher,
  createPatientClippingState,
} from "../web/js/patient-volume-ray-marcher.js";

const descriptor = {
  ready: true,
  revision: "4".repeat(64),
  source_modality: "CT",
  source_intensity_units: "HU",
  source_value_range: [-1024, 2500],
  texture_dimensions: [4, 3, 2],
  texture_coordinate_to_patient_lps: [
    [40, 0, 0, -20],
    [0, 60, 0, -30],
    [0, 0, 80, -40],
    [0, 0, 0, 1],
  ],
  patient_bounds_lps_mm: [-20, -30, -40, 20, 30, 40],
  decode_offset: -1024,
  decode_scale: 3524 / 65535,
};

const clipping = createPatientClippingState(descriptor, {
  axial: { enabled: true, minimumLpsMm: -20, maximumLpsMm: 25 },
  coronal: { enabled: true, minimumLpsMm: -12, maximumLpsMm: 18 },
  sagittal: { enabled: true, minimumLpsMm: -10, maximumLpsMm: 8 },
});

assert.deepEqual(clipping.enabled, [1, 1, 1]);
assert.deepEqual(clipping.minimumPositionsLpsMm, [-10, -12, -20]);
assert.deepEqual(clipping.maximumPositionsLpsMm, [8, 18, 25]);
assert.equal(clipping.sixPlaneCount, 6);

const fullBounds = createPatientClippingState(descriptor);
assert.deepEqual(fullBounds.enabled, [0, 0, 0]);
assert.deepEqual(fullBounds.minimumPositionsLpsMm, [-20, -30, -40]);
assert.deepEqual(fullBounds.maximumPositionsLpsMm, [20, 30, 40]);

assert.throws(
  () => createPatientClippingState(descriptor, {
    axial: { enabled: true, minimumLpsMm: -41, maximumLpsMm: 10 },
  }),
  /outside patient bounds/,
);
assert.throws(
  () => createPatientClippingState(descriptor, {
    coronal: { enabled: true, minimumLpsMm: 10, maximumLpsMm: 10 },
  }),
  /range is invalid/,
);
assert.throws(
  () => createPatientClippingState(descriptor, {
    sagittal: { enabled: true, minimumLpsMm: 12, maximumLpsMm: 2 },
  }),
  /range is invalid/,
);

class FakeGeometry { dispose() {} }
class FakeMaterial {
  constructor(options) { Object.assign(this, options); }
  dispose() {}
}
class FakeMatrix4 {
  set(...elements) { this.elements = elements; return this; }
}
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
  constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
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
const manager = new PatientVolumeRayMarcher({ three: THREE });
const resource = manager.create({ texture, descriptor });
const originalRoot = resource.root;
const originalMaterial = resource.material;
const originalTexture = resource.material.uniforms.uVolume.value;
const applied = manager.setClippingPlanes({
  axial: { enabled: true, minimumLpsMm: -20, maximumLpsMm: 25 },
  coronal: { enabled: true, minimumLpsMm: -12, maximumLpsMm: 18 },
  sagittal: { enabled: true, minimumLpsMm: -10, maximumLpsMm: 8 },
});

assert.deepEqual(Object.values(resource.material.uniforms.uClipPlaneEnabled.value), [1, 1, 1]);
assert.deepEqual(Object.values(resource.material.uniforms.uClipBoundsMinimum.value), [-10, -12, -20]);
assert.deepEqual(Object.values(resource.material.uniforms.uClipBoundsMaximum.value), [8, 18, 25]);
assert.equal(resource.root, originalRoot);
assert.equal(resource.material, originalMaterial);
assert.equal(resource.material.uniforms.uVolume.value, originalTexture);
assert.equal(originalTexture, texture);
assert.equal(resource.clippingState.current, applied);

console.log("PHASE4H4_DUAL_SIDED_PATIENT_LPS_CLIPPING=PASS");
