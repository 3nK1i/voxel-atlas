import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sharedSource = readFileSync(resolve(root, "web/js/reconstruction-surface-presentation.js"), "utf8");
const viewerSource = readFileSync(resolve(root, "web/js/segmentation-surface-viewer.js"), "utf8");
const panelSource = readFileSync(resolve(root, "web/js/segmentation-structure-panel.js"), "utf8");
const appSource = readFileSync(resolve(root, "web/js/app.js"), "utf8");
const asModule = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;

const shared = await import(asModule(sharedSource));
assert.match(panelSource, /structure\.colorHex\s*=\s*this\.color\.value\.toLowerCase\(\)/);
assert.match(appSource, /redrawSegmentationOverlays\(\)/);

// Test the actual viewer class with import-only, no-op dependency shims. No
// backend, DICOM data, browser, geometry generation or network request is used.
const withoutImports = viewerSource.replace(
  /^import\s*\{[\s\S]*?\}\s*from\s*"[^"]+";\s*$/gm, "",
);
assert.ok(!/^import\s/m.test(withoutImports), "Unexpected viewer import; refresh the fixture");
globalThis.__ctb1 = shared;
const shim = `
const { applySegmentationSurfaceMaterialProfile, createSegmentationSurfaceMaterial,
  getSurfacePresentationProfile } = globalThis.__ctb1;
const resolveStructureInteraction = (presentation, labelId) => ({
  effectiveSurfaceVisible: Boolean(presentation.structures.get(labelId)?.visible),
  explodedOffsetLpsMm: [0, 0, 0], clippingEnabled: true,
});
const patientLpsOffsetToViewer = () => [0, 0, 0];
const applySurfaceClippingToMaterial = () => {};
const segmentationViewerWinding = (indices) => indices;
`;
const { PatientSegmentationSurfaceLayer } = await import(asModule(shim + withoutImports));
delete globalThis.__ctb1;

class Color {
  constructor(value) { this.value = value; }
  set(value) { this.value = value; }
}
class Material {
  constructor(options) {
    Object.assign(this, options);
    this.color = new Color(options.color);
    this.emissive = new Color(options.emissive);
  }
  dispose() {}
}
const three = {
  BufferGeometry: class {},
  Mesh: class {},
  MeshStandardMaterial: Material,
  Group: class {
    constructor() { this.userData = {}; this.visible = true; }
    add() {}
    remove() {}
  },
  FrontSide: 0,
  DoubleSide: 2,
};
let renderCount = 0;
const layer = new PatientSegmentationSurfaceLayer({
  three,
  parent: { add() {} },
  fetchImpl: async () => { throw new Error("Network access is not permitted in the color test"); },
  requestRender: () => { renderCount += 1; },
});
const descriptor = (id) => ({
  ready: true, coordinate_system: "patient_lps", label_map_id: id,
  present_labels: [7],
});
layer.setDescriptor(descriptor("study-1-label-map"));
const original = { labelId: 7, colorHex: "#a1b2c3", opacity: 0.45, visible: true, surfaceVisible: true };
const presentation = { structures: new Map([[7, original]]), selectedLabelId: 7 };
layer.presentation = presentation;
layer.desiredLabels.add(7);
const material = shared.createSegmentationSurfaceMaterial(three, original, "fidelity", true);
const geometry = { dispose() {} };
const mesh = { visible: true, position: { set() {} }, userData: {} };
layer.items.set(7, { labelId: 7, material, geometry, mesh });
const previousGeometry = layer.items.get(7).geometry;
assert.equal(material.color.value, "#a1b2c3");
assert.equal(material.opacity, 0.45);

const stored = layer.set3dColorOverrides(new Map([[7, "#D8C9A5"]]));
assert.equal(stored.get(7), "#d8c9a5");
assert.equal(material.color.value, "#d8c9a5");
assert.equal(material.emissive.value, "#d8c9a5");
assert.equal(original.colorHex, "#a1b2c3", "MPR's source structure color was modified");
assert.equal(material.opacity, 0.45);
assert.equal(layer.items.get(7).geometry, previousGeometry);
stored.set(7, "#000000");
assert.equal(layer.surfaceColorOverrides.get(7), "#d8c9a5", "Caller mutated stored overrides");

layer.setPresentationProfile("presentation");
assert.equal(material.color.value, "#d8c9a5", "Lighting/profile switch lost the 3D override");
layer._updateItemPresentation(layer.items.get(7), original, 7);
assert.equal(material.color.value, "#d8c9a5", "Structure refresh lost the 3D override");
assert.equal(layer._makeMaterial(original).color.value, "#d8c9a5", "New resident surfaces lack the override");

assert.throws(() => layer.set3dColorOverrides({ 7: "#ffffff" }), TypeError);
assert.throws(() => layer.set3dColorOverrides(new Map([[7, "ivory"]])), TypeError);
assert.throws(() => layer.set3dColorOverrides(new Map([["7", "#ffffff"]])), TypeError);
assert.equal(material.color.value, "#d8c9a5", "Invalid update partially changed resident material");
layer.set3dColorOverrides(new Map());
assert.equal(material.color.value, "#a1b2c3", "Removing override did not restore original semantic color");
assert.equal(original.colorHex, "#a1b2c3");

layer.set3dColorOverrides(new Map([[7, "#d8c9a5"]]));
layer.setDescriptor(descriptor("study-2-label-map"));
assert.equal(layer.surfaceColorOverrides.size, 0, "Study change leaked presentation to another label map");
assert.equal(layer.items.size, 0, "Study change retained stale geometry");
layer.set3dColorOverrides(new Map([[7, "#d8c9a5"]]));
layer.clear();
assert.equal(layer.surfaceColorOverrides.size, 0, "Clear retained the presentation override");
assert.equal(original.colorHex, "#a1b2c3");
assert.ok(renderCount >= 4, "Resident materials did not trigger a re-render");
console.log("CTB1_3D_ONLY_COLOR_OVERRIDE=PASS");
console.log("CTB1_MPR_SHARED_COLOR_UNCHANGED=PASS");
console.log("CTB1_GEOMETRY_PRESERVED_AND_STUDY_ISOLATED=PASS");
