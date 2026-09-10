#!/usr/bin/env node
import assert from "node:assert/strict";
import {
  activateSurfaceForStructure,
  createStructurePresentation,
  resetStructurePresentation,
} from "../web/js/segmentation-structure-panel.js";

const descriptor = {
  label_map_id: "map-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  structure_catalog: {
    schema_version: 1,
    structure_count: 3,
    groups: [{ group_id: "organs", display_name: "Organs" }],
    structures: [1, 2, 3].map((labelId) => ({
      label_id: labelId,
      name: `label_${labelId}`,
      display_name: `Structure ${labelId}`,
      group_id: "organs",
      group_name: "Organs",
      color_hex: ["#c66b5e", "#e2a55f", "#77a8c7"][labelId - 1],
      default_visible: true,
      default_opacity: 1,
    })),
  },
};

const presentation = createStructurePresentation(descriptor);
assert.equal(presentation.selectedLabelId, null);
assert.equal(
  Array.from(presentation.structures.values()).every((structure) => structure.surfaceVisible === false),
  true,
);
assert.equal(
  Array.from(presentation.structures.values()).every((structure) => structure.visible === true),
  true,
  "The correction must not silently change Phase 5 MPR-overlay visibility semantics",
);

activateSurfaceForStructure(presentation, 2);
assert.equal(presentation.selectedLabelId, 2);
assert.equal(presentation.structures.get(2).surfaceVisible, true);
assert.equal(presentation.structures.get(1).surfaceVisible, false);
assert.equal(presentation.structures.get(3).surfaceVisible, false);

activateSurfaceForStructure(presentation, 3);
assert.equal(presentation.structures.get(2).surfaceVisible, true);
assert.equal(presentation.structures.get(3).surfaceVisible, true);

resetStructurePresentation(presentation);
assert.equal(presentation.selectedLabelId, null);
assert.equal(
  Array.from(presentation.structures.values()).every((structure) => structure.surfaceVisible === false),
  true,
);
assert.equal(
  Array.from(presentation.structures.values()).every((structure) => structure.visible === true),
  true,
);

console.log("PHASE6D0_NO_AUTOMATIC_3D_STRUCTURE=PASS");
console.log("PHASE6D0_EXPLICIT_3D_STRUCTURE_SELECTION=PASS");
console.log("PHASE6D0_MULTI_STRUCTURE_ACCUMULATION_PRESERVED=PASS");
console.log("PHASE6D0_RESET_RETURNS_TO_EMPTY_3D_SELECTION=PASS");
console.log("PHASE5_MPR_OVERLAY_VISIBILITY_SEMANTICS=PRESERVED");
console.log("PHASE6D0_EXPLICIT_SURFACE_SELECTION_CORRECTION_OK=YES");
