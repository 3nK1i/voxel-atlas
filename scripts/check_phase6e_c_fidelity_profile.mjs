import assert from "node:assert/strict";
import {
  getSurfacePresentationProfile,
  applyVolumeSurfaceMaterialProfile,
  applySegmentationSurfaceMaterialProfile,
  createSurfaceLightingRig,
} from "../web/js/reconstruction-surface-presentation.js";

const fidelity = getSurfacePresentationProfile("fidelity");
const presentation = getSurfacePresentationProfile("presentation");

assert.deepEqual(fidelity.lighting.hemisphere, {
  sky: "#d8efff",
  ground: "#182332",
  intensity: 1.18,
});
assert.deepEqual(fidelity.lighting.key, {
  color: "#fff6ea",
  intensity: 1.35,
  position: [2.8, 3.6, 4.8],
});
assert.deepEqual(fidelity.lighting.fill, {
  color: "#c9ddff",
  intensity: 0.48,
  position: [-3.4, 1.4, 2.6],
});
assert.deepEqual(fidelity.lighting.rim, {
  color: "#e4efff",
  intensity: 0.62,
  position: [-1.2, 3.0, -4.2],
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

const volumeMaterial = { color: makeColor(), needsUpdate: false };
applyVolumeSurfaceMaterialProfile(volumeMaterial, "presentation");
applyVolumeSurfaceMaterialProfile(volumeMaterial, "fidelity");
assert.equal(volumeMaterial.color.value, fidelity.volumeSurface.color);
assert.equal(volumeMaterial.roughness, fidelity.volumeSurface.roughness);
assert.equal(volumeMaterial.metalness, fidelity.volumeSurface.metalness);
assert.equal(volumeMaterial.needsUpdate, true);

const structure = { colorHex: "#35c987", opacity: 0.64, labelId: 17 };
const segmentationMaterial = { color: makeColor(), needsUpdate: false };
applySegmentationSurfaceMaterialProfile(segmentationMaterial, structure, "presentation", true);
applySegmentationSurfaceMaterialProfile(segmentationMaterial, structure, "fidelity", false);
assert.equal(segmentationMaterial.color.value, structure.colorHex);
assert.equal(segmentationMaterial.opacity, structure.opacity);
assert.equal(segmentationMaterial.transparent, true);
assert.equal(segmentationMaterial.depthWrite, false);
assert.equal(segmentationMaterial.roughness, fidelity.segmentationSurface.roughness);
assert.equal(segmentationMaterial.metalness, fidelity.segmentationSurface.metalness);

class FakeColor {
  constructor(value) { this.value = value; }
  set(value) { this.value = value; }
}
class FakePosition {
  constructor() { this.value = [0, 0, 0]; }
  set(...value) { this.value = value; }
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
  }
}
const scene = { items: [], add(...items) { this.items.push(...items); } };
let renderRequests = 0;
const rig = createSurfaceLightingRig({
  three: { HemisphereLight: FakeHemisphereLight, DirectionalLight: FakeDirectionalLight },
  scene,
  requestRender() { renderRequests += 1; },
});
assert.equal(scene.items.length, 4);
rig.setProfile("presentation");
rig.setProfile("fidelity");
assert.equal(rig.profile, "fidelity");
assert.equal(rig.hemisphere.color.value, fidelity.lighting.hemisphere.sky);
assert.equal(rig.hemisphere.groundColor.value, fidelity.lighting.hemisphere.ground);
assert.equal(rig.hemisphere.intensity, fidelity.lighting.hemisphere.intensity);
assert.equal(rig.key.color.value, fidelity.lighting.key.color);
assert.deepEqual(rig.key.position.value, fidelity.lighting.key.position);
assert.equal(rig.fill.color.value, fidelity.lighting.fill.color);
assert.deepEqual(rig.fill.position.value, fidelity.lighting.fill.position);
assert.equal(rig.rim.color.value, fidelity.lighting.rim.color);
assert.deepEqual(rig.rim.position.value, fidelity.lighting.rim.position);
assert.ok(renderRequests >= 3);

console.log("PHASE6E_C_FIDELITY_REFERENCE_ROUND_TRIP=PASS");
