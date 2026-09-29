#!/usr/bin/env node
import assert from "node:assert/strict";
import { ReconstructionVisualizationModeController } from "../web/js/reconstruction-visualization-mode.js";

const controller = new ReconstructionVisualizationModeController();

controller.setVolumeAvailable(true);
controller.setSurfaceSource("volume-derived", { available: true, resident: true, selected: true });
controller.setSurfaceSource("segmentation-derived", { available: true, resident: true, selected: true });
assert.equal(controller.requestMode("combined").accepted, true);
let snapshot = controller.snapshot();
assert.equal(snapshot.mode, "combined");
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], true);
assert.equal(snapshot.visibility.surfaceSources["segmentation-derived"], true);

controller.setSurfaceSource("volume-derived", { resident: false });
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "combined", "Combined remains valid while one selected resident source remains");
assert.deepEqual(snapshot.selectedResidentSurfaceSources, ["segmentation-derived"]);

controller.setSurfaceSource("segmentation-derived", { resident: false });
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume", "Loss of the final surface must reconcile to Volume");
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.canSurface, false);
assert.equal(snapshot.canCombined, false);

const unavailableSurface = controller.requestMode("surface");
assert.equal(unavailableSurface.accepted, false);
assert.equal(unavailableSurface.reason, "surface-unavailable");
assert.equal(controller.snapshot().mode, "volume");

controller.setSurfaceSource("volume-derived", { available: true, resident: true, selected: true });
assert.equal(controller.requestMode("surface").accepted, true);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "surface");
assert.equal(snapshot.visibility.volume, false);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], true);

controller.setVolumeAvailable(false);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "surface", "Resident surface remains usable if volume presentation becomes unavailable");
assert.equal(snapshot.visibility.volume, false);

controller.reset();
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume");
assert.equal(snapshot.volumeAvailable, false);
assert.deepEqual(snapshot.selectedSurfaceSources, []);
assert.deepEqual(snapshot.residentSurfaceSources, []);
assert.equal(snapshot.canSurface, false);
assert.equal(snapshot.canCombined, false);

console.log("PHASE6D2D_FINAL_SOURCE_REMOVAL_FALLBACK=PASS");
console.log("PHASE6D2D_UNAVAILABLE_MODE_REJECTION=PASS");
console.log("PHASE6D2D_SURFACE_ONLY_WITHOUT_VOLUME=PASS");
console.log("PHASE6D2D_CONTROLLER_RESET=PASS");
console.log("PHASE6D2D_STATE_CLOSURE_OK=YES");
