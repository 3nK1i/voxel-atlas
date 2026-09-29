import assert from "node:assert/strict";
import {
  getSurfacePresentationProfile,
  applyVolumeSurfaceMaterialProfile,
  applySegmentationSurfaceMaterialProfile,
  createSurfaceLightingRig,
} from "../web/js/reconstruction-surface-presentation.js";

const fidelity = getSurfacePresentationProfile("fidelity");
const presentation = getSurfacePresentationProfile("presentation");

assert.equal(presentation.lighting.viewRelative, true);
assert.equal(presentation.lighting.hemisphere.ground, "#64748a");
assert.equal(presentation.lighting.fill.intensity, 0.88);
assert.equal(presentation.volumeSurface.emissive, "#4a4134");
assert.equal(presentation.volumeSurface.emissiveIntensity, 0.16);
assert.equal(presentation.segmentationSurface.emissiveIntensity, 0.08);
assert.equal(presentation.segmentationSurface.selectedEmissiveIntensity, 0.12);

assert.deepEqual(fidelity.lighting.hemisphere, {
  sky: "#d8efff",
  ground: "#182332",
  intensity: 1.18,
});
assert.deepEqual(fidelity.volumeSurface, {
  color: "#e8e1d2",
  roughness: 0.62,
  metalness: 0.0,
});
assert.deepEqual(fidelity.segmentationSurface, {
  roughness: 0.60,
  selectedRoughness: 0.52,
  metalness: 0.0,
});

const makeColor = () => ({ value: null, set(value) { this.value = value; } });
const volumeMaterial = {
  color: makeColor(),
  emissive: makeColor(),
  emissiveIntensity: 0,
  needsUpdate: false,
};
applyVolumeSurfaceMaterialProfile(volumeMaterial, "presentation");
assert.equal(volumeMaterial.color.value, presentation.volumeSurface.color);
assert.equal(volumeMaterial.emissive.value, presentation.volumeSurface.emissive);
assert.equal(volumeMaterial.emissiveIntensity, presentation.volumeSurface.emissiveIntensity);
applyVolumeSurfaceMaterialProfile(volumeMaterial, "fidelity");
assert.equal(volumeMaterial.color.value, fidelity.volumeSurface.color);
assert.equal(volumeMaterial.emissive.value, "#000000");
assert.equal(volumeMaterial.emissiveIntensity, 0);
assert.equal(volumeMaterial.roughness, fidelity.volumeSurface.roughness);

const structure = { colorHex: "#35c987", opacity: 0.64, labelId: 17 };
const segmentationMaterial = {
  color: makeColor(),
  emissive: makeColor(),
  emissiveIntensity: 0,
  needsUpdate: false,
};
applySegmentationSurfaceMaterialProfile(segmentationMaterial, structure, "presentation", false);
assert.equal(segmentationMaterial.color.value, structure.colorHex);
assert.equal(segmentationMaterial.emissive.value, structure.colorHex);
assert.equal(segmentationMaterial.emissiveIntensity, 0.08);
assert.equal(segmentationMaterial.opacity, structure.opacity);
applySegmentationSurfaceMaterialProfile(segmentationMaterial, structure, "presentation", true);
assert.equal(segmentationMaterial.emissiveIntensity, 0.12);
applySegmentationSurfaceMaterialProfile(segmentationMaterial, structure, "fidelity", false);
assert.equal(segmentationMaterial.color.value, structure.colorHex);
assert.equal(segmentationMaterial.emissive.value, structure.colorHex);
assert.equal(segmentationMaterial.emissiveIntensity, 0);
assert.equal(segmentationMaterial.roughness, fidelity.segmentationSurface.roughness);

class FakeColor {
  constructor(value) { this.value = value; }
  set(value) { this.value = value; }
}
class FakePosition {
  constructor(x = 0, y = 0, z = 0) { this.set(x, y, z); }
  set(x, y, z) { this.x = x; this.y = y; this.z = z; this.value = [x, y, z]; return this; }
}
class FakeTarget {
  constructor() { this.position = new FakePosition(); this.updated = 0; }
  updateMatrixWorld() { this.updated += 1; }
}
class FakeHemisphereLight {
  constructor(sky, ground, intensity) {
    this.color = new FakeColor(sky);
    this.groundColor = new FakeColor(ground);
    this.intensity = intensity;
    this.position = new FakePosition();
  }
}
class FakeDirectionalLight {
  constructor(color, intensity) {
    this.color = new FakeColor(color);
    this.intensity = intensity;
    this.position = new FakePosition();
    this.target = new FakeTarget();
  }
}
class FakeVector3 {
  constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
  applyQuaternion(quaternion) {
    if (quaternion?.quarterTurnY) {
      const x = this.x;
      this.x = this.z;
      this.z = -x;
    }
    return this;
  }
}

const scene = { items: [], add(...items) { this.items.push(...items); } };
let renderRequests = 0;
const rig = createSurfaceLightingRig({
  three: {
    HemisphereLight: FakeHemisphereLight,
    DirectionalLight: FakeDirectionalLight,
    Vector3: FakeVector3,
  },
  scene,
  requestRender() { renderRequests += 1; },
});
assert.equal(scene.items.length, 4);

rig.setProfile("presentation");
const focus = { x: 10, y: 20, z: 30 };
assert.equal(rig.syncToView({ quaternion: { quarterTurnY: false } }, focus), true);
assert.deepEqual(rig.key.position.value, [11.9, 22.4, 33.1]);
assert.deepEqual(rig.fill.position.value, [7.5, 21.0, 32.2]);
assert.deepEqual(rig.rim.position.value, [10.8, 22.0, 27.2]);
assert.deepEqual(rig.key.target.position.value, [10, 20, 30]);

assert.equal(rig.syncToView({ quaternion: { quarterTurnY: true } }, focus), true);
assert.deepEqual(rig.key.position.value, [13.1, 22.4, 28.1]);
assert.deepEqual(rig.fill.position.value, [12.2, 21.0, 32.5]);
assert.deepEqual(rig.rim.position.value, [7.2, 22.0, 29.2]);

rig.setProfile("fidelity");
assert.equal(rig.syncToView({ quaternion: { quarterTurnY: true } }, focus), false);
assert.deepEqual(rig.key.position.value, fidelity.lighting.key.position);
assert.deepEqual(rig.fill.position.value, fidelity.lighting.fill.position);
assert.deepEqual(rig.rim.position.value, fidelity.lighting.rim.position);
assert.ok(renderRequests >= 3);

console.log("PHASE6E_D_PRESENTATION_POLISH=PASS");
console.log("PRESENTATION_LIGHTING=VIEW_RELATIVE_KEY_FILL_RIM");
console.log("PRESENTATION_SHADOW_LIFT=DIRECT_CT_PLUS_SEMANTIC_SEGMENTATION");
console.log("FIDELITY_ROUND_TRIP=LOCKED_REFERENCE_RESTORED");
