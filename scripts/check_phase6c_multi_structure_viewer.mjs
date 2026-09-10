#!/usr/bin/env node
import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import {
  PatientSegmentationSurfaceLayer,
} from "../web/js/segmentation-surface-viewer.js";
import {
  activateSurfaceForStructure,
  createStructurePresentation,
  isolateStructure,
  resetStructurePresentation,
} from "../web/js/segmentation-structure-panel.js";

class FakeColor {
  constructor(value) { this.value = value; }
  set(value) { this.value = value; return this; }
}
class FakeBufferAttribute {
  constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; }
}
class FakeBufferGeometry {
  constructor() { this.attributes = {}; this.index = null; this.disposed = false; }
  setAttribute(name, attribute) { this.attributes[name] = attribute; }
  setIndex(attribute) { this.index = attribute; }
  applyMatrix4() { return this; }
  computeVertexNormals() { this.computedNormals = true; }
  computeBoundingSphere() { this.boundingSphere = {}; }
  dispose() { this.disposed = true; }
}
class FakeMeshStandardMaterial {
  constructor(options) {
    Object.assign(this, options);
    this.color = new FakeColor(options.color);
    this.needsUpdate = false;
    this.disposed = false;
  }
  dispose() { this.disposed = true; }
}
class FakeMesh {
  constructor(geometry, material) {
    this.geometry = geometry;
    this.material = material;
    this.userData = {};
    this.visible = true;
    this.renderOrder = 0;
  }
}
class FakeGroup {
  constructor() { this.children = []; this.userData = {}; this.visible = true; }
  add(child) { if (!this.children.includes(child)) this.children.push(child); }
  remove(child) { this.children = this.children.filter((item) => item !== child); }
  removeFromParent() { this.removed = true; }
}
class FakeMatrix4 { set(...values) { this.values = values; return this; } }

const THREE = {
  BufferGeometry: FakeBufferGeometry,
  BufferAttribute: FakeBufferAttribute,
  MeshStandardMaterial: FakeMeshStandardMaterial,
  Mesh: FakeMesh,
  Group: FakeGroup,
  Matrix4: FakeMatrix4,
  FrontSide: "front",
  DoubleSide: "double",
};

function payloadFor(labelId) {
  const positions = new Float32Array([
    0, 0, 0,
    1, 0, 0,
    0, 1, 0,
  ]);
  const normals = new Float32Array([
    0, 0, 1,
    0, 0, 1,
    0, 0, 1,
  ]);
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

const catalogDescriptor = {
  label_map_id: "map-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  structure_catalog: {
    schema_version: 1,
    structure_count: 3,
    groups: [{ group_id: "organs", display_name: "Organs" }],
    structures: [1, 2, 3].map((labelId) => ({
      label_id: labelId,
      name: `label_${labelId}`,
      display_name: `Structure ${labelId}`,
      group_id: "organs",
      group_name: "Organs",
      color_hex: ["#c66b5e", "#e2a55f", "#77a8c7"][labelId - 1],
      default_visible: true,
      default_opacity: 1,
    })),
  },
};

const presentation = createStructurePresentation(catalogDescriptor);
assert.equal(presentation.selectedLabelId, null);
assert.equal(
  Array.from(presentation.structures.values()).some((item) => item.surfaceVisible),
  false,
  "Activating segmentation must not auto-request a 3D surface",
);
activateSurfaceForStructure(presentation, 1);
assert.equal(presentation.structures.get(1).surfaceVisible, true);
assert.equal(presentation.structures.get(2).surfaceVisible, false);
activateSurfaceForStructure(presentation, 2);
assert.equal(presentation.structures.get(1).surfaceVisible, true);
assert.equal(presentation.structures.get(2).surfaceVisible, true);
isolateStructure(presentation, 3);
assert.deepEqual(
  Array.from(presentation.structures.values()).filter((item) => item.surfaceVisible).map((item) => item.labelId),
  [3],
);
resetStructurePresentation(presentation);
assert.equal(Array.from(presentation.structures.values()).every((item) => item.visible), true);
assert.equal(presentation.selectedLabelId, null);
assert.deepEqual(
  Array.from(presentation.structures.values()).filter((item) => item.surfaceVisible).map((item) => item.labelId),
  [],
);
activateSurfaceForStructure(presentation, 1);
activateSurfaceForStructure(presentation, 2);
activateSurfaceForStructure(presentation, 3);

const surfaceDescriptor = {
  ready: true,
  label_map_id: catalogDescriptor.label_map_id,
  coordinate_system: "patient_lps",
  present_labels: [1, 2, 3],
  default_quality: "accurate",
  presentation_quality: "refined",
  accurate_surface: { extraction: "marching_cubes_half_voxel" },
  refined_surface: {
    refinement: "bounded_taubin_vertex_clustering",
    minimum_triangle_retention_ratio: 0.70,
    cluster_cell_sizes_index: [0.50, 0.65, 0.70, 0.80],
  },
};

