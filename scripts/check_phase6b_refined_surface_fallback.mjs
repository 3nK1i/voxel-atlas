#!/usr/bin/env node
import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import { PatientSegmentationSurfaceLayer } from "../web/js/segmentation-surface-viewer.js";

class FakeColor { constructor(value) { this.value = value; } set(value) { this.value = value; return this; } }
class FakeBufferAttribute { constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; } }
class FakeBufferGeometry {
  constructor() { this.attributes = {}; this.index = null; }
  setAttribute(name, value) { this.attributes[name] = value; }
  setIndex(value) { this.index = value; }
  applyMatrix4() { return this; }
  computeVertexNormals() {}
  computeBoundingSphere() {}
  dispose() {}
}
class FakeMaterial { constructor(options) { Object.assign(this, options); this.color = new FakeColor(options.color); } dispose() {} }
class FakeMesh { constructor(geometry, material) { this.geometry = geometry; this.material = material; this.userData = {}; this.visible = true; } }
class FakeGroup {
  constructor() { this.children = []; this.userData = {}; this.visible = true; }
  add(child) { if (!this.children.includes(child)) this.children.push(child); }
  remove(child) { this.children = this.children.filter((item) => item !== child); }
  removeFromParent() {}
}
class FakeMatrix4 { set(...values) { this.values = values; return this; } }
const THREE = {
  BufferGeometry: FakeBufferGeometry,
  BufferAttribute: FakeBufferAttribute,
  MeshStandardMaterial: FakeMaterial,
  Mesh: FakeMesh,
  Group: FakeGroup,
  Matrix4: FakeMatrix4,
  FrontSide: "front",
  DoubleSide: "double",
};

function payloadFor(labelId) {
  const positions = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
  const normals = new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]);
  const indices = new Uint32Array([0, 1, 2]);
  const buffer = new ArrayBuffer(36 + positions.byteLength + normals.byteLength + indices.byteLength);
  const view = new DataView(buffer);
  new Uint8Array(buffer, 0, 4).set([86, 88, 83, 70]);
  view.setUint32(4, 2, true);
  view.setUint32(8, labelId, true);
  view.setUint32(12, 3, true);
  view.setUint32(16, 3, true);
  view.setUint32(20, positions.byteLength, true);
  view.setUint32(24, normals.byteLength, true);
  view.setUint32(28, indices.byteLength, true);
  view.setUint32(32, 1, true);
  let offset = 36;
  new Uint8Array(buffer, offset, positions.byteLength).set(new Uint8Array(positions.buffer));
  offset += positions.byteLength;
  new Uint8Array(buffer, offset, normals.byteLength).set(new Uint8Array(normals.buffer));
  offset += normals.byteLength;
  new Uint8Array(buffer, offset, indices.byteLength).set(new Uint8Array(indices.buffer));
  return buffer;
}

const labelId = 92;
const labelMapId = "map-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const descriptor = {
  ready: true,
  label_map_id: labelMapId,
  coordinate_system: "patient_lps",
  present_labels: [labelId],
  default_quality: "accurate",
  presentation_quality: "refined",
  accurate_surface: { extraction: "marching_cubes_half_voxel" },
  refined_surface: {
    refinement: "bounded_taubin_vertex_clustering",
    minimum_triangle_retention_ratio: 0.70,
    cluster_cell_sizes_index: [0.50, 0.65, 0.70, 0.80],
  },
};
const presentation = {
  selectedLabelId: labelId,
  isolatedLabelId: null,
  structures: new Map([[labelId, {
    labelId,
    displayName: "Left Rib 1",
    colorHex: "#d8c85a",
    opacity: 1,
    visible: true,
    surfaceVisible: true,
  }]]),
};

