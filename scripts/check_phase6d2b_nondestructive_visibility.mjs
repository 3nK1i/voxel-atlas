#!/usr/bin/env node
import assert from "node:assert/strict";
import { PatientVolumeSurfaceLayer } from "../web/js/volume-surface-viewer.js";
import { PatientSegmentationSurfaceLayer } from "../web/js/segmentation-surface-viewer.js";

class FakeGroup {
  constructor() { this.children = []; this.userData = {}; this.visible = true; this.parent = null; }
  add(child) { if (!this.children.includes(child)) this.children.push(child); child.parent = this; }
  remove(child) { this.children = this.children.filter((entry) => entry !== child); child.parent = null; }
  removeFromParent() { this.parent?.remove?.(this); }
}
class FakeGeometry { constructor() { this.disposed = false; } dispose() { this.disposed = true; } }
class FakeMaterial { constructor() { this.disposed = false; } dispose() { this.disposed = true; } }
class FakeMesh { constructor() { this.visible = true; this.userData = {}; this.parent = null; } }
class FakeBufferGeometry {}
class FakeMeshStandardMaterial {}
class FakeMatrix4 { set() { return this; } }
const THREE = {
  Group: FakeGroup,
  BufferGeometry: FakeBufferGeometry,
  Mesh: FakeMesh,
  MeshStandardMaterial: FakeMeshStandardMaterial,
  Matrix4: FakeMatrix4,
};

let renderRequests = 0;
const parent = new FakeGroup();
const volumeLayer = new PatientVolumeSurfaceLayer({
  three: THREE,
  parent,
  fetchImpl: async () => { throw new Error("fetch must not run during presentation visibility changes"); },
  requestRender: () => { renderRequests += 1; },
});
const volumeGeometry = new FakeGeometry();
const volumeMaterial = new FakeMaterial();
const volumeMesh = new FakeMesh();
volumeLayer.current = { mesh: volumeMesh, geometry: volumeGeometry, material: volumeMaterial };
volumeLayer.group.add(volumeMesh);
const volumeIdentity = volumeLayer.current;
volumeLayer.setPresentationVisible(false);
assert.equal(volumeLayer.group.visible, false);
assert.equal(volumeLayer.current, volumeIdentity);
assert.equal(volumeGeometry.disposed, false);
assert.equal(volumeMaterial.disposed, false);
volumeLayer.setPresentationVisible(true);
assert.equal(volumeLayer.group.visible, true);
assert.equal(volumeLayer.current, volumeIdentity);

let abortCount = 0;
const segmentationLayer = new PatientSegmentationSurfaceLayer({
  three: THREE,
  parent,
  fetchImpl: async () => { throw new Error("fetch must not run during presentation visibility changes"); },
  requestRender: () => { renderRequests += 1; },
});
const segGeometry = new FakeGeometry();
const segMaterial = new FakeMaterial();
const segMesh = new FakeMesh();
segmentationLayer.items.set(91, {
  labelId: 91,
  mesh: segMesh,
  geometry: segGeometry,
  material: segMaterial,
  triangleCount: 12,
});
segmentationLayer.group.add(segMesh);
segmentationLayer.controllers.set(91, { abort: () => { abortCount += 1; } });
segmentationLayer.queue.push({ labelId: 92, generation: segmentationLayer.generation });

segmentationLayer.setPresentationVisible(false);
assert.equal(segmentationLayer.group.visible, false);
assert.equal(abortCount, 0, "Presentation hiding must not abort pending surface work");
assert.equal(segmentationLayer.controllers.size, 1);
assert.equal(segmentationLayer.queue.length, 1);
assert.equal(segmentationLayer.items.size, 1);
assert.equal(segGeometry.disposed, false);
assert.equal(segMaterial.disposed, false);
segmentationLayer.setPresentationVisible(true);
assert.equal(segmentationLayer.group.visible, true);
assert.equal(segmentationLayer.items.size, 1);
assert.equal(abortCount, 0);

segmentationLayer.setEnabled(false);
assert.equal(abortCount, 1, "Existing semantic Show toggle lifecycle remains authoritative");
assert.equal(segmentationLayer.group.visible, false);

assert.ok(renderRequests >= 4);
console.log("PHASE6D2B_VOLUME_SURFACE_VISIBILITY_NON_DESTRUCTIVE=PASS");
console.log("PHASE6D2B_SEGMENTATION_VISIBILITY_NON_DESTRUCTIVE=PASS");
console.log("PHASE6D2B_PENDING_SEGMENTATION_WORK_PRESERVED=PASS");
console.log("PHASE6D2B_EXISTING_SHOW_TOGGLE_LIFECYCLE_PRESERVED=PASS");
console.log("PHASE6D2B_NONDESTRUCTIVE_VISIBILITY_OK=YES");
