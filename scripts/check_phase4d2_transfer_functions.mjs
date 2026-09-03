#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  PatientVolumeRayMarcher,
  createMedicalTransferFunction,
  listMedicalTransferPresets,
} from "../web/js/patient-volume-ray-marcher.js";


const ctDescriptor = {
  ready: true,
  revision: "d".repeat(64),
  source_modality: "CT",
  source_intensity_units: "HU",
  source_value_range: [-1024, 2500],
  texture_dimensions: [4, 3, 2],
  texture_coordinate_to_patient_lps: [
    [4, 0, 0, 10],
    [0, 6, 0, 20],
    [0, 0, 8, 30],
    [0, 0, 0, 1],
  ],
  decode_offset: -1024,
  decode_scale: 3524 / 65535,
};

const mrDescriptor = {
  ...ctDescriptor,
  revision: "e".repeat(64),
  source_modality: "MR",
  source_intensity_units: "modality",
  source_value_range: [0, 4095],
  decode_offset: 0,
  decode_scale: 4095 / 65535,
};

const ctPresets = listMedicalTransferPresets(ctDescriptor);
assert.deepEqual(
  ctPresets.map(({ id }) => id),
  ["ct-general", "ct-soft-tissue", "ct-bone", "ct-lung"],
);
assert.ok(ctPresets.every(({ modality }) => modality === "CT"));

const mrPresets = listMedicalTransferPresets(mrDescriptor);
assert.deepEqual(
  mrPresets.map(({ id }) => id),
  ["mr-balanced", "mr-lower-intensity", "mr-higher-intensity"],
);
assert.ok(mrPresets.every(({ modality }) => modality === "MR"));
assert.ok(mrPresets.every(({ units }) => units === "modality"));

const bone = createMedicalTransferFunction(ctDescriptor, "ct-bone");
assert.equal(bone.id, "ct-bone");
assert.equal(bone.units, "HU");
assert.equal(bone.controlPoints.length, 6);
assert.ok(bone.rangeLow >= ctDescriptor.source_value_range[0]);
assert.ok(bone.rangeHigh <= ctDescriptor.source_value_range[1]);
assert.ok(bone.rangeHigh > bone.rangeLow);
for (let index = 1; index < bone.controlPoints.length; index += 1) {
  assert.ok(
    bone.controlPoints[index].intensity > bone.controlPoints[index - 1].intensity,
    "transfer intensities must be strictly increasing",
  );
}

const adjusted = createMedicalTransferFunction(ctDescriptor, "ct-bone", {
  rangeLow: 275,
  rangeHigh: 1675,
  densityMultiplier: 1.35,
});
assert.equal(adjusted.rangeLow, 275);
assert.equal(adjusted.rangeHigh, 1675);
assert.equal(adjusted.densityMultiplier, 1.35);
assert.ok(adjusted.densityScale > bone.densityScale);
assert.throws(
  () => createMedicalTransferFunction(ctDescriptor, "mr-balanced"),
  /preset is invalid/,
);
assert.throws(
  () => createMedicalTransferFunction(ctDescriptor, "ct-bone", {
    rangeLow: 500,
    rangeHigh: 500,
  }),
  /intensity range is invalid/,
);
assert.throws(
  () => createMedicalTransferFunction(ctDescriptor, "ct-bone", {
    densityMultiplier: 2.01,
  }),
  /density is invalid/,
);

class FakeGeometry {
  dispose() {}
}

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
  constructor(x, y, z) { this.x = x; this.y = y; this.z = z; }
}

const THREE = {
  BackSide: "BackSide",
  BoxGeometry: FakeGeometry,
  GLSL3: "GLSL3",
  Group: FakeGroup,
  Mesh: FakeMesh,
  NearestFilter: "NearestFilter",
  ShaderMaterial: FakeMaterial,
  Vector3: FakeVector3,
};

const manager = new PatientVolumeRayMarcher({ three: THREE });
const resource = manager.create({ texture: {}, descriptor: ctDescriptor });
const applied = manager.setTransferPreset("ct-soft-tissue", {
  rangeLow: -125,
  rangeHigh: 275,
  densityMultiplier: 0.8,
});

assert.equal(resource.transferState.current.id, "ct-soft-tissue");
assert.equal(applied.rangeLow, -125);
assert.equal(resource.material.uniforms.uDensityScale.value, applied.densityScale);
assert.deepEqual(
  resource.material.uniforms.uTransferIntensities.value,
  applied.controlPoints.map(({ intensity }) => intensity),
);
assert.equal(resource.material.uniforms.uTransferColors.value.length, 6);

console.log("PHASE4D2_MEDICAL_TRANSFER_FUNCTIONS=PASS");
