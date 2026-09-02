#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  PatientVolumeRayMarcher,
  buildVolumePresentation,
  selectBaselineTransferFunction,
} from "../web/js/patient-volume-ray-marcher.js";


const descriptor = {
  ready: true,
  revision: "a".repeat(64),
  source_modality: "CT",
  source_intensity_units: "HU",
  source_value_range: [-1024, 1500],
  texture_dimensions: [4, 3, 2],
  texture_coordinate_to_patient_lps: [
    [4, 0, 0, 10],
    [0, 6, 0, 20],
    [0, 0, 8, 30],
    [0, 0, 0, 1],
  ],
  decode_offset: -1024,
  decode_scale: 2524 / 65535,
};

const presentation = buildVolumePresentation(descriptor);
assert.deepEqual(presentation.extentMm, [4, 8, 6]);
assert.deepEqual(presentation.normalizedExtent, [1, 2, 1.5]);
assert.equal(presentation.maximumExtentMm, 8);
assert.equal(presentation.matrix.length, 16);
assert.ok(presentation.matrix[0] < 0, "LPS left must map toward viewer left");
assert.ok(presentation.matrix[6] > 0, "LPS superior must map toward viewer superior");
assert.ok(presentation.matrix[9] < 0, "LPS posterior must map away from viewer anterior");

const transfer = selectBaselineTransferFunction(descriptor);
assert.equal(transfer.modality, "CT");
assert.equal(transfer.units, "HU");
assert.ok(transfer.intensityLow >= descriptor.source_value_range[0]);
assert.ok(transfer.intensityHigh <= descriptor.source_value_range[1]);
assert.ok(transfer.intensityHigh > transfer.intensityLow);

class FakeGeometry {
  constructor() { this.disposeCount = 0; }
  dispose() { this.disposeCount += 1; }
}

class FakeMaterial {
  constructor(options) {
    Object.assign(this, options);
    this.disposeCount = 0;
  }
  dispose() { this.disposeCount += 1; }
}

class FakeMatrix4 {
  set(...elements) { this.elements = elements; return this; }
}

class FakeMesh {
  constructor(geometry, material) {
    this.geometry = geometry;
    this.material = material;
    this.matrix = new FakeMatrix4();
    this.matrixAutoUpdate = true;
    this.isMesh = true;
    this.visible = true;
  }
}

class FakeGroup {
  constructor() { this.children = []; this.userData = {}; this.visible = true; }
  add(child) { this.children.push(child); child.parent = this; }
  remove(child) { this.children = this.children.filter((item) => item !== child); }
  traverse(callback) {
    callback(this);
    for (const child of this.children) callback(child);
  }
  updateMatrixWorld() {}
}

const THREE = {
  BackSide: "BackSide",
  BoxGeometry: FakeGeometry,
  GLSL3: "GLSL3",
  Group: FakeGroup,
  NearestFilter: "NearestFilter",
  Matrix4: FakeMatrix4,
  Mesh: FakeMesh,
  ShaderMaterial: FakeMaterial,
};

const texture = { minFilter: "Nearest", magFilter: "Nearest", needsUpdate: false };
const manager = new PatientVolumeRayMarcher({ three: THREE });
const resource = manager.create({ texture, descriptor });
assert.equal(texture.minFilter, THREE.NearestFilter);
assert.equal(texture.magFilter, THREE.NearestFilter);
assert.equal(texture.needsUpdate, true);
assert.equal(resource.mesh.material.side, THREE.BackSide);
assert.equal(resource.mesh.material.glslVersion, THREE.GLSL3);
assert.equal(resource.mesh.material.uniforms.uVolume.value, texture);
assert.deepEqual(resource.mesh.matrix.elements, presentation.matrix);

manager.setOpacity(0.37);
assert.equal(resource.mesh.material.uniforms.uGlobalOpacity.value, 0.37);
manager.dispose();
assert.equal(resource.geometry.disposeCount, 1);
assert.equal(resource.material.disposeCount, 1);
assert.equal(manager.current, null);

console.log("PHASE4C2_VOLUME_RAY_MARCHER=PASS");