const requestedQualities = [];
async function fetchImpl(url) {
  const parsed = new URL(String(url), "http://127.0.0.1");
  const quality = parsed.searchParams.get("quality");
  requestedQualities.push(quality);
  if (quality === "refined") {
    return new Response(JSON.stringify({ detail: "Refined segmentation surface worker failed" }), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    });
  }
  assert.equal(quality, "accurate");
  const buffer = payloadFor(labelId);
  const digest = createHash("sha256").update(Buffer.from(buffer)).digest("hex");
  return new Response(buffer, {
    status: 200,
    headers: {
      "Content-Type": "application/x-voxelatlas-surface-v2",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
      "X-VoxelAtlas-Label-Map-Id": labelMapId,
      "X-VoxelAtlas-Label-Id": String(labelId),
      "X-VoxelAtlas-Surface-Quality": "accurate",
      "X-VoxelAtlas-Surface-SHA256": digest,
      "X-VoxelAtlas-Surface-Vertices": "3",
      "X-VoxelAtlas-Surface-Triangles": "1",
      "X-VoxelAtlas-Surface-Schema": "2",
      "X-VoxelAtlas-Surface-Id": `surf-${"a".repeat(32)}`,
      "X-VoxelAtlas-Surface-Provenance-SHA256": "b".repeat(64),
      "X-VoxelAtlas-Surface-Extraction": "marching_cubes_half_voxel",
      "X-VoxelAtlas-Surface-Refinement": "",
      "X-VoxelAtlas-Surface-Reference-Id": "",
      "X-VoxelAtlas-Surface-Reference-SHA256": "",
      "X-VoxelAtlas-Surface-Max-Displacement-Mm": "0.000000",
      "X-VoxelAtlas-Surface-Displacement-Limit-Mm": "0.000000",
      "X-VoxelAtlas-Surface-Triangle-Retention": "1.000000000",
      "X-VoxelAtlas-Surface-Decimation-Applied": "false",
      "X-VoxelAtlas-Surface-Decimation-Cell-Index": "0.000000",
    },
  });
}

const statuses = [];
const layer = new PatientSegmentationSurfaceLayer({
  three: THREE,
  parent: new FakeGroup(),
  fetchImpl,
  cryptoImpl: webcrypto,
  readVolumePresentation: () => ({ viewerCenterLpsMm: [0, 0, 0], maximumExtentMm: 100 }),
  onStatusChange: (status) => statuses.push(status),
});
layer.setDescriptor(descriptor);
await layer.sync(presentation);
const deadline = Date.now() + 1500;
while ((layer.activeLoads !== 0 || layer.items.size !== 1) && Date.now() < deadline) {
  await new Promise((resolve) => setTimeout(resolve, 10));
}

assert.deepEqual(requestedQualities, ["refined", "accurate"]);
assert.equal(layer.failedLabels.size, 0);
assert.equal(layer.items.size, 1);
const item = layer.items.get(labelId);
assert.equal(item.mesh.userData.surfaceQuality, "accurate");
assert.equal(item.mesh.userData.presentationFallback, true);
assert.equal(item.mesh.userData.presentationFallbackFrom, "refined");
const finalStatus = statuses.findLast((status) => status.state === "qualified");
assert.ok(finalStatus);
assert.equal(finalStatus.fallbackCount, 1);
assert.equal(finalStatus.labels[0].fallback, true);
assert.equal(finalStatus.labels[0].quality, "accurate");
assert.match(finalStatus.message, /accurate fallback/);


const serverFailureRequests = [];
async function serverFailureFetch(url) {
  const parsed = new URL(String(url), "http://127.0.0.1");
  serverFailureRequests.push(parsed.searchParams.get("quality"));
  return new Response(JSON.stringify({ detail: "Unexpected server failure" }), {
    status: 500,
    headers: { "Content-Type": "application/json" },
  });
}
const serverFailureLayer = new PatientSegmentationSurfaceLayer({
  three: THREE,
  parent: new FakeGroup(),
  fetchImpl: serverFailureFetch,
  cryptoImpl: webcrypto,
  readVolumePresentation: () => ({ viewerCenterLpsMm: [0, 0, 0], maximumExtentMm: 100 }),
});
serverFailureLayer.setDescriptor(descriptor);
await serverFailureLayer.sync(presentation);
const failureDeadline = Date.now() + 1500;
while (serverFailureLayer.activeLoads !== 0 && Date.now() < failureDeadline) {
  await new Promise((resolve) => setTimeout(resolve, 10));
}
assert.deepEqual(serverFailureRequests, ["refined"]);
assert.equal(serverFailureLayer.items.size, 0);
assert.equal(serverFailureLayer.failedLabels.size, 1);

console.log("REFINED_422_TO_ACCURATE_FALLBACK=PASS");
console.log("FALLBACK_PROVENANCE_VISIBLE=PASS");
console.log("NON_422_REFINEMENT_FAILURE_DOES_NOT_FALLBACK=PASS");
console.log("FAILED_LABEL_COUNT_AFTER_FALLBACK=0");
console.log("PHASE6B_REFINED_SURFACE_FALLBACK_OK=YES");
