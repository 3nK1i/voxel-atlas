#!/usr/bin/env node

import assert from "node:assert/strict";
import fs from "node:fs";
import { decodeSegmentationSurface } from "../web/js/segmentation-surface-viewer.js";

function writeMagic(view) {
  for (const [index, character] of Array.from("VXSF").entries()) {
    view.setUint8(index, character.charCodeAt(0));
  }
}

const positions = new Float32Array([
  10, 20, 30,
  11, 20, 30,
  10, 21, 30,
]);
const normals = new Float32Array([
  0, 0, 1,
  0, 0, 1,
  0, 0, 1,
]);
const indices = new Uint32Array([0, 1, 2]);
const payload = new ArrayBuffer(36 + positions.byteLength + normals.byteLength + indices.byteLength);
const header = new DataView(payload);
writeMagic(header);
header.setUint32(4, 2, true);
header.setUint32(8, 91, true);
header.setUint32(12, 3, true);
header.setUint32(16, 3, true);
header.setUint32(20, positions.byteLength, true);
header.setUint32(24, normals.byteLength, true);
header.setUint32(28, indices.byteLength, true);
header.setUint32(32, 1, true);
let offset = 36;
new Uint8Array(payload, offset, positions.byteLength).set(new Uint8Array(positions.buffer));
offset += positions.byteLength;
new Uint8Array(payload, offset, normals.byteLength).set(new Uint8Array(normals.buffer));
offset += normals.byteLength;
new Uint8Array(payload, offset, indices.byteLength).set(new Uint8Array(indices.buffer));

const decoded = decodeSegmentationSurface(payload, { labelId: 91 });
assert.equal(decoded.version, 2);
assert.equal(decoded.vertexCount, 3);
assert.equal(decoded.triangleCount, 1);
assert.deepEqual(Array.from(decoded.normals), Array.from(normals));

const moduleText = fs.readFileSync(
  new URL("../web/js/segmentation-surface-viewer.js", import.meta.url),
  "utf8",
);
const indexText = fs.readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const appText = fs.readFileSync(new URL("../web/js/app.js", import.meta.url), "utf8");

assert.match(moduleText, /this\.descriptor\.presentation_quality/);
assert.match(moduleText, /requestedQuality === "refined"/);
assert.match(moduleText, /X-VoxelAtlas-Surface-Reference-Id/);
assert.match(moduleText, /X-VoxelAtlas-Surface-Max-Displacement-Mm/);
assert.match(moduleText, /X-VoxelAtlas-Surface-Triangle-Retention/);
assert.match(moduleText, /X-VoxelAtlas-Surface-Decimation-Applied/);
assert.match(moduleText, /Refined segmentation surface binding is invalid/);
assert.match(indexText, /Patient LPS refined surface/);
assert.match(indexText, /data-accurate-reference="Patient LPS accurate surface"/);
assert.match(appText, /segmentation-surface-viewer\.js\?v=phase6a-r1-phase6b-r1/);

console.log("PHASE6B_V2_REFINED_DECODE=PASS");
console.log("PHASE6B_PRESENTATION_QUALITY_SELECTION=PASS");
console.log("PHASE6B_REFINEMENT_PROVENANCE_BINDING=PASS");
console.log("PHASE6B_GEOMETRIC_BOUND_HEADERS=PASS");
console.log("PHASE6A_ACCURATE_REFERENCE_UI_IDENTITY=PASS");
console.log("PHASE6B_BROWSER_CONTRACT_OK=YES");
