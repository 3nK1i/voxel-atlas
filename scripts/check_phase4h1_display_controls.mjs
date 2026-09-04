#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  PatientVolumeRayMarcher,
  createMedicalTransferFunction,
} from "../web/js/patient-volume-ray-marcher.js";
import {
  AdaptiveVolumeRenderingQuality,
  RENDERING_QUALITY_POLICIES,
  createAdaptiveRenderingProfile,
} from "../web/js/volume-rendering-quality.js";


const ctDescriptor = {
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
const mrDescriptor = {
  ...ctDescriptor,
  source_modality: "MR",
  source_intensity_units: "modality",
  source_value_range: [0, 4095],
  decode_offset: 0,
  decode_scale: 4095 / 65535,
};

const generalCt = createMedicalTransferFunction(ctDescriptor, "ct-general");
assert.equal(generalCt.units, "HU");
assert.equal(generalCt.windowCenter, 40);
assert.equal(generalCt.windowWidth, 400);
assert.equal(generalCt.rangeLow, -1000);
assert.equal(generalCt.rangeHigh, 1200);

const adjustedCt = createMedicalTransferFunction(ctDescriptor, "ct-general", {
  windowCenter: 72,
  windowWidth: 520,
  rangeLow: -850,
  rangeHigh: 1450,
  densityMultiplier: 1.2,
});
assert.equal(adjustedCt.windowCenter, 72);
assert.equal(adjustedCt.windowWidth, 520);
assert.equal(adjustedCt.rangeLow, -850);
assert.equal(adjustedCt.rangeHigh, 1450);
assert.equal(adjustedCt.densityMultiplier, 1.2);

const balancedMr = createMedicalTransferFunction(mrDescriptor, "mr-balanced");
assert.equal(balancedMr.units, "modality");
assert.ok(balancedMr.windowWidth > 0);
assert.ok(balancedMr.windowCenter >= mrDescriptor.source_value_range[0]);
assert.ok(balancedMr.windowCenter <= mrDescriptor.source_value_range[1]);
assert.throws(
  () => createMedicalTransferFunction(ctDescriptor, "ct-general", { windowWidth: 0 }),
  /window width is invalid/,
);

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
const rayMarcher = new PatientVolumeRayMarcher({ three: THREE });
const resource = rayMarcher.create({ texture: {}, descriptor: ctDescriptor });
const applied = rayMarcher.setTransferPreset("ct-general", {
  windowCenter: 65,
  windowWidth: 475,
});
assert.equal(resource.material.uniforms.uWindowCenter.value, 65);
assert.equal(resource.material.uniforms.uWindowWidth.value, 475);
assert.deepEqual(
  [
    resource.material.uniforms.uIntensityBounds.value.x,
    resource.material.uniforms.uIntensityBounds.value.y,
  ],
  [applied.rangeLow, applied.rangeHigh],
);

assert.deepEqual(
  RENDERING_QUALITY_POLICIES.map(({ id }) => id),
  ["interactive", "balanced", "high", "maximum"],
);
const profiles = Object.fromEntries(RENDERING_QUALITY_POLICIES.map(({ id }) => [
  id,
  createAdaptiveRenderingProfile(
    ctDescriptor,
    { ready: true, max3dTextureSize: 2048 },
    2,
    id,
  ),
]));
assert.equal(profiles.balanced.policy, "balanced");
assert.ok(profiles.interactive.settledSamplingRate < profiles.balanced.settledSamplingRate);
assert.ok(profiles.high.settledSamplingRate > profiles.balanced.settledSamplingRate);
assert.ok(profiles.maximum.settledSamplingRate >= profiles.high.settledSamplingRate);
assert.ok(profiles.maximum.settledSamplingRate <= 512);
assert.ok(profiles.maximum.interactiveSamplingRate < profiles.maximum.settledSamplingRate);

const samplingRates = [];
const renderer = { setPixelRatio() {} };
const controller = new AdaptiveVolumeRenderingQuality({
  renderer,
  rayMarcher: {
    setSamplingRate(value) { samplingRates.push(value); return value; },
  },
  devicePixelRatio: 2,
});
controller.activate(ctDescriptor, { ready: true, max3dTextureSize: 2048 });
assert.equal(controller.snapshot().policy, "balanced");
controller.setPolicy("maximum");
assert.equal(controller.snapshot().policy, "maximum");
const maximumSettled = controller.snapshot().samplingRate;
controller.beginInteraction("orbit");
assert.equal(controller.snapshot().mode, "interactive");
assert.ok(controller.snapshot().samplingRate < maximumSettled);
assert.ok(samplingRates.length >= 3);

console.log("CT_WINDOW=40/400_HU");
console.log(`MR_WINDOW=${balancedMr.windowCenter}/${balancedMr.windowWidth}_REL`);
console.log(`QUALITY_POLICIES=${RENDERING_QUALITY_POLICIES.length}`);
console.log("PHASE4H1_PROFESSIONAL_MEDICAL_DISPLAY_CONTROLS=PASS");
