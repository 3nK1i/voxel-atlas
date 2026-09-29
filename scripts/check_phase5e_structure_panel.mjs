#!/usr/bin/env node

import assert from "node:assert/strict";
import {
  createStructurePresentation,
  isolateStructure,
  resetStructurePresentation,
  restoreIsolation,
} from "../web/js/segmentation-structure-panel.js";
import {
  resolveStructureInteraction,
} from "../web/js/segmentation-structure-interaction.js";
import {
  decodeSegmentationLabels,
  drawSegmentationLabels,
} from "../web/js/segmentation-overlay.js";


const descriptor = {
  label_map_id: "map-44444444444444444444444444444444",
  palette: [
    { label_id: 1, color_hex: "#ff0000" },
    { label_id: 51, color_hex: "#00ff00" },
  ],
  structure_catalog: {
    schema_version: 1,
    structure_count: 2,
    groups: [
      { group_id: "organs", display_name: "Organs", structure_count: 1 },
      { group_id: "cardiovascular", display_name: "Cardiovascular", structure_count: 1 },
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
        default_opacity: 1,
      },
    ],
  },
};

const presentation = createStructurePresentation(descriptor);
assert.equal(presentation.structures.size, 2);
assert.equal(presentation.structures.get(51).displayName, "Heart");

const visibilityBeforeIsolation = new Map(
  Array.from(presentation.structures.values(), (item) => [item.labelId, item.visible]),
);
isolateStructure(presentation, 51);
assert.equal(presentation.structures.get(1).visible, visibilityBeforeIsolation.get(1));
assert.equal(presentation.structures.get(51).visible, visibilityBeforeIsolation.get(51));
assert.equal(resolveStructureInteraction(presentation, 1).effectiveVisible, false);
assert.equal(resolveStructureInteraction(presentation, 51).effectiveVisible, true);
restoreIsolation(presentation);
assert.equal(resolveStructureInteraction(presentation, 1).effectiveVisible, true);

resetStructurePresentation(presentation);
presentation.structures.get(1).colorHex = "#112233";
presentation.structures.get(51).opacity = 0.5;

const rgba = new Uint8Array([
  0, 0, 0, 0,
  255, 0, 0, 255,
  0, 255, 0, 255,
]);
const labels = decodeSegmentationLabels(rgba, 3, 1, descriptor.palette);
assert.deepEqual(Array.from(labels), [0, 1, 51]);

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
      putImageData(image) {
        rendered = image.data;
      },
    };
  },
};
drawSegmentationLabels(canvas, labels, 3, 1, presentation, 0.45);
assert.equal(canvas.hidden, false);
assert.equal(canvas.style.opacity, "0.45");
assert.deepEqual(Array.from(rendered.slice(4, 8)), [17, 34, 51, 255]);
assert.deepEqual(Array.from(rendered.slice(8, 12)), [0, 255, 0, 128]);

console.log("PHASE5E_STRUCTURE_PRESENTATION_MODEL=PASS");
console.log("PHASE5E_STRUCTURE_VISIBILITY_ISOLATION=PASS_NON_DESTRUCTIVE_SUPERSESSION");
console.log("PHASE5E_LOCAL_COLOR_OPACITY_COMPOSITING=PASS");
console.log("PHASE5E_BROWSER_CONTRACT_OK=YES");
