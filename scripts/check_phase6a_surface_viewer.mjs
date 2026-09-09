#!/usr/bin/env node

import assert from "node:assert/strict";
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
const accurate = new ArrayBuffer(36 + positions.byteLength + normals.byteLength + indices.byteLength);
const accurateHeader = new DataView(accurate);
writeMagic(accurateHeader);
accurateHeader.setUint32(4, 2, true);
accurateHeader.setUint32(8, 91, true);
accurateHeader.setUint32(12, 3, true);
accurateHeader.setUint32(16, 3, true);
accurateHeader.setUint32(20, positions.byteLength, true);
accurateHeader.setUint32(24, normals.byteLength, true);
accurateHeader.setUint32(28, indices.byteLength, true);
accurateHeader.setUint32(32, 1, true);
let offset = 36;
new Uint8Array(accurate, offset, positions.byteLength).set(new Uint8Array(positions.buffer));
offset += positions.byteLength;
new Uint8Array(accurate, offset, normals.byteLength).set(new Uint8Array(normals.buffer));
offset += normals.byteLength;
new Uint8Array(accurate, offset, indices.byteLength).set(new Uint8Array(indices.buffer));

const decoded = decodeSegmentationSurface(accurate, { labelId: 91 });
assert.equal(decoded.version, 2);
assert.equal(decoded.vertexCount, 3);
assert.equal(decoded.triangleCount, 1);
assert.equal(decoded.stride, 1);
assert.deepEqual(Array.from(decoded.positions), Array.from(positions));
assert.deepEqual(Array.from(decoded.normals), Array.from(normals));
assert.deepEqual(Array.from(decoded.indices), Array.from(indices));

const legacyPositions = new Float32Array([
  10, 20, 30,
  11, 20, 30,
  11, 21, 30,
  10, 21, 30,
]);
const legacyIndices = new Uint32Array([0, 1, 2, 0, 2, 3]);
const legacy = new ArrayBuffer(32 + legacyPositions.byteLength + legacyIndices.byteLength);
const legacyHeader = new DataView(legacy);
writeMagic(legacyHeader);
legacyHeader.setUint32(4, 1, true);
legacyHeader.setUint32(8, 91, true);
legacyHeader.setUint32(12, 4, true);
legacyHeader.setUint32(16, 6, true);
legacyHeader.setUint32(20, 2, true);
legacyHeader.setUint32(24, legacyPositions.byteLength, true);
legacyHeader.setUint32(28, legacyIndices.byteLength, true);
new Uint8Array(legacy, 32, legacyPositions.byteLength).set(new Uint8Array(legacyPositions.buffer));
new Uint8Array(legacy, 32 + legacyPositions.byteLength).set(new Uint8Array(legacyIndices.buffer));
const legacyDecoded = decodeSegmentationSurface(legacy, { labelId: 91 });
assert.equal(legacyDecoded.version, 1);
assert.equal(legacyDecoded.normals, null);
assert.equal(legacyDecoded.stride, 2);

const wrongFlags = accurate.slice(0);
new DataView(wrongFlags).setUint32(32, 0, true);
assert.throws(
  () => decodeSegmentationSurface(wrongFlags, { labelId: 91 }),
  /contract is invalid/,
);
assert.throws(
  () => decodeSegmentationSurface(accurate, { labelId: 90 }),
  /contract is invalid/,
);
assert.throws(
  () => decodeSegmentationSurface(accurate.slice(0, -4), { labelId: 91 }),
  /contract is invalid/,
);

console.log("PHASE6A_V2_SURFACE_DECODE=PASS");
console.log("PHASE6A_PATIENT_LPS_NORMAL_TRANSPORT=PASS");
console.log("PHASE5F1_V1_DECODE_COMPATIBILITY=PASS");
console.log("PHASE6A_BINDING_AND_TRUNCATION_REJECTION=PASS");
console.log("PHASE6A_BROWSER_CONTRACT_OK=YES");
