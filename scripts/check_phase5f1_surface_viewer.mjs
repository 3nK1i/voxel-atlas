#!/usr/bin/env node

import assert from "node:assert/strict";
import { decodeSegmentationSurface } from "../web/js/segmentation-surface-viewer.js";


const vertexCount = 4;
const indices = new Uint32Array([0, 1, 2, 0, 2, 3]);
const positions = new Float32Array([
  10, 20, 30,
  11, 20, 30,
  11, 21, 30,
  10, 21, 30,
]);
const buffer = new ArrayBuffer(32 + positions.byteLength + indices.byteLength);
const header = new DataView(buffer);
for (const [index, character] of Array.from("VXSF").entries()) {
  header.setUint8(index, character.charCodeAt(0));
}
header.setUint32(4, 1, true);
header.setUint32(8, 91, true);
header.setUint32(12, vertexCount, true);
header.setUint32(16, indices.length, true);
header.setUint32(20, 2, true);
header.setUint32(24, positions.byteLength, true);
header.setUint32(28, indices.byteLength, true);
new Uint8Array(buffer, 32, positions.byteLength).set(new Uint8Array(positions.buffer));
new Uint8Array(buffer, 32 + positions.byteLength).set(new Uint8Array(indices.buffer));

const decoded = decodeSegmentationSurface(buffer, { labelId: 91 });
assert.equal(decoded.labelId, 91);
assert.equal(decoded.vertexCount, 4);
assert.equal(decoded.triangleCount, 2);
assert.equal(decoded.stride, 2);
assert.deepEqual(Array.from(decoded.positions), Array.from(positions));
assert.deepEqual(Array.from(decoded.indices), Array.from(indices));

assert.throws(
  () => decodeSegmentationSurface(buffer, { labelId: 90 }),
  /contract is invalid/,
);
assert.throws(
  () => decodeSegmentationSurface(buffer.slice(0, -4), { labelId: 91 }),
  /contract is invalid/,
);

console.log("PHASE5F1_BINARY_SURFACE_DECODE=PASS");
console.log("PHASE5F1_LABEL_BINDING=PASS");
console.log("PHASE5F1_TRUNCATION_REJECTION=PASS");
console.log("PHASE5F1_BROWSER_CONTRACT_OK=YES");
