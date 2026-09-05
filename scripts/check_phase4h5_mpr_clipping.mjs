#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { projectMprClipping, renderMprClippingOverlay } from "../web/js/mpr-clipping-overlay.js";

const planes = {
  axial: { normal_axis: "z", horizontal_axis: "x", vertical_axis: "y", vertical_reverse: false },
  coronal: { normal_axis: "y", horizontal_axis: "x", vertical_axis: "z", vertical_reverse: true },
  sagittal: { normal_axis: "x", horizontal_axis: "y", vertical_axis: "z", vertical_reverse: true },
};
const ranges = { x: [-100, 100], y: [-150, 50], z: [-60, 140] };
for (const p of Object.values(planes)) {
  p.horizontal_range_mm = ranges[p.horizontal_axis];
  p.vertical_range_mm = ranges[p.vertical_axis];
}
const request = {
  axial: { enabled: true, minimumLpsMm: -20, maximumLpsMm: 80 },
  coronal: { enabled: true, minimumLpsMm: -110, maximumLpsMm: 10 },
  sagittal: { enabled: true, minimumLpsMm: -50, maximumLpsMm: 60 },
};
const original = JSON.stringify({ planes, request });
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
const area = (g) => g.rectangles.reduce((s, r) => s + r.width * r.height, 0);

for (const [name, p] of Object.entries(planes)) {
  const g = projectMprClipping(p, request, 0);
  assert.equal(g.active, true, name);
  assert.equal(g.outside, false, name);
  assert.equal(g.lines.length, 4, name);
  assert.equal(g.rectangles.length, 4, name);
  for (const r of g.rectangles) {
    assert.ok(r.x >= 0 && r.y >= 0 && r.x + r.width <= 1.000001 && r.y + r.height <= 1.000001);
  }
}
const axial = projectMprClipping(planes.axial, request, 0);
near(axial.lines[0].x1, 0.25);
near(axial.lines[1].x1, 0.8);
near(axial.lines[2].y1, 0.2);
near(axial.lines[3].y1, 0.8);
near(area(axial), 1 - 0.55 * 0.6);
const coronal = projectMprClipping(planes.coronal, request, 0);
near(coronal.lines[2].y1, 0.3); // Superior boundary at top; Z reversed.
near(coronal.lines[3].y1, 0.8);
const sagittal = projectMprClipping(planes.sagittal, request, 0);
near(sagittal.lines[0].x1, 0.2); // Anterior (-Y) is left on sagittal.
near(sagittal.lines[1].x1, 0.8);

assert.equal(projectMprClipping(planes.axial, {}, 0).active, false);
assert.equal(projectMprClipping(planes.axial, request, -20).outside, false);
assert.equal(projectMprClipping(planes.axial, request, 80).outside, false);
const outside = projectMprClipping(planes.axial, request, 80.01);
assert.equal(outside.outside, true);
near(area(outside), 1);
assert.equal(outside.lines.length, 0);
const full = { sagittal: { enabled: true, minimumLpsMm: -100, maximumLpsMm: 100 } };
near(area(projectMprClipping(planes.axial, full, 0)), 0);
assert.equal(projectMprClipping(planes.axial, { sagittal: { ...full.sagittal, enabled: false } }, 0).active, false);
const invalid = { axial: { enabled: true, minimumLpsMm: NaN, maximumLpsMm: 4 } };
assert.equal(projectMprClipping(planes.axial, invalid, 0).active, false);
assert.equal(projectMprClipping(null, request, 0).active, false);
assert.equal(projectMprClipping(planes.axial, request, NaN).active, false);
const degenerate = { ...planes.axial, horizontal_range_mm: [0, 0] };
assert.equal(projectMprClipping(degenerate, request, 0).active, false);
assert.equal(JSON.stringify({ planes, request }), original, "input geometry must not change");

// Exercise actual app glue, not a duplicate of its geometry calculations.
const app = readFileSync(new URL("../web/js/app.js", import.meta.url), "utf8");
function extract(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  const end = app.indexOf("\nfunction ", start + 1);
  return app.slice(start, end);
}
const calls = [];
const entry = { surface: {}, renderedPlaneDescriptor: planes.axial, renderedPositionLpsMm: 80.01 };
const state = { mpr: { descriptor: { planes }, crosshairLpsMm: [0, 0, 0] } };
const context = vm.createContext({
  state, mprRegistry: new Map([["axial", entry]]),
  mprClippingOverlayToggle: { checked: true },
  clippingRequest: () => request, projectMprClipping,
  renderMprClippingOverlay: (surface, g) => calls.push(g),
});
vm.runInContext(extract("updateMprClippingOverlays"), context);
vm.runInContext("updateMprClippingOverlays()", context);
assert.equal(calls.at(-1).outside, true, "use displayed slice, not continuous crosshair");
context.mprClippingOverlayToggle.checked = false;
vm.runInContext("updateMprClippingOverlays()", context);
assert.equal(calls.at(-1), null);
context.mprClippingOverlayToggle.checked = true;
entry.renderedPlaneDescriptor = { ...planes.axial };
vm.runInContext("updateMprClippingOverlays()", context);
assert.equal(calls.at(-1), null, "hide stale study overlay");
state.mpr.descriptor = null;
vm.runInContext("updateMprClippingOverlays()", context);
assert.equal(calls.at(-1), null);
assert.deepEqual(state.mpr.crosshairLpsMm, [0, 0, 0]);

// DOM lifecycle: fixed-size node pool, no image-canvas access, hidden reset.
class Element {
  constructor() { this.attrs = {}; this.children = []; this.style = {}; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  append(...items) { this.children.push(...items); }
}
const doc = { createElement: () => new Element(), createElementNS: () => new Element() };
const surface = new Element(); surface.ownerDocument = doc;
renderMprClippingOverlay(surface, axial);
const nodes = surface.children.slice();
assert.equal(nodes.length, 2);
assert.equal(nodes[0].children.length, 8);
for (let n = 0; n < 1000; n++) renderMprClippingOverlay(surface, coronal);
assert.deepEqual(surface.children, nodes);
renderMprClippingOverlay(surface, outside);
assert.equal(nodes[1].hidden, false);
renderMprClippingOverlay(surface, null);
assert.equal(nodes[0].style.display, "none");
assert.equal(nodes[1].hidden, true);
console.log("PHASE4H5_MPR_CLIPPING_PROBE_OK=YES");
