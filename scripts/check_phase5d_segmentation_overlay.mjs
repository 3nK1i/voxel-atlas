import assert from "node:assert/strict";
import {
  clearSegmentationOverlay,
  drawSegmentationRgba,
  SEGMENTATION_OVERLAY_MEDIA_TYPE,
  validateOverlayPayload,
} from "../web/js/segmentation-overlay.js";


assert.equal(SEGMENTATION_OVERLAY_MEDIA_TYPE, "application/x-voxelatlas-rgba8");
const pixels = new Uint8Array([0, 0, 0, 0, 255, 80, 40, 255]);
assert.deepEqual(validateOverlayPayload(pixels, 2, 1), { width: 2, height: 1 });
assert.throws(
  () => validateOverlayPayload(new Uint8Array(7), 2, 1),
  /payload is invalid/,
);

let stored = null;
let cleared = false;
const context = {
  createImageData(width, height) {
    return { data: new Uint8ClampedArray(width * height * 4) };
  },
  putImageData(image) {
    stored = image.data;
  },
  clearRect() {
    cleared = true;
  },
};
const canvas = {
  width: 0,
  height: 0,
  hidden: true,
  style: {},
  getContext() {
    return context;
  },
};

drawSegmentationRgba(canvas, pixels, 2, 1, 0.45);
assert.equal(canvas.width, 2);
assert.equal(canvas.height, 1);
assert.equal(canvas.hidden, false);
assert.equal(canvas.style.opacity, "0.45");
assert.deepEqual(Array.from(stored), Array.from(pixels));

clearSegmentationOverlay(canvas);
assert.equal(cleared, true);
assert.equal(canvas.hidden, true);

console.log("PHASE5D_BROWSER_OVERLAY_CONTRACT=PASS");
console.log("RGBA_LENGTH_VALIDATION=PASS");
console.log("OPACITY_COMPOSITING=PASS");
console.log("TRANSPARENT_CLEAR=PASS");
