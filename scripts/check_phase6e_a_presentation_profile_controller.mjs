import assert from "node:assert/strict";
import {
  ReconstructionPresentationProfileController,
  listReconstructionPresentationProfiles,
} from "../web/js/reconstruction-presentation-profile.js";
import {
  ReconstructionVisualizationModeController,
} from "../web/js/reconstruction-visualization-mode.js";

const profiles = listReconstructionPresentationProfiles();
assert.deepEqual(profiles.map((entry) => entry.id), ["fidelity", "presentation"]);
assert.deepEqual(profiles.map((entry) => entry.label), ["Fidelity", "Presentation"]);

const changes = [];
const controller = new ReconstructionPresentationProfileController({
  onChange: (snapshot, reason) => changes.push({ snapshot, reason }),
});

let snapshot = controller.snapshot();
assert.equal(snapshot.profile, "fidelity");
assert.equal(snapshot.intent, "restrained");
assert.equal(changes.length, 0);

const modeController = new ReconstructionVisualizationModeController();
modeController.setVolumeAvailable(true);
modeController.setSurfaceSource("volume-derived", { available: true, resident: true, selected: true });
assert.equal(modeController.requestMode("combined").accepted, true);
const beforeMode = modeController.snapshot();

const accepted = controller.requestProfile("presentation");
assert.equal(accepted.accepted, true);
assert.equal(accepted.reason, "accepted");
snapshot = controller.snapshot();
assert.equal(snapshot.profile, "presentation");
assert.equal(snapshot.intent, "polished");
assert.equal(changes.length, 1);
assert.equal(changes[0].reason, "profile-request");
assert.deepEqual(modeController.snapshot(), beforeMode);

const unchanged = controller.requestProfile("presentation");
assert.equal(unchanged.accepted, true);
assert.equal(unchanged.reason, "unchanged");
assert.equal(changes.length, 1);

controller.reset();
snapshot = controller.snapshot();
assert.equal(snapshot.profile, "fidelity");
assert.equal(changes.at(-1).reason, "reset");

assert.throws(() => controller.requestProfile("diagnostic"), /Unknown reconstruction presentation profile/);

console.log("PHASE6E_A_PROFILE_CATALOG=PASS");
console.log("PHASE6E_A_DEFAULT_FIDELITY=PASS");
console.log("PHASE6E_A_MODE_SOURCE_STATE_INDEPENDENT=PASS");
console.log("PHASE6E_A_DETERMINISTIC_RESET=PASS");
console.log("PHASE6E_A_CONTROLLER_OK=YES");
