import assert from "node:assert/strict";
import {
  ReconstructionVisualizationModeController,
  listReconstructionVisualizationModes,
  listReconstructionSurfaceSources,
} from "../web/js/reconstruction-visualization-mode.js";

const modes = listReconstructionVisualizationModes();
assert.deepEqual(modes.map((entry) => entry.id), ["volume", "surface", "combined"]);
assert.deepEqual(modes.map((entry) => entry.label), ["Volume", "Surface", "Combined"]);

const sources = listReconstructionSurfaceSources();
assert.deepEqual(sources.map((entry) => entry.id), ["volume-derived", "segmentation-derived"]);

const controller = new ReconstructionVisualizationModeController();
let snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume");
assert.equal(snapshot.canVolume, false);
assert.equal(snapshot.canSurface, false);
assert.equal(snapshot.canCombined, false);
assert.deepEqual(snapshot.selectedSurfaceSources, []);
assert.equal(snapshot.visibility.volume, false);
assert.deepEqual(snapshot.visibility.surfaceSources, {
  "volume-derived": false,
  "segmentation-derived": false,
});

controller.setVolumeAvailable(true);
snapshot = controller.snapshot();
assert.equal(snapshot.canVolume, true);
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.canSurface, false);
assert.equal(snapshot.canCombined, false);

controller.setSurfaceSource("volume-derived", { available: true, resident: true, selected: true });
snapshot = controller.snapshot();
assert.deepEqual(snapshot.selectedSurfaceSources, ["volume-derived"]);
assert.equal(snapshot.canSurface, true);
assert.equal(snapshot.canCombined, true);
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], false);

assert.equal(controller.requestMode("surface").accepted, true);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "surface");
assert.equal(snapshot.visibility.volume, false);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], true);

assert.equal(controller.requestMode("combined").accepted, true);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "combined");
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], true);

controller.setSurfaceSource("segmentation-derived", { available: true, resident: true, selected: true });
snapshot = controller.snapshot();
assert.deepEqual(snapshot.selectedSurfaceSources, ["volume-derived", "segmentation-derived"]);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], true);
assert.equal(snapshot.visibility.surfaceSources["segmentation-derived"], true);

controller.setSurfaceSource("volume-derived", { resident: false });
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "combined");
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], false);
assert.equal(snapshot.visibility.surfaceSources["segmentation-derived"], true);

controller.setSurfaceSource("segmentation-derived", { resident: false });
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume");
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.canSurface, false);
assert.equal(snapshot.canCombined, false);

const rejected = controller.requestMode("surface");
assert.equal(rejected.accepted, false);
assert.equal(rejected.reason, "surface-unavailable");
assert.equal(controller.snapshot().mode, "volume");

controller.setVolumeAvailable(false);
controller.setSurfaceSource("segmentation-derived", { available: true, resident: true, selected: true });
assert.equal(controller.requestMode("surface").accepted, true);
controller.setSurfaceSource("segmentation-derived", { resident: false });
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume");
assert.equal(snapshot.visibility.volume, false);

controller.reset();
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume");
assert.equal(snapshot.volumeAvailable, false);
assert.deepEqual(snapshot.selectedSurfaceSources, []);

assert.throws(() => controller.requestMode("diagnostic"), /Unknown reconstruction visualization mode/);
assert.throws(() => controller.setSurfaceSource("mesh-x", { available: true }), /Unknown reconstruction surface source/);

console.log("PHASE6D2A_MODE_CATALOG=PASS");
console.log("PHASE6D2A_SURFACE_SOURCE_SEPARATION=PASS");
console.log("PHASE6D2A_VISIBILITY_PLAN=PASS");
console.log("PHASE6D2A_UNAVAILABLE_MODE_REJECTION=PASS");
console.log("PHASE6D2A_DETERMINISTIC_FALLBACK=PASS");
console.log("PHASE6D2A_CONTROLLER_OK=YES");
