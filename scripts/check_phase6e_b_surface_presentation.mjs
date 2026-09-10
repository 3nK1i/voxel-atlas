import assert from "node:assert/strict";
import {
  getSurfacePresentationProfile,
  applyVolumeSurfaceMaterialProfile,
  applySegmentationSurfaceMaterialProfile,
} from "../web/js/reconstruction-surface-presentation.js";

const fidelity = getSurfacePresentationProfile("fidelity");
const presentation = getSurfacePresentationProfile("presentation");
assert.equal(fidelity.id, "fidelity");
assert.equal(presentation.id, "presentation");
assert.notDeepEqual(fidelity.lighting, presentation.lighting);
assert.notEqual(fidelity.volumeSurface.roughness, presentation.volumeSurface.roughness);
assert.notEqual(fidelity.segmentationSurface.roughness, presentation.segmentationSurface.roughness);

const volumeMaterial = { color: { set(v){ this.value=v; } }, needsUpdate:false };
applyVolumeSurfaceMaterialProfile(volumeMaterial, "presentation");
assert.equal(volumeMaterial.color.value, presentation.volumeSurface.color);
assert.equal(volumeMaterial.roughness, presentation.volumeSurface.roughness);
assert.equal(volumeMaterial.metalness, 0);
assert.equal(volumeMaterial.needsUpdate, true);

const segmentationMaterial = {
  color: { set(v){ this.value=v; } },
  needsUpdate:false,
};
const structure = { colorHex: "#12ab34", opacity: 0.72, labelId: 4 };
applySegmentationSurfaceMaterialProfile(segmentationMaterial, structure, "presentation", true);
assert.equal(segmentationMaterial.color.value, "#12ab34");
assert.equal(segmentationMaterial.opacity, 0.72);
assert.equal(segmentationMaterial.transparent, true);
assert.equal(segmentationMaterial.depthWrite, false);
assert.equal(segmentationMaterial.metalness, 0);
assert.equal(segmentationMaterial.roughness, presentation.segmentationSurface.selectedRoughness);
assert.equal(segmentationMaterial.needsUpdate, true);

console.log("PHASE6E_B_SHARED_SURFACE_PRESENTATION_BEHAVIOR=PASS");
