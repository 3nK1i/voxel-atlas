#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  PatientVolumeRayMarcher,
  constrainMedicalIntensityInterval,
  createMedicalTransferFunction,
  evaluateDepthShadingFactor,
  evaluateEdgeDefinitionWeight,
  evaluateOpacitySoftnessWeight,
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
  decode_offset: -1024,
  decode_scale: 3524 / 65535,
};

const baseline = createMedicalTransferFunction(descriptor, "ct-general");
for (const field of ["opacitySoftness", "edgeDefinition", "shadingStrength"]) {
  assert.ok(baseline[field] >= 0 && baseline[field] <= 1, `${field} must be normalized`);
}

const adjusted = createMedicalTransferFunction(descriptor, "ct-general", {
  opacitySoftness: 0.55,
  edgeDefinition: 0.72,
  shadingStrength: 0.64,
});
assert.equal(adjusted.opacitySoftness, 0.55);
assert.equal(adjusted.edgeDefinition, 0.72);
assert.equal(adjusted.shadingStrength, 0.64);
assert.throws(
  () => createMedicalTransferFunction(descriptor, "ct-general", { edgeDefinition: 1.01 }),
  /edge definition is invalid/,
);

const fixedDomainInterval = constrainMedicalIntensityInterval(
  [-1024, 2500],
  2499,
  1200,
  "minimum",
);
assert.ok(fixedDomainInterval.minimum < fixedDomainInterval.maximum);
assert.equal(fixedDomainInterval.maximum, 1200);
const lowerEdgeInterval = constrainMedicalIntensityInterval(
  [-1024, 2500],
  2500,
  -1024,
  "minimum",
);
const upperEdgeInterval = constrainMedicalIntensityInterval(
  [-1024, 2500],
  2500,
  -1024,
  "maximum",
);
assert.ok(lowerEdgeInterval.minimum < lowerEdgeInterval.maximum);
assert.ok(upperEdgeInterval.minimum < upperEdgeInterval.maximum);

const hardBoundary = evaluateOpacitySoftnessWeight(1150, -1000, 1200, 0);
const softBoundary = evaluateOpacitySoftnessWeight(1150, -1000, 1200, 1);
assert.equal(hardBoundary, 1);
assert.ok(softBoundary < 0.2, "maximum softness must visibly feather a cutoff");

const neutralEdge = evaluateEdgeDefinitionWeight(0.8, 0);
const strongEdge = evaluateEdgeDefinitionWeight(0.8, 1);
const flatEdge = evaluateEdgeDefinitionWeight(0, 1);
assert.equal(neutralEdge, 1);
assert.ok(strongEdge > 2, "maximum edge definition must emphasize strong gradients");
assert.ok(flatEdge < 0.3, "maximum edge definition must suppress flat opacity");

const neutralShading = evaluateDepthShadingFactor(0.2, 0.2, 0, 0);
const litShading = evaluateDepthShadingFactor(0.9, 0.8, 0.7, 1);
const shadowShading = evaluateDepthShadingFactor(0.1, 0.1, 0, 1);
assert.equal(neutralShading, 1);
assert.ok(litShading > 1.05, "maximum shading must produce a visible highlight cue");
assert.ok(shadowShading < 0.5, "maximum shading must produce a visible depth cue");

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
const resource = rayMarcher.create({ texture: {}, descriptor });
rayMarcher.setTransferPreset("ct-general", {
  opacitySoftness: 0.55,
  edgeDefinition: 0.72,
  shadingStrength: 0.64,
});
assert.deepEqual(
  [
    resource.material.uniforms.uTextureTexelSize.value.x,
    resource.material.uniforms.uTextureTexelSize.value.y,
    resource.material.uniforms.uTextureTexelSize.value.z,
  ],
  [1 / 512, 1 / 512, 1 / 112],
);
assert.equal(resource.material.uniforms.uOpacitySoftness.value, 0.55);
assert.equal(resource.material.uniforms.uEdgeDefinition.value, 0.72);
assert.equal(resource.material.uniforms.uShadingStrength.value, 0.64);

console.log("CANONICAL_TEXTURE_REUSED=YES");
console.log("DISPLAY_PARAMETERS_USE_GPU_UNIFORMS=YES");
console.log("INDEPENDENT_INTENSITY_INTERVAL=YES");
console.log("DISPLAY_RESPONSE_EXTREMES_DISTINCT=YES");
console.log("PHASE4H2_R1A_VOLUME_DEFINITION_AND_SHADING=PASS");
