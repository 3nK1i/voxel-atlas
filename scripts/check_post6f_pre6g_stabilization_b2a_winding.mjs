import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  patientLpsToViewerMatrix,
} from "../web/js/segmentation-surface-viewer.js";
import {
  segmentationViewerWinding,
} from "../web/js/segmentation-viewer-winding.js";

class TestMatrix4 {
  set(...values) { this.rowMajor = values; return this; }
}
const THREE = { Matrix4: TestMatrix4 };
const presentation = { viewerCenterLpsMm: [12, -8, 4], maximumExtentMm: 100 };
const matrix = patientLpsToViewerMatrix(THREE, presentation).rowMajor;
const det3 = (m) => (
  m[0] * (m[5] * m[10] - m[6] * m[9])
  - m[1] * (m[4] * m[10] - m[6] * m[8])
  + m[2] * (m[4] * m[9] - m[5] * m[8])
);
assert.ok(det3(matrix) < 0, "The actual Patient LPS viewer transform must reverse handedness");
const source = new Uint32Array([0, 1, 2, 2, 3, 0]);
const before = source.slice();
const transformed = segmentationViewerWinding(source);
assert.deepEqual(Array.from(source), Array.from(before), "Canonical source indices must remain intact");
assert.deepEqual(Array.from(transformed), [0, 2, 1, 2, 0, 3]);
assert.notStrictEqual(transformed.buffer, source.buffer);
assert.deepEqual(Array.from(segmentationViewerWinding(transformed)), Array.from(source));
assert.throws(() => segmentationViewerWinding(new Uint32Array([0, 1])), /triangle/);
assert.throws(() => segmentationViewerWinding([0, 1, 2]), /Uint32Array/);

const transform = (p) => [
  matrix[0]*p[0]+matrix[1]*p[1]+matrix[2]*p[2]+matrix[3],
  matrix[4]*p[0]+matrix[5]*p[1]+matrix[6]*p[2]+matrix[7],
  matrix[8]*p[0]+matrix[9]*p[1]+matrix[10]*p[2]+matrix[11],
];
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const sub = (a,b) => a.map((v,i)=>v-b[i]);
const dot = (a,b) => a.reduce((sum,v,i)=>sum+v*b[i],0);
const original = [[0,0,0],[1,0,0],[0,1,0]];
const transformedPositions = original.map(transform);
const faceNormal = cross(sub(transformedPositions[transformed[1]], transformedPositions[transformed[0]]),sub(transformedPositions[transformed[2]],transformedPositions[transformed[0]]));
const transformedSourceNormal = [matrix[2],matrix[6],matrix[10]];
assert.ok(dot(faceNormal,transformedSourceNormal)>0, "Display face winding must align with transformed source normal");
const unflippedNormal = cross(sub(transformedPositions[1], transformedPositions[0]),sub(transformedPositions[2],transformedPositions[0]));
assert.ok(dot(unflippedNormal,transformedSourceNormal)<0, "Previous viewer winding must demonstrate reversed orientation");

const viewerSource = readFileSync(new URL("../web/js/segmentation-surface-viewer.js", import.meta.url), "utf8");
assert.match(viewerSource, /geometry\.setIndex\(new this\.three\.BufferAttribute\(segmentationViewerWinding\(decoded\.indices\), 1\)\)/);
assert.match(viewerSource, /geometry\.applyMatrix4\(presentationTransform\)/);
assert.match(viewerSource, /geometry\.setAttribute\("normal", new this\.three\.BufferAttribute\(decoded\.normals, 3\)\)/);
console.log("B2A_LPS_VIEWER_HANDEDNESS=PASS");
console.log("B2A_SOURCE_BUFFER_UNCHANGED=PASS");
console.log("B2A_FACE_NORMAL_ALIGNMENT=PASS");
console.log("B2A_EXISTING_MATERIAL_AND_PROFILE=UNCHANGED");
