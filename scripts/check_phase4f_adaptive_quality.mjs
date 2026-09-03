#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  AdaptiveVolumeRenderingQuality,
  createAdaptiveRenderingProfile,
} from "../web/js/volume-rendering-quality.js";


function descriptor(dimensions) {
  return { ready: true, texture_dimensions: dimensions };
}

const representativeHead = createAdaptiveRenderingProfile(
  descriptor([574, 512, 112]),
  { ready: true, max3dTextureSize: 2048 },
  2,
);
assert.equal(representativeHead.workload, "light");
assert.equal(representativeHead.voxelCount, 574 * 512 * 112);
assert.ok(representativeHead.settledSamplingRate > representativeHead.interactiveSamplingRate);
assert.ok(representativeHead.settledPixelRatio > representativeHead.interactivePixelRatio);

const representativeBody = createAdaptiveRenderingProfile(
  descriptor([512, 512, 512]),
  { ready: true, max3dTextureSize: 2048 },
  2,
);
assert.equal(representativeBody.workload, "balanced");
assert.ok(representativeBody.settledSamplingRate <= representativeHead.settledSamplingRate);

const largeVolume = createAdaptiveRenderingProfile(
  descriptor([768, 768, 512]),
  { ready: true, max3dTextureSize: 2048 },
  2,
);
assert.equal(largeVolume.workload, "heavy");
assert.ok(largeVolume.interactiveSamplingRate < representativeBody.interactiveSamplingRate);
assert.ok(largeVolume.settledPixelRatio <= representativeBody.settledPixelRatio);

let now = 1000;
const samplingRates = [];
const pixelRatios = [];
let renderRequests = 0;
const rayMarcher = {
  current: {},
  setSamplingRate(value) { samplingRates.push(value); return value; },
};
const renderer = {
  ratio: 2,
  getPixelRatio() { return this.ratio; },
  setPixelRatio(value) { this.ratio = value; pixelRatios.push(value); },
};
const controller = new AdaptiveVolumeRenderingQuality({
  renderer,
  rayMarcher,
  devicePixelRatio: 2,
  now: () => now,
  requestRender: () => { renderRequests += 1; },
});

const activated = controller.activate(
  descriptor([574, 512, 112]),
  { ready: true, max3dTextureSize: 2048 },
);
assert.equal(activated.mode, "settled");
assert.equal(samplingRates.at(-1), representativeHead.settledSamplingRate);

controller.beginInteraction("orbit");
assert.equal(controller.snapshot().mode, "interactive");
assert.equal(samplingRates.at(-1), representativeHead.interactiveSamplingRate);
assert.equal(pixelRatios.at(-1), representativeHead.interactivePixelRatio);

controller.endInteraction("orbit");
now += representativeHead.settleDelayMs - 1;
assert.equal(controller.update(now), false);
assert.equal(controller.snapshot().mode, "interactive");
now += 1;
assert.equal(controller.update(now), true);
assert.equal(controller.snapshot().mode, "settled");
assert.equal(samplingRates.at(-1), representativeHead.settledSamplingRate);
assert.equal(pixelRatios.at(-1), representativeHead.settledPixelRatio);

controller.beginInteraction("clipping");
const initialInteractiveRate = controller.snapshot().samplingRate;
for (let index = 0; index < 12; index += 1) {
  controller.recordFrameDuration(55);
}
assert.ok(controller.snapshot().samplingRate < initialInteractiveRate);
const backedOffInteractiveRate = controller.snapshot().samplingRate;
assert.ok(
  controller.snapshot().samplingRate
    >= representativeHead.minimumInteractiveSamplingRate,
);

controller.endInteraction("clipping");
now += representativeHead.settleDelayMs;
controller.update(now);
assert.equal(controller.snapshot().samplingRate, representativeHead.settledSamplingRate);
assert.ok(renderRequests > 0);

console.log(`HEAD_WORKLOAD=${representativeHead.workload}`);
console.log(`HEAD_SAMPLING_SETTLED=${representativeHead.settledSamplingRate}`);
console.log(`HEAD_SAMPLING_INTERACTIVE=${representativeHead.interactiveSamplingRate}`);
console.log(`BODY_WORKLOAD=${representativeBody.workload}`);
console.log(`BODY_SAMPLING_SETTLED=${representativeBody.settledSamplingRate}`);
console.log(`BODY_SAMPLING_INTERACTIVE=${representativeBody.interactiveSamplingRate}`);
console.log(`LARGE_WORKLOAD=${largeVolume.workload}`);
console.log(`LARGE_SAMPLING_SETTLED=${largeVolume.settledSamplingRate}`);
console.log(`LARGE_SAMPLING_INTERACTIVE=${largeVolume.interactiveSamplingRate}`);
console.log(`FRAME_PRESSURE_BACKOFF=${initialInteractiveRate}->${backedOffInteractiveRate}`);
console.log("PHASE4F_ADAPTIVE_RENDERING_QUALITY=PASS");
