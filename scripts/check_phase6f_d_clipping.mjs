import assert from "node:assert/strict";
import {
  applySurfaceClippingToMaterial,
  enableSurfaceLocalClipping,
  resolvePatientSurfaceClippingDescriptors,
} from "../web/js/reconstruction-surface-clipping.js";
import {
  resolveStructureInteraction,
} from "../web/js/segmentation-structure-interaction.js";

const presentation = {
  viewerCenterLpsMm: [0, 0, 0],
  maximumExtentMm: 100,
};
const clipping = {
  sagittal: { enabled: true, minimumLpsMm: -5, maximumLpsMm: 15 },
  coronal: { enabled: false, minimumLpsMm: -20, maximumLpsMm: 20 },
  axial: { enabled: true, minimumLpsMm: -10, maximumLpsMm: 25 },
};

const descriptors = resolvePatientSurfaceClippingDescriptors(presentation, clipping);
assert.equal(descriptors.length, 4);
assert.deepEqual(descriptors[0].normal, [-1, 0, 0]);
assert.ok(Math.abs(descriptors[0].constant - 0.1) < 1e-9);
assert.deepEqual(descriptors[1].normal, [1, 0, 0]);
assert.ok(Math.abs(descriptors[1].constant - 0.3) < 1e-9);
assert.deepEqual(descriptors[2].normal, [0, 1, 0]);
assert.ok(Math.abs(descriptors[2].constant - 0.2) < 1e-9);
assert.deepEqual(descriptors[3].normal, [0, -1, 0]);
assert.ok(Math.abs(descriptors[3].constant - 0.5) < 1e-9);

class Vector3 {
  constructor(x, y, z) { this.x = x; this.y = y; this.z = z; }
}
class Plane {
  constructor(normal, constant) { this.normal = normal; this.constant = constant; }
}
const THREE = { Vector3, Plane };
const material = { clippingPlanes: null, clipIntersection: true, needsUpdate: false };
const applied = applySurfaceClippingToMaterial(material, THREE, presentation, clipping, true);
assert.equal(applied.length, 4);
assert.equal(material.clippingPlanes.length, 4);
assert.equal(material.clipIntersection, false);
assert.equal(material.needsUpdate, true);

const ignored = applySurfaceClippingToMaterial(material, THREE, presentation, clipping, false);
assert.equal(ignored.length, 0);
assert.equal(material.clippingPlanes.length, 0);

const renderer = { localClippingEnabled: false };
assert.equal(enableSurfaceLocalClipping(renderer), true);
assert.equal(renderer.localClippingEnabled, true);

const structure = {
  labelId: 91,
  groupId: "head_neck",
  visible: true,
  surfaceVisible: true,
  opacity: 0.42,
  clippingEnabled: false,
  explodedOffsetLpsMm: [0, 0, 0],
};
const structurePresentation = {
  interaction: { schemaVersion: 1, isolatedLabelId: null },
  structures: new Map([[91, structure]]),
};
const resolved = resolveStructureInteraction(structurePresentation, 91);
assert.equal(resolved.clippingEnabled, false);
assert.equal(resolved.opacity, 0.42);
assert.equal(resolved.effectiveSurfaceVisible, true);

console.log("PHASE6F_D_PATIENT_LPS_CLIPPING_DESCRIPTORS=PASS");
console.log("PHASE6F_D_MATERIAL_CLIPPING_DISPLAY_ONLY=YES");
console.log("PHASE6F_D_PER_STRUCTURE_CLIP_IGNORE=PASS");
console.log("PHASE6F_D_LOCAL_CLIPPING_ENABLED=YES");
