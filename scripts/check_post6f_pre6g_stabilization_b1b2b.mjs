#!/usr/bin/env node
import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import { PatientVolumeSurfaceLayer } from '../web/js/volume-surface-viewer.js';

const surfaceId = 'vsurf-' + '1'.repeat(32);
const surfaceSha = 'a'.repeat(64);
const labels = new Uint8Array([1, 0, 2, 1]);
const digest = (buffer) => createHash('sha256').update(Buffer.from(buffer)).digest('hex');
const headerValues = {
  'content-type': 'application/x-voxelatlas-direct-ct-regions-v1',
  'x-voxelatlas-volume-surface-id': surfaceId,
  'x-voxelatlas-volume-surface-sha256': surfaceSha,
  'x-voxelatlas-region-labels-sha256': digest(labels),
  'x-voxelatlas-region-triangles': '4',
  'x-voxelatlas-region-face-counts': '1,2,1',
  'x-voxelatlas-region-body-count': '2',
  'x-voxelatlas-region-classification': 'not_anatomical',
};
const response = (overrides = {}, bytes = labels) => ({
  ok: true,
  headers: { get: (name) => ({...headerValues, ...overrides})[name.toLowerCase()] ?? null },
  arrayBuffer: async () => new Uint8Array(bytes).buffer,
});
let fetches = 0;
const geometry = {
  index: {array: new Uint32Array([0,1,2,3,4,5,6,7,8,9,10,11]), needsUpdate: false},
  setDrawRange(start, count) { this.drawRange = {start,count}; },
};
const original = new Uint32Array(geometry.index.array);
const current = {surfaceId, payloadSha256: surfaceSha, triangleCount: 4, geometry, regionVisibility: null};
const layer = {
  current, crypto: webcrypto,
  fetchImpl: async (url, options) => {
    fetches++;
    assert.equal(url, `/api/studies/latest/volume-surface/regions?surface_id=${surfaceId}`);
    assert.equal(options.credentials, 'same-origin');
    return response();
  },
  requestRender() { this.renders = (this.renders || 0) + 1; },
  bindRegionEvidence: PatientVolumeSurfaceLayer.prototype.bindRegionEvidence,
};
const load = PatientVolumeSurfaceLayer.prototype.loadRegionEvidence;
const evidence = await load.call(layer);
assert.deepEqual(evidence, {available: true, faceCounts: Object.freeze([1,2,1])});
assert.equal(fetches, 1);
assert.equal(current.regionVisibility.mode, 'all');
assert.deepEqual(geometry.index.array, original);
PatientVolumeSurfaceLayer.prototype.setRegionDisplayMode.call(layer, 'hide-region-1');
assert.equal(geometry.drawRange.count, 6);
PatientVolumeSurfaceLayer.prototype.setRegionDisplayMode.call(layer, 'all');
assert.deepEqual(geometry.index.array, original);
assert.equal(geometry.drawRange.count, original.length);

for (const bad of [
  response({'x-voxelatlas-volume-surface-id':'vsurf-'+'2'.repeat(32)}),
  response({'x-voxelatlas-volume-surface-sha256':'b'.repeat(64)}),
  response({'x-voxelatlas-region-labels-sha256':'c'.repeat(64)}),
  response({'x-voxelatlas-region-face-counts':'1,1,2'}),
  response({}, new Uint8Array([1,0,3,1])),
]) {
  layer.fetchImpl = async () => bad;
  await assert.rejects(load.call(layer));
  assert.deepEqual(geometry.index.array, original);
  assert.equal(geometry.drawRange.count, original.length);
}
// A stale response cannot attach to the next study's surface.
layer.fetchImpl = async () => { layer.current = null; return response(); };
await assert.rejects(load.call(layer), /does not match/);
assert.equal(current.regionVisibility.mode, 'all');
assert.deepEqual(geometry.index.array, original);
console.log('B1B2B_AUTHENTICATED_EXACT_SURFACE_BINDING=PASS');
console.log('B1B2B_FAILED_OR_STALE_EVIDENCE_DOES_NOT_HIDE_GEOMETRY=PASS');
console.log('B1B2B_REVERSIBLE_NO_EXTRACTION=PASS');
