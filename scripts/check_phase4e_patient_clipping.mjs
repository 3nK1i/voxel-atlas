#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  PatientVolumeRayMarcher,
  createPatientClippingState,
  listMedicalTransferPresets,
} from "../web/js/patient-volume-ray-marcher.js";


const descriptor = {
  ready: true,
  revision: "f".repeat(64),
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
  axial: { enabled: true, minimumLpsMm: -15, maximumLpsMm: 5 },
  coronal: { enabled: true, minimumLpsMm: -7, maximumLpsMm: 12 },
  sagittal: { enabled: true, minimumLpsMm: 3, maximumLpsMm: 14 },
});

assert.deepEqual(clipping.enabled, [1, 1, 1]);
assert.deepEqual(clipping.minimumPositionsLpsMm, [3, -7, -15]);
assert.deepEqual(clipping.maximumPositionsLpsMm, [14, 12, 5]);
assert.equal(clipping.sixPlaneCount, 6);
assert.equal(clipping.planes.axial.axis, "z");
assert.equal(clipping.planes.coronal.axis, "y");
assert.equal(clipping.planes.sagittal.axis, "x");
assert.throws(
  () => createPatientClippingState(descriptor, {
    axial: { enabled: true, minimumLpsMm: -15, maximumLpsMm: 41 },
  }),
  /range is outside patient bounds/,
);

const ctPresets = listMedicalTransferPresets(descriptor);
const lowDensity = ctPresets.find(({ id }) => id === "ct-lung");
assert.equal(lowDensity.label, "Low-Density CT");

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

const manager = new PatientVolumeRayMarcher({ three: THREE });
const resource = manager.create({ texture: {}, descriptor });
const applied = manager.setClippingPlanes({
  axial: { enabled: true, minimumLpsMm: -15, maximumLpsMm: 5 },
  coronal: { enabled: true, minimumLpsMm: -7, maximumLpsMm: 12 },
  sagittal: { enabled: true, minimumLpsMm: 3, maximumLpsMm: 14 },
});

assert.deepEqual(
  Object.values(resource.material.uniforms.uClipPlaneEnabled.value),
  [1, 1, 1],
);
assert.deepEqual(
  Object.values(resource.material.uniforms.uClipBoundsMinimum.value),
  [3, -7, -15],
);
assert.deepEqual(
  Object.values(resource.material.uniforms.uClipBoundsMaximum.value),
  [14, 12, 5],
);
assert.equal(applied.planes.coronal.maximumLpsMm, 12);
assert.equal(resource.clippingState.current, applied);

manager.setClippingPlanes({});
assert.deepEqual(
  Object.values(resource.material.uniforms.uClipPlaneEnabled.value),
  [0, 0, 0],
);

console.log("PHASE4E_MULTIPLANE_PATIENT_SPACE_CLIPPING=PASS");
