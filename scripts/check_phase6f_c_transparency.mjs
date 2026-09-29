import assert from "node:assert/strict";
import {
  applySegmentationSurfaceMaterialProfile,
  createSegmentationSurfaceMaterial,
  resolveDirectCtSurfaceCompositionPolicy,
  resolveSegmentationSurfaceOpacityPolicy,
} from "../web/js/reconstruction-surface-presentation.js";
import {
  activateStructureIsolation,
  restoreStructureIsolation,
} from "../web/js/segmentation-structure-interaction.js";

class FakeMeshStandardMaterial {
  constructor(options = {}) {
    Object.assign(this, options);
    this.color = { value: options.color, set(v){ this.value = v; } };
    this.emissive = { value: options.emissive, set(v){ this.value = v; } };
    this.needsUpdate = false;
  }
}
const THREE = { MeshStandardMaterial: FakeMeshStandardMaterial, FrontSide: 0, DoubleSide: 2 };


const directCtSurfaceOnly = resolveDirectCtSurfaceCompositionPolicy(1, false);
assert.equal(directCtSurfaceOnly.opacity, 1);
assert.equal(directCtSurfaceOnly.transparent, false);
assert.equal(directCtSurfaceOnly.depthWrite, true);

const directCtSemanticOverlay = resolveDirectCtSurfaceCompositionPolicy(1, true);
assert.equal(directCtSemanticOverlay.opacity, 1);
assert.equal(directCtSemanticOverlay.transparent, true);
assert.equal(directCtSemanticOverlay.depthWrite, false);

const directCtTranslucent = resolveDirectCtSurfaceCompositionPolicy(0.72, false);
assert.equal(directCtTranslucent.transparent, true);
assert.equal(directCtTranslucent.depthWrite, false);

for (const opacity of [0, 0.42, 0.85, 0.97, 0.98, 0.99]) {
  const policy = resolveSegmentationSurfaceOpacityPolicy(opacity);
  assert.equal(policy.opacity, opacity);
  assert.equal(policy.transparent, true);
  assert.equal(policy.depthWrite, false);
}
const opaque = resolveSegmentationSurfaceOpacityPolicy(1);
assert.equal(opaque.opacity, 1);
assert.equal(opaque.transparent, true);
assert.equal(opaque.depthWrite, true);
assert.throws(() => resolveSegmentationSurfaceOpacityPolicy(1.01), RangeError);

const structure = { labelId: 90, colorHex: "#315fd6", opacity: 0.85 };
const material = createSegmentationSurfaceMaterial(THREE, structure, "fidelity", true);
assert.equal(material.opacity, 0.85);
assert.equal(material.transparent, true);
assert.equal(material.depthWrite, false);

for (const profile of ["presentation", "fidelity", "presentation"]) {
  applySegmentationSurfaceMaterialProfile(material, structure, profile, true);
  assert.equal(material.opacity, 0.85);
  assert.equal(material.transparent, true);
  assert.equal(material.depthWrite, false);
}
structure.opacity = 1;
applySegmentationSurfaceMaterialProfile(material, structure, "presentation", true);
assert.equal(material.opacity, 1);
assert.equal(material.transparent, true);
assert.equal(material.depthWrite, true);

const presentation = {
  interaction: { isolatedLabelId: null },
  structures: new Map([[90, structure], [91, { labelId: 91, opacity: 0.37 }]]),
};
const originalOpacity = structure.opacity;
activateStructureIsolation(presentation, 90);
assert.equal(structure.opacity, originalOpacity);
restoreStructureIsolation(presentation);
assert.equal(structure.opacity, originalOpacity);

console.log("PHASE6F_C_OPACITY_EXACT=YES");
console.log("PHASE6F_C_NEAR_OPAQUE_DEPTH_WRITE=NO");
console.log("PHASE6F_C_ALPHA_100_TRANSPARENT_RENDER_LANE=YES");
console.log("PHASE6F_C_SURFACE_MODE_DIRECT_CT_SEMANTIC_COEXISTENCE=YES");
console.log("PHASE6F_C_FULL_ALPHA_DEPTH_WRITE=YES");
console.log("PHASE6F_C_PROFILE_ROUND_TRIP_PRESERVES_OPACITY=YES");
console.log("PHASE6F_C_ISOLATION_PRESERVES_OPACITY=YES");
