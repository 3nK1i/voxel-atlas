#!/usr/bin/env node
import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import { PatientVolumeSurfaceLayer } from "../web/js/volume-surface-viewer.js";

class FakeBufferAttribute { constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; } }
class FakeBufferGeometry {
  constructor() { this.attributes = {}; this.index = null; this.disposed = false; }
  setAttribute(name, value) { this.attributes[name] = value; }
  setIndex(value) { this.index = value; }
  applyMatrix4(matrix) { this.matrix = matrix; return this; }
  computeBoundingSphere() { this.boundingSphere = {}; }
  dispose() { this.disposed = true; }
}
class FakeMeshStandardMaterial { constructor(options) { Object.assign(this, options); this.disposed = false; } dispose() { this.disposed = true; } }
class FakeMesh { constructor(geometry, material) { this.geometry = geometry; this.material = material; this.userData = {}; } }
class FakeGroup {
  constructor() { this.children = []; this.userData = {}; this.parent = null; }
  add(child) { if (!this.children.includes(child)) this.children.push(child); if (child instanceof FakeGroup) child.parent = this; }
  remove(child) { this.children = this.children.filter((item) => item !== child); if (child instanceof FakeGroup) child.parent = null; }
}
class FakeMatrix4 { set(...values) { this.values = values; return this; } }
const THREE = {
  BufferGeometry: FakeBufferGeometry,
  BufferAttribute: FakeBufferAttribute,
  MeshStandardMaterial: FakeMeshStandardMaterial,
  Mesh: FakeMesh,
  Group: FakeGroup,
  Matrix4: FakeMatrix4,
  DoubleSide: "double",
};

function payload() {
  const positions = new Float32Array([0,0,0, 1,0,0, 0,1,0]);
  const normals = new Float32Array([0,0,1, 0,0,1, 0,0,1]);
  const indices = new Uint32Array([0,1,2]);
  const buffer = new ArrayBuffer(32 + positions.byteLength + normals.byteLength + indices.byteLength);
  const view = new DataView(buffer);
  new Uint8Array(buffer, 0, 4).set([86,88,86,83]);
  view.setUint32(4, 1, true);
  view.setUint32(8, 3, true);
  view.setUint32(12, 3, true);
  view.setUint32(16, positions.byteLength, true);
  view.setUint32(20, normals.byteLength, true);
  view.setUint32(24, indices.byteLength, true);
  view.setUint32(28, 1, true);
  let offset = 32;
  new Uint8Array(buffer, offset, positions.byteLength).set(new Uint8Array(positions.buffer)); offset += positions.byteLength;
  new Uint8Array(buffer, offset, normals.byteLength).set(new Uint8Array(normals.buffer)); offset += normals.byteLength;
  new Uint8Array(buffer, offset, indices.byteLength).set(new Uint8Array(indices.buffer));
  return buffer;
}

let fetchCount = 0;
let requestedBody = null;
async function fetchImpl(url, options) {
  fetchCount += 1;
  assert.equal(url, "/api/studies/latest/volume-surface");
  assert.equal(options.method, "POST");
  requestedBody = JSON.parse(options.body);
  const buffer = payload();
  const digest = createHash("sha256").update(Buffer.from(buffer)).digest("hex");
  return new Response(buffer, { status: 200, headers: {
    "Content-Type": "application/x-voxelatlas-volume-surface-v1",
    "Cache-Control": "no-store",
    "X-VoxelAtlas-Volume-Surface-Id": `vsurf-${"1".repeat(32)}`,
    "X-VoxelAtlas-Volume-Surface-Source": "canonical_volume",
    "X-VoxelAtlas-Volume-Surface-Isovalue": "300.000000",
    "X-VoxelAtlas-Volume-Surface-Units": "HU",
    "X-VoxelAtlas-Volume-Surface-Extraction": "marching_cubes_isovalue",
    "X-VoxelAtlas-Volume-Surface-SHA256": digest,
    "X-VoxelAtlas-Volume-Surface-Provenance-SHA256": "2".repeat(64),
    "X-VoxelAtlas-Volume-Surface-Vertices": "3",
    "X-VoxelAtlas-Volume-Surface-Triangles": "1",
  }});
}

const parent = new FakeGroup();
const statuses = [];
const layer = new PatientVolumeSurfaceLayer({
  three: THREE,
  parent,
  fetchImpl,
  cryptoImpl: webcrypto,
  readVolumePresentation: () => ({ viewerCenterLpsMm: [0,0,0], maximumExtentMm: 100 }),
  onStatusChange: (status) => statuses.push(status),
});
layer.setDescriptor({
  available: true,
  study_id: "a".repeat(32),
  source_type: "canonical_volume",
  source_modality: "CT",
  source_intensity_units: "HU",
  source_value_range: [-1000, 1200],
  surface_intensity_units: "HU",
  surface_isovalue_range: [-1000, 1200],
  default_isovalue: 300,
});
assert.equal(fetchCount, 0, "Setting a descriptor must never auto-build the surface");
assert.equal(layer.current, null);
await layer.build(300);
assert.equal(fetchCount, 1);
assert.deepEqual(requestedBody, { isovalue: 300 });
assert.equal(layer.current.triangleCount, 1);
assert.equal(layer.current.mesh.userData.sourceType, "canonical_volume");
assert.equal(layer.current.mesh.userData.coordinateSystem, "patient_lps");
assert.equal(layer.current.mesh.userData.isovalue, 300);
assert.equal(layer.current.material.side, "double");
assert.ok(statuses.some((status) => status.state === "loading"));
assert.ok(statuses.some((status) => status.state === "qualified"));
layer.clearSurface();
assert.equal(layer.current, null);
assert.equal(fetchCount, 1, "Clearing a surface must not trigger a new extraction");

console.log("PHASE6D1_NO_AUTOMATIC_VOLUME_SURFACE=PASS");
console.log("PHASE6D1_EXPLICIT_VOLUME_SURFACE_BUILD=PASS");
console.log("PHASE6D1_DEDICATED_VXVS_TRANSPORT=PASS");
console.log("PHASE6D1_PATIENT_LPS_PRESENTATION=PASS");
console.log("PHASE6D1_VOLUME_SOURCE_PROVENANCE=PASS");
console.log("PHASE6D1_BROWSER_CONTRACT_OK=YES");
