import assert from "node:assert/strict";
import {
  getCombinedPresentationPolicy,
  resolveCombinedPresentationBalance,
} from "../web/js/reconstruction-combined-presentation.js";

const fidelity = getCombinedPresentationPolicy("fidelity");
const presentation = getCombinedPresentationPolicy("presentation");
assert.deepEqual(fidelity, {
  volumeOpacityMultiplier: 0.78,
  directCtSurfaceOpacity: 0.84,
  segmentationOpacityMultiplier: 1,
});
assert.deepEqual(presentation, {
  volumeOpacityMultiplier: 0.62,
  directCtSurfaceOpacity: 0.72,
  segmentationOpacityMultiplier: 1,
});

const fidelityCombined = resolveCombinedPresentationBalance({
  mode: "combined",
  profile: "fidelity",
  userVolumeOpacity: 0.8,
  directCtSurfaceVisible: true,
  segmentationSurfaceVisible: true,
});
assert.equal(fidelityCombined.active, true);
assert.ok(Math.abs(fidelityCombined.effectiveVolumeOpacity - 0.624) < 1e-12);
assert.equal(fidelityCombined.directCtSurfaceOpacity, 0.84);
assert.equal(fidelityCombined.segmentationOpacityMultiplier, 1);

const presentationCombined = resolveCombinedPresentationBalance({
  mode: "combined",
  profile: "presentation",
  userVolumeOpacity: 0.8,
  directCtSurfaceVisible: true,
  segmentationSurfaceVisible: true,
});
assert.equal(presentationCombined.active, true);
assert.ok(Math.abs(presentationCombined.effectiveVolumeOpacity - 0.496) < 1e-12);
assert.equal(presentationCombined.directCtSurfaceOpacity, 0.72);
assert.equal(presentationCombined.segmentationOpacityMultiplier, 1);

const surfaceMode = resolveCombinedPresentationBalance({
  mode: "surface",
  profile: "presentation",
  userVolumeOpacity: 0.8,
  directCtSurfaceVisible: true,
  segmentationSurfaceVisible: true,
});
assert.equal(surfaceMode.active, false);
assert.equal(surfaceMode.effectiveVolumeOpacity, 0.8);
assert.equal(surfaceMode.directCtSurfaceOpacity, 1);

const volumeMode = resolveCombinedPresentationBalance({
  mode: "volume",
  profile: "fidelity",
  userVolumeOpacity: 0.35,
});
assert.equal(volumeMode.active, false);
assert.equal(volumeMode.effectiveVolumeOpacity, 0.35);
assert.equal(volumeMode.directCtSurfaceOpacity, 1);

console.log("PHASE6E_E_COMBINED_PRESENTATION=PASS");
console.log("COMBINED_VOLUME_BALANCE=DERIVED_FROM_USER_OPACITY");
console.log("COMBINED_DIRECT_CT_BALANCE=PRESENTATION_ONLY_ALPHA");
console.log("SEGMENTATION_OPACITY_MULTIPLIER=1");
console.log("LEAVING_COMBINED=USER_STATE_RESTORED");
