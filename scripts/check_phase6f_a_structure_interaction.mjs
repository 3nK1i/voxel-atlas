#!/usr/bin/env node

import assert from "node:assert/strict";
import {
  createStructurePresentation,
  resetStructurePresentation,
} from "../web/js/segmentation-structure-panel.js";
import {
  STRUCTURE_INTERACTION_SCHEMA_VERSION,
  resolveStructureInteraction,
} from "../web/js/segmentation-structure-interaction.js";

const descriptor = {
  label_map_id: "map-6fa00000000000000000000000000000",
  structure_catalog: {
    schema_version: 1,
    structure_count: 3,
    groups: [
      { group_id: "organs", display_name: "Organs", structure_count: 1 },
      { group_id: "cardiovascular", display_name: "Cardiovascular", structure_count: 2 },
    ],
    structures: [
      {
        label_id: 1,
        name: "spleen",
        display_name: "Spleen",
        group_id: "organs",
        group_name: "Organs",
        color_hex: "#ff0000",
        default_visible: true,
        default_opacity: 1,
      },
      {
        label_id: 51,
        name: "heart",
        display_name: "Heart",
        group_id: "cardiovascular",
        group_name: "Cardiovascular",
        color_hex: "#00ff00",
        default_visible: true,
        default_opacity: 0.8,
      },
      {
        label_id: 52,
        name: "aorta",
        display_name: "Aorta",
        group_id: "cardiovascular",
        group_name: "Cardiovascular",
        color_hex: "#0000ff",
        default_visible: false,
        default_opacity: 0.6,
      },
    ],
  },
};

const presentation = createStructurePresentation(descriptor);
assert.equal(presentation.interaction.schemaVersion, STRUCTURE_INTERACTION_SCHEMA_VERSION);
assert.equal(presentation.interaction.isolatedLabelId, null);

for (const structure of presentation.structures.values()) {
  assert.equal(structure.clippingEnabled, true);
  assert.deepEqual(structure.explodedOffsetLpsMm, [0, 0, 0]);
}

const heart = presentation.structures.get(51);
heart.surfaceVisible = true;
heart.opacity = 0.37;
heart.clippingEnabled = false;
heart.explodedOffsetLpsMm = [12.5, -4, 3];

let resolved = resolveStructureInteraction(presentation, 51);
assert.equal(resolved.userVisible, true);
assert.equal(resolved.surfaceRequested, true);
assert.equal(resolved.effectiveVisible, true);
assert.equal(resolved.effectiveSurfaceVisible, true);
assert.equal(resolved.opacity, 0.37);
assert.equal(resolved.clippingEnabled, false);
assert.deepEqual(resolved.explodedOffsetLpsMm, [12.5, -4, 3]);

const baseVisibility = new Map(
  Array.from(presentation.structures.values(), (structure) => [structure.labelId, structure.visible]),
);
const baseSurfaceRequests = new Map(
  Array.from(presentation.structures.values(), (structure) => [structure.labelId, structure.surfaceVisible]),
);
presentation.interaction.isolatedLabelId = 51;

resolved = resolveStructureInteraction(presentation, 51);
assert.equal(resolved.isolated, true);
assert.equal(resolved.effectiveVisible, true);
assert.equal(resolved.effectiveSurfaceVisible, true);

const spleenResolved = resolveStructureInteraction(presentation, 1);
assert.equal(spleenResolved.isolated, false);
assert.equal(spleenResolved.userVisible, true);
assert.equal(spleenResolved.effectiveVisible, false);
assert.equal(spleenResolved.effectiveSurfaceVisible, false);

const hiddenAorta = resolveStructureInteraction(presentation, 52);
assert.equal(hiddenAorta.userVisible, false);
assert.equal(hiddenAorta.effectiveVisible, false);

for (const structure of presentation.structures.values()) {
  assert.equal(structure.visible, baseVisibility.get(structure.labelId));
  assert.equal(structure.surfaceVisible, baseSurfaceRequests.get(structure.labelId));
}

resetStructurePresentation(presentation);
assert.equal(presentation.interaction.isolatedLabelId, null);
for (const structure of presentation.structures.values()) {
  assert.equal(structure.clippingEnabled, true);
  assert.deepEqual(structure.explodedOffsetLpsMm, [0, 0, 0]);
}

console.log("PHASE6F_A_INTERACTION_SCHEMA=PASS");
console.log("PHASE6F_A_ISOLATION_PRECEDENCE=NON_DESTRUCTIVE");
console.log("PHASE6F_A_USER_OPACITY=AUTHORITATIVE");
console.log("PHASE6F_A_SURFACE_REQUEST_STATE=PRESERVED");
console.log("PHASE6F_A_CLIPPING_STATE=DECLARED_NOT_APPLIED");
console.log("PHASE6F_A_EXPLODED_OFFSET=DISPLAY_STATE_ONLY");
console.log("PHASE6F_A_BEHAVIOR_OK=YES");
