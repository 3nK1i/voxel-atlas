#!/usr/bin/env node
import assert from "node:assert/strict";
import { ReconstructionVisualizationModeController } from "../web/js/reconstruction-visualization-mode.js";

const controller = new ReconstructionVisualizationModeController();
controller.setVolumeAvailable(true);
controller.setSurfaceSource("volume-derived", { available: true, resident: true, selected: true });
controller.setSurfaceSource("segmentation-derived", { available: true, resident: true, selected: true });

let snapshot = controller.snapshot();
assert.equal(snapshot.canCombined, true);
assert.equal(snapshot.mode, "volume");
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], false);
assert.equal(snapshot.visibility.surfaceSources["segmentation-derived"], false);

const combined = controller.requestMode("combined");
assert.equal(combined.accepted, true);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "combined");
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], true);
assert.equal(snapshot.visibility.surfaceSources["segmentation-derived"], true);

controller.selectSurfaceSource("volume-derived", false);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "combined");
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], false);
assert.equal(snapshot.visibility.surfaceSources["segmentation-derived"], true);
assert.deepEqual(snapshot.selectedResidentSurfaceSources, ["segmentation-derived"]);

controller.selectSurfaceSource("segmentation-derived", false);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume", "Removing the final selected surface source must fall back to Volume");
assert.equal(snapshot.visibility.volume, true);
assert.equal(snapshot.canCombined, false);

controller.selectSurfaceSource("volume-derived", true);
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume", "Selecting a source must not implicitly switch visualization mode");
assert.equal(snapshot.canCombined, true);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], false);

controller.requestMode("surface");
snapshot = controller.snapshot();
assert.equal(snapshot.visibility.volume, false);
assert.equal(snapshot.visibility.surfaceSources["volume-derived"], true);

controller.requestMode("combined");
controller.setSurfaceSource("volume-derived", { resident: false });
snapshot = controller.snapshot();
assert.equal(snapshot.mode, "volume", "Combined must fail closed when its final resident source disappears");
assert.equal(snapshot.visibility.volume, true);

console.log("PHASE6D2C_COMBINED_VOLUME_PLUS_SURFACES=PASS");
console.log("PHASE6D2C_SOURCE_SELECTION_PRESENTATION_ONLY=PASS");
console.log("PHASE6D2C_LAST_SOURCE_FALLBACK=PASS");
console.log("PHASE6D2C_SOURCE_SELECTION_DOES_NOT_SWITCH_MODE=PASS");
console.log("PHASE6D2C_COMBINED_CONTROLLER_OK=YES");