let activeFetches = 0;
let maximumConcurrentFetches = 0;
const requestedLabels = [];
async function fetchImpl(url) {
  activeFetches += 1;
  maximumConcurrentFetches = Math.max(maximumConcurrentFetches, activeFetches);
  const match = String(url).match(/segmentation-surfaces\/(\d+)\?/);
  assert.ok(match);
  const labelId = Number(match[1]);
  requestedLabels.push(labelId);
  await new Promise((resolve) => setTimeout(resolve, 8));
  const buffer = payloadFor(labelId);
  const digest = createHash("sha256").update(Buffer.from(buffer)).digest("hex");
  activeFetches -= 1;
  return new Response(buffer, {
    status: 200,
    headers: {
      "Content-Type": "application/x-voxelatlas-surface-v2",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
      "X-VoxelAtlas-Label-Map-Id": surfaceDescriptor.label_map_id,
      "X-VoxelAtlas-Label-Id": String(labelId),
      "X-VoxelAtlas-Surface-Quality": "refined",
      "X-VoxelAtlas-Surface-SHA256": digest,
      "X-VoxelAtlas-Surface-Vertices": "3",
      "X-VoxelAtlas-Surface-Triangles": "1",
      "X-VoxelAtlas-Surface-Schema": "2",
      "X-VoxelAtlas-Surface-Id": `surf-${labelId.toString(16).padStart(32, "0")}`,
      "X-VoxelAtlas-Surface-Provenance-SHA256": "9".repeat(64),
      "X-VoxelAtlas-Surface-Extraction": "marching_cubes_half_voxel",
      "X-VoxelAtlas-Surface-Refinement": "bounded_taubin_vertex_clustering",
      "X-VoxelAtlas-Surface-Reference-Id": `surf-${"a".repeat(31)}${labelId}`,
      "X-VoxelAtlas-Surface-Reference-SHA256": "8".repeat(64),
      "X-VoxelAtlas-Surface-Max-Displacement-Mm": "0.100000",
      "X-VoxelAtlas-Surface-Displacement-Limit-Mm": "0.500000",
      "X-VoxelAtlas-Surface-Triangle-Retention": "1.000000000",
      "X-VoxelAtlas-Surface-Decimation-Applied": "false",
      "X-VoxelAtlas-Surface-Decimation-Cell-Index": "0.000000",
    },
  });
}

const parent = new FakeGroup();
const statuses = [];
const layer = new PatientSegmentationSurfaceLayer({
  three: THREE,
  parent,
  fetchImpl,
  cryptoImpl: webcrypto,
  readVolumePresentation: () => ({
    viewerCenterLpsMm: [0, 0, 0],
    maximumExtentMm: 100,
  }),
  onStatusChange: (status) => statuses.push(status),
});
layer.setDescriptor(surfaceDescriptor);
await layer.sync(presentation);

const loadingSnapshot = statuses.find((status) => (
  status.state === "loading"
  && status.labels?.some((entry) => entry.labelId === 3 && entry.state === "building")
));
assert.ok(loadingSnapshot, "Selected structure should expose a real building state immediately");
assert.match(loadingSnapshot.message, /Building Structure 3 surface…/);
assert.equal(loadingSnapshot.buildingCount >= 1, true);
assert.equal(loadingSnapshot.queuedCount >= 1, true);
assert.equal(loadingSnapshot.requestedCount, 3);

const deadline = Date.now() + 2500;
while ((layer.items.size !== 3 || layer.activeLoads !== 0) && Date.now() < deadline) {
  await new Promise((resolve) => setTimeout(resolve, 10));
}
assert.equal(layer.items.size, 3);
assert.equal(layer.activeLoads, 0);
assert.equal(maximumConcurrentFetches <= 2, true);
assert.deepEqual(requestedLabels.slice().sort((a, b) => a - b), [1, 2, 3]);
assert.equal(layer.group.children.length, 3);
for (const item of layer.items.values()) {
  assert.ok(item.material instanceof FakeMeshStandardMaterial);
  assert.equal(item.material.metalness, 0.0);
  assert.equal(item.mesh.visible, true);
  assert.equal(item.mesh.userData.surfaceQuality, "refined");
}

presentation.structures.get(2).surfaceVisible = false;
presentation.structures.get(1).colorHex = "#123456";
presentation.structures.get(1).opacity = 0.5;
await layer.sync(presentation);
assert.equal(layer.items.get(2).mesh.visible, false);
assert.equal(layer.items.get(1).material.color.value, "#123456");
assert.equal(layer.items.get(1).material.opacity, 0.5);
assert.equal(layer.items.get(1).material.depthWrite, false);
assert.equal(layer.items.size, 3, "Hidden surfaces should stay resident within the study");
const qualifiedSnapshot = statuses.findLast((status) => status.state === "qualified");
assert.ok(qualifiedSnapshot);
assert.equal(qualifiedSnapshot.readyCount, 2);
assert.equal(qualifiedSnapshot.labels.find((entry) => entry.labelId === 1)?.state, "ready");
assert.equal(qualifiedSnapshot.labels.find((entry) => entry.labelId === 2)?.state, "ready");
assert.equal(qualifiedSnapshot.labels.find((entry) => entry.labelId === 3)?.state, "ready");

layer.clear();
assert.equal(layer.items.size, 0);
assert.equal(layer.group.children.length, 0);

console.log("PHASE6C_MULTI_STRUCTURE_RESIDENCY=PASS");
console.log("PHASE6C_EXPLICIT_INITIAL_SURFACE_SELECTION=PASS");
console.log("PHASE6C_PROGRESSIVE_SURFACE_ACTIVATION=PASS");
console.log("PHASE6C_BOUNDED_CONCURRENT_LOADS=PASS");
console.log("PHASE6C_POLISHED_STANDARD_MATERIAL=PASS");
console.log("PHASE6C_HIDDEN_SURFACE_RESIDENCY=PASS");
console.log("PHASE6C_SURFACE_BUILD_FEEDBACK=PASS");
console.log("PHASE6C_REAL_COMPLETION_COUNTS=PASS");
console.log("PHASE6C_BROWSER_CONTRACT_OK=YES");
