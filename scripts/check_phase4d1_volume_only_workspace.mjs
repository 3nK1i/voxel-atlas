#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";


const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const app = readFileSync(new URL("../web/js/app.js", import.meta.url), "utf8");

assert.equal((html.match(/data-layer=/g) || []).length, 1);
assert.match(
  html,
  /id="volumeLayerButton"[^>]*class="layer-button is-active"[^>]*data-layer="volume"[^>]*disabled[^>]*aria-pressed="true"/,
);

for (const forbidden of [
  'data-layer="skull"',
  'data-layer="brain"',
  'data-layer="combined"',
  "data-future-layer=",
  "surfaceStatusRow",
  "GLTFLoader",
  "SKULL_URL",
  "loadSkull",
  "prepareSkull",
  "MeshPhysicalMaterial",
  "/assets/models/",
  "Demo anatomy",
  "Demo skull",
]) {
  assert.ok(!`${html}\n${app}`.includes(forbidden), `retired runtime marker: ${forbidden}`);
}

for (const required of [
  "const volumeLayer =",
  "setVolumeAvailability(false)",
  "setVolumeAvailability(true)",
  "PatientVolumeRayMarcher",
  "volumeRayMarcher.create",
  "volumeRayMarcher.setOpacity",
  "volumeRayMarcher.dispose",
  "Patient scan - Full Volume",
  "Synchronized MPR remains available.",
]) {
  assert.ok(`${html}\n${app}`.includes(required), `missing volume-only marker: ${required}`);
}

console.log("PHASE4D1_VOLUME_ONLY_WORKSPACE=PASS");
