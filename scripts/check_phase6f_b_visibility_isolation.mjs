#!/usr/bin/env node

import assert from "node:assert/strict";
import {
  createStructurePresentation,
  isolateStructure,
  restoreIsolation,
} from "../web/js/segmentation-structure-panel.js";
import {
  resolveStructureInteraction,
} from "../web/js/segmentation-structure-interaction.js";
import {
  drawSegmentationLabels,
} from "../web/js/segmentation-overlay.js";
import {
  PatientSegmentationSurfaceLayer,
} from "../web/js/segmentation-surface-viewer.js";

const descriptor = {
  label_map_id: "map-6fb00000000000000000000000000000",
  structure_catalog: {
    schema_version: 1,
    structure_count: 3,
    groups: [{ group_id: "organs", display_name: "Organs", structure_count: 3 }],
    structures: [
      {
        label_id: 1,
        name: "hidden_structure",
        display_name: "Hidden structure",
        group_id: "organs",
        group_name: "Organs",
        color_hex: "#ff0000",
        default_visible: false,
        default_opacity: 1,
      },
      {
        label_id: 51,
        name: "target_structure",
        display_name: "Target structure",
        group_id: "organs",
        group_name: "Organs",
        color_hex: "#00ff00",
        default_visible: true,
        default_opacity: 0.8,
      },
      {
        label_id: 52,
        name: "other_structure",
        display_name: "Other structure",
        group_id: "organs",
        group_name: "Organs",
        color_hex: "#0000ff",
        default_visible: true,
        default_opacity: 0.6,
      },
    ],
  },
};

const presentation = createStructurePresentation(descriptor);
presentation.structures.get(51).surfaceVisible = true;
presentation.structures.get(52).surfaceVisible = true;

const baseVisibility = new Map(
  Array.from(presentation.structures.values(), (item) => [item.labelId, item.visible]),
);
const baseSurfaceRequests = new Map(
  Array.from(presentation.structures.values(), (item) => [item.labelId, item.surfaceVisible]),
);

isolateStructure(presentation, 51);
assert.equal(presentation.interaction.isolatedLabelId, 51);
assert.equal(presentation.selectedLabelId, 51);
assert.equal(resolveStructureInteraction(presentation, 51).effectiveVisible, true);
assert.equal(resolveStructureInteraction(presentation, 51).effectiveSurfaceVisible, true);
assert.equal(resolveStructureInteraction(presentation, 52).effectiveVisible, false);
assert.equal(resolveStructureInteraction(presentation, 52).effectiveSurfaceVisible, false);
for (const structure of presentation.structures.values()) {
  assert.equal(structure.visible, baseVisibility.get(structure.labelId));
  assert.equal(structure.surfaceVisible, baseSurfaceRequests.get(structure.labelId));
}

let rendered = null;
const canvas = {
  width: 0,
  height: 0,
  hidden: true,
  style: {},
  getContext() {
    return {
      createImageData(width, height) {
        return { data: new Uint8ClampedArray(width * height * 4) };
      },
      putImageData(image) { rendered = image.data; },
    };
  },
};
const labels = new Uint16Array([1, 51, 52]);
drawSegmentationLabels(canvas, labels, 3, 1, presentation, 1);
assert.equal(rendered[3], 0);
assert.equal(rendered[7], Math.round(255 * 0.8));
assert.equal(rendered[11], 0);

restoreIsolation(presentation);
assert.equal(presentation.interaction.isolatedLabelId, null);
assert.equal(resolveStructureInteraction(presentation, 1).effectiveVisible, false);
assert.equal(resolveStructureInteraction(presentation, 51).effectiveVisible, true);
assert.equal(resolveStructureInteraction(presentation, 52).effectiveVisible, true);
for (const structure of presentation.structures.values()) {
  assert.equal(structure.visible, baseVisibility.get(structure.labelId));
  assert.equal(structure.surfaceVisible, baseSurfaceRequests.get(structure.labelId));
}

// A hidden structure can be inspected transiently without changing its base visibility
// or silently requesting a 3D surface.
isolateStructure(presentation, 1);
const hiddenIsolated = resolveStructureInteraction(presentation, 1);
assert.equal(hiddenIsolated.userVisible, false);
assert.equal(hiddenIsolated.effectiveVisible, true);
assert.equal(hiddenIsolated.surfaceRequested, false);
assert.equal(hiddenIsolated.effectiveSurfaceVisible, false);
restoreIsolation(presentation);
assert.equal(resolveStructureInteraction(presentation, 1).effectiveVisible, false);

// Isolation is a presentation gate only: it must not alter the explicit 3D
// surface-request set, cancel requests, or create new geometry requests.
let nonIsolatedRequestAborted = false;
const fakeSurfaceLayer = Object.create(PatientSegmentationSurfaceLayer.prototype);
Object.assign(fakeSurfaceLayer, {
  descriptor: { ready: true },
  presentation: null,
  desiredLabels: new Set(),
  controllers: new Map([[52, { abort() { nonIsolatedRequestAborted = true; } }]]),
  failedLabels: new Map(),
  items: new Map(),
  queue: [],
  generation: 1,
  requestRender: () => {},
  _enqueue: () => {},
  _pumpQueue: () => {},
  _updateStatus: () => {},
});
await fakeSurfaceLayer.sync(presentation);
assert.deepEqual(Array.from(fakeSurfaceLayer.desiredLabels).sort((a, b) => a - b), [51, 52]);
isolateStructure(presentation, 51);
await fakeSurfaceLayer.sync(presentation);
assert.deepEqual(
  Array.from(fakeSurfaceLayer.desiredLabels).sort((a, b) => a - b),
  [51, 52],
  "Isolation must not alter the explicit surface-request set",
);
assert.equal(nonIsolatedRequestAborted, false, "Isolation must not abort an existing surface request");
restoreIsolation(presentation);

console.log("PHASE6F_B_ISOLATION=NON_DESTRUCTIVE");
console.log("PHASE6F_B_RESTORE=BASE_VISIBILITY_RECOVERED");
console.log("PHASE6F_B_SURFACE_REQUEST_STATE=PRESERVED");
console.log("PHASE6F_B_ISOLATION_SURFACE_FETCH_DELTA=NONE");
console.log("PHASE6F_B_MPR_OVERLAY=EFFECTIVE_VISIBILITY");
console.log("PHASE6F_B_BEHAVIOR_OK=YES");
