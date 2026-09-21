#!/usr/bin/env node
import assert from "node:assert/strict";
import { createDirectCtRegionVisibility } from "../web/js/direct-ct-region-visibility.js";
import { PatientVolumeSurfaceLayer } from "../web/js/volume-surface-viewer.js";

function fixture() {
  const indices = new Uint32Array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
  const attribute = { array: indices, needsUpdate: false };
  const geometry = { index: attribute, setDrawRange(start, count) { this.drawRange = { start, count }; } };
  return { geometry, attribute, indices, original: new Uint32Array(indices) };
}
const s = fixture();
const labels = new Uint8Array([1, 0, 2, 1]);
const originalLabels = new Uint8Array(labels);
const state = createDirectCtRegionVisibility(s.geometry, labels);
assert.equal(state.available, true);
assert.deepEqual(state.faceCounts, [1, 2, 1]);
assert.equal(state.mode, "all");
assert.deepEqual(s.indices, s.original);
assert.deepEqual(s.geometry.drawRange, {start: 0, count: 12});
assert.equal(state.show("hide-region-2").visibleTriangles, 3);
assert.deepEqual([...s.indices.slice(0, 9)], [0,1,2,3,4,5,9,10,11]);
assert.equal(state.show("hide-region-1").visibleTriangles, 2);
assert.deepEqual([...s.indices.slice(0, 6)], [3,4,5,6,7,8]);
assert.equal(state.show("all").visibleTriangles, 4);
assert.deepEqual(s.indices, s.original);
assert.deepEqual(labels, originalLabels);
assert.equal(s.geometry.index, s.attribute, "The same resident index buffer must be reused");
assert.equal(s.attribute.array, s.indices);
assert.equal(s.attribute.needsUpdate, true);
assert.throws(() => state.show("hide-both"), /Unknown/);
assert.deepEqual(s.indices, s.original, "Invalid display mode must leave the original visible");

const one = fixture();
const singleton = createDirectCtRegionVisibility(one.geometry, new Uint8Array([0,1,1,1]));
assert.equal(singleton.available, false);
assert.throws(() => singleton.show("hide-region-1"), /Two distinct/);
assert.deepEqual(one.indices, one.original);

for (const invalid of [new Uint8Array([1, 2]), new Uint8Array([1, 2, 0, 3]), new Int8Array([1, 2, 0, 1])]) {
  assert.throws(() => createDirectCtRegionVisibility(fixture().geometry, invalid));
}
const altered = fixture();
const bound = createDirectCtRegionVisibility(altered.geometry, labels);
altered.geometry.index = { array: altered.indices, needsUpdate: false };
assert.throws(() => bound.show("hide-region-2"), /geometry changed/);

// The viewer does not auto-bind, auto-hide or request an extraction when evidence
// is absent/mismatched; its current mesh remains untouched until explicit choice.
assert.equal(typeof PatientVolumeSurfaceLayer.prototype.bindRegionEvidence, "function");
assert.equal(typeof PatientVolumeSurfaceLayer.prototype.setRegionDisplayMode, "function");
const fake = {
  current: {surfaceId: "vsurf-" + "1".repeat(32), geometry: fixture().geometry, regionVisibility: null},
  requestRender() { this.renders = (this.renders || 0) + 1; },
};
assert.throws(() => PatientVolumeSurfaceLayer.prototype.bindRegionEvidence.call(fake, "vsurf-mismatch", labels), /does not match/);
assert.equal(fake.current.regionVisibility, null);
assert.throws(() => PatientVolumeSurfaceLayer.prototype.setRegionDisplayMode.call(fake, "hide-region-2"), /not available/);
const result = PatientVolumeSurfaceLayer.prototype.bindRegionEvidence.call(fake, fake.current.surfaceId, labels);
assert.equal(result.available, true);
assert.equal(fake.current.regionVisibility.mode, "all");
PatientVolumeSurfaceLayer.prototype.setRegionDisplayMode.call(fake, "hide-region-2");
assert.equal(fake.current.regionVisibility.mode, "hide-region-2");
PatientVolumeSurfaceLayer.prototype.setRegionDisplayMode.call(fake, "all");
assert.equal(fake.current.regionVisibility.mode, "all");
assert.ok(fake.renders >= 3);
console.log("B1B2A_RESIDENT_INDEX_VISIBILITY=PASS");
console.log("B1B2A_EXPLICIT_REVERSIBLE_DISPLAY=PASS");
console.log("B1B2A_NO_SOURCE_MUTATION_OR_EXTRACTION=PASS");
