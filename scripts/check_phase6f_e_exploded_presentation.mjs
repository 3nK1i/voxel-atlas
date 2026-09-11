#!/usr/bin/env node

import assert from "node:assert/strict";
import {
  createStructurePresentation,
} from "../web/js/segmentation-structure-panel.js";
import {
  MAX_ANATOMICAL_GROUP_EXPLODE_MM,
  applyAnatomicalGroupExplosion,
  patientLpsOffsetToViewer,
  resetAnatomicalGroupExplosion,
  resolveAnatomicalGroupExplosion,
} from "../web/js/segmentation-exploded-presentation.js";
import {
  resolveStructureInteraction,
} from "../web/js/segmentation-structure-interaction.js";
import {
  createThreeSurfaceClippingPlanes,
} from "../web/js/reconstruction-surface-clipping.js";

const descriptor = {
  label_map_id: "map-6fe00000000000000000000000000000",
  structure_catalog: {
    schema_version: 1,
    structure_count: 4,
    groups: [
      { group_id: "organs", display_name: "Organs", structure_count: 2 },
      { group_id: "cardiovascular", display_name: "Cardiovascular", structure_count: 1 },
      { group_id: "nervous_system", display_name: "Nervous system", structure_count: 1 },
    ],
    structures: [
      { label_id: 1, name: "spleen", display_name: "Spleen", group_id: "organs", group_name: "Organs", color_hex: "#ff0000", default_visible: true, default_opacity: 0.8 },
      { label_id: 5, name: "liver", display_name: "Liver", group_id: "organs", group_name: "Organs", color_hex: "#ffff00", default_visible: true, default_opacity: 1 },
      { label_id: 51, name: "heart", display_name: "Heart", group_id: "cardiovascular", group_name: "Cardiovascular", color_hex: "#00ff00", default_visible: true, default_opacity: 0.65 },
      { label_id: 90, name: "brain", display_name: "Brain", group_id: "nervous_system", group_name: "Nervous system", color_hex: "#0000ff", default_visible: false, default_opacity: 1 },
    ],
  },
};

const presentation = createStructurePresentation(descriptor);
presentation.structures.get(1).surfaceVisible = true;
presentation.structures.get(5).surfaceVisible = true;
presentation.structures.get(51).surfaceVisible = true;
presentation.structures.get(1).clippingEnabled = false;

const before = new Map(Array.from(presentation.structures.values(), (structure) => [
  structure.labelId,
  {
    visible: structure.visible,
    surfaceVisible: structure.surfaceVisible,
    opacity: structure.opacity,
    clippingEnabled: structure.clippingEnabled,
  },
]));

const planned = resolveAnatomicalGroupExplosion(presentation, MAX_ANATOMICAL_GROUP_EXPLODE_MM * 2);
assert.equal(planned.amountMm, MAX_ANATOMICAL_GROUP_EXPLODE_MM);
assert.equal(planned.groupCount, 3);

const applied = applyAnatomicalGroupExplosion(presentation, 24);
assert.equal(applied.amountMm, 24);
assert.equal(presentation.explodedSeparationMm, 24);

const spleenOffset = presentation.structures.get(1).explodedOffsetLpsMm;
const liverOffset = presentation.structures.get(5).explodedOffsetLpsMm;
const heartOffset = presentation.structures.get(51).explodedOffsetLpsMm;
assert.deepEqual(spleenOffset, liverOffset);
assert.notDeepEqual(spleenOffset, heartOffset);
for (const structure of presentation.structures.values()) {
  const length = Math.hypot(...structure.explodedOffsetLpsMm);
  assert.ok(Math.abs(length - 24) < 1e-9);
  const original = before.get(structure.labelId);
  assert.equal(structure.visible, original.visible);
  assert.equal(structure.surfaceVisible, original.surfaceVisible);
  assert.equal(structure.opacity, original.opacity);
  assert.equal(structure.clippingEnabled, original.clippingEnabled);
}

const resolvedSpleen = resolveStructureInteraction(presentation, 1);
assert.deepEqual(resolvedSpleen.explodedOffsetLpsMm, spleenOffset);
assert.equal(resolvedSpleen.opacity, 0.8);
assert.equal(resolvedSpleen.clippingEnabled, false);

const viewerOffset = patientLpsOffsetToViewer([10, 20, 30], { maximumExtentMm: 100 });
assert.deepEqual(viewerOffset, [-0.2, 0.6, -0.4]);

class Vector3 {
  constructor(x, y, z) { this.x = x; this.y = y; this.z = z; }
}
class Plane {
  constructor(normal, constant) { this.normal = normal; this.constant = constant; }
}
const THREE = { Vector3, Plane };
const clipping = {
  sagittal: { enabled: true, minimumLpsMm: -5, maximumLpsMm: 15 },
};
const basePlanes = createThreeSurfaceClippingPlanes(
  THREE,
  { viewerCenterLpsMm: [0, 0, 0], maximumExtentMm: 100 },
  clipping,
);
const movedPlanes = createThreeSurfaceClippingPlanes(
  THREE,
  { viewerCenterLpsMm: [0, 0, 0], maximumExtentMm: 100 },
  clipping,
  [0.25, 0, 0],
);
assert.equal(basePlanes.length, 2);
assert.equal(movedPlanes.length, 2);
assert.ok(Math.abs(movedPlanes[0].constant - (basePlanes[0].constant + 0.25)) < 1e-9);
assert.ok(Math.abs(movedPlanes[1].constant - (basePlanes[1].constant - 0.25)) < 1e-9);

resetAnatomicalGroupExplosion(presentation);
assert.equal(presentation.explodedSeparationMm, 0);
for (const structure of presentation.structures.values()) {
  assert.deepEqual(structure.explodedOffsetLpsMm, [0, 0, 0]);
  const original = before.get(structure.labelId);
  assert.equal(structure.visible, original.visible);
  assert.equal(structure.surfaceVisible, original.surfaceVisible);
  assert.equal(structure.opacity, original.opacity);
  assert.equal(structure.clippingEnabled, original.clippingEnabled);
}

console.log("PHASE6F_E_GROUP_EXPLOSION=ANATOMICAL_GROUP_SHARED_OFFSETS");
console.log(`PHASE6F_E_EXPLOSION_MAX_MM=${MAX_ANATOMICAL_GROUP_EXPLODE_MM}`);
console.log("PHASE6F_E_PATIENT_LPS_OFFSET_TO_VIEWER=PASS");
console.log("PHASE6F_E_CLIPPING_FOLLOWS_EXPLODED_DISPLAY_OFFSET=YES");
console.log("PHASE6F_E_VISIBILITY_OPACITY_CLIPPING_STATE=PRESERVED");
console.log("PHASE6F_E_BEHAVIOR_OK=YES");
