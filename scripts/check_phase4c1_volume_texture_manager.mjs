#!/usr/bin/env node
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";

import {
  PatientVolumeTextureManager,
  VolumeTextureLoadError,
} from "../web/js/volume-texture-manager.js";


class FakeData3DTexture {
  constructor(data, width, height, depth) {
    this.image = { data, width, height, depth };
    this.disposeCount = 0;
  }

  dispose() {
    this.disposeCount += 1;
  }
}


const THREE = {
  Data3DTexture: FakeData3DTexture,
  RGFormat: "RGFormat",
  UnsignedByteType: "UnsignedByteType",
  NearestFilter: "NearestFilter",
  ClampToEdgeWrapping: "ClampToEdgeWrapping",
  NoColorSpace: "NoColorSpace",
};

const bytes = new Uint8Array([0, 0, 255, 0, 0, 1, 255, 255]);
const digest = await webcrypto.subtle.digest("SHA-256", bytes);
const artifactSha256 = Array.from(new Uint8Array(digest), (value) => (
  value.toString(16).padStart(2, "0")
)).join("");
const revision = "a".repeat(64);
const descriptor = {
  ready: true,
  revision,
  artifact_sha256: artifactSha256,
  encoding: "linear_uint16_rg8",
  component_type: "uint8",
  component_order: ["low_byte", "high_byte"],
  bytes_per_voxel: 2,
  byte_length: bytes.byteLength,
  texture_dimensions: [2, 2, 1],
};

function binaryResponse(data = bytes, headers = {}) {
  return new Response(data, {
    status: 200,
    headers: {
      "Cache-Control": "no-store",
      "Content-Length": String(data.byteLength),
      "Content-Type": "application/x-voxelatlas-volume-rg8",
      "X-Content-Type-Options": "nosniff",
      "X-VoxelAtlas-Volume-Revision": revision,
      "X-VoxelAtlas-Volume-SHA256": artifactSha256,
      ...headers,
    },
  });
}

const requests = [];
let initialized = 0;
const manager = new PatientVolumeTextureManager({
  three: THREE,
  cryptoImpl: webcrypto,
  fetchImpl: async function receiverSensitiveFetch(url, options) {
    assert.equal(this, globalThis);
    requests.push({ url, options });
    return binaryResponse();
  },
  initializeTexture: (texture) => {
    assert.ok(texture instanceof FakeData3DTexture);
    initialized += 1;
  },
});

const first = await manager.load(descriptor);
assert.equal(
  requests[0].url,
  `/api/studies/latest/volume-rendering/data?revision=${revision}`,
);
assert.equal(requests[0].options.credentials, "same-origin");
assert.equal(requests[0].options.cache, "no-store");
assert.equal(first.texture.image.width, 2);
assert.equal(first.texture.image.height, 2);
assert.equal(first.texture.image.depth, 1);
assert.deepEqual(first.texture.image.data, bytes);
assert.equal(first.texture.format, THREE.RGFormat);
assert.equal(first.texture.type, THREE.UnsignedByteType);
assert.equal(first.texture.internalFormat, "RG8");
assert.equal(first.texture.minFilter, THREE.NearestFilter);
assert.equal(first.texture.magFilter, THREE.NearestFilter);
assert.equal(first.texture.generateMipmaps, false);
assert.equal(first.texture.unpackAlignment, 1);
assert.equal(first.texture.needsUpdate, true);
assert.equal(initialized, 1);
assert.equal(manager.current, first);

const second = await manager.load(descriptor);
assert.equal(first.texture.disposeCount, 1);
assert.equal(manager.current, second);
manager.dispose();
assert.equal(second.texture.disposeCount, 1);
assert.equal(manager.current, null);

const tampered = new Uint8Array(bytes);
tampered[0] = 1;
const integrityManager = new PatientVolumeTextureManager({
  three: THREE,
  cryptoImpl: webcrypto,
  fetchImpl: async () => binaryResponse(tampered),
});
await assert.rejects(
  integrityManager.load(descriptor),
  (error) => error instanceof VolumeTextureLoadError && /SHA256/i.test(error.message),
);
assert.equal(integrityManager.current, null);

const headerManager = new PatientVolumeTextureManager({
  three: THREE,
  cryptoImpl: webcrypto,
  fetchImpl: async () => binaryResponse(bytes, {
    "X-VoxelAtlas-Volume-Revision": "b".repeat(64),
  }),
});
await assert.rejects(
  headerManager.load(descriptor),
  (error) => error instanceof VolumeTextureLoadError && /revision/i.test(error.message),
);

let failedTexture = null;
const initializationManager = new PatientVolumeTextureManager({
  three: THREE,
  cryptoImpl: webcrypto,
  fetchImpl: async () => binaryResponse(),
  initializeTexture: (texture) => {
    failedTexture = texture;
    throw new Error("synthetic GPU initialization failure");
  },
});
await assert.rejects(
  initializationManager.load(descriptor),
  (error) => error instanceof VolumeTextureLoadError,
);
assert.equal(failedTexture.disposeCount, 1);
assert.equal(initializationManager.current, null);

let observedSignal = null;
const abortManager = new PatientVolumeTextureManager({
  three: THREE,
  cryptoImpl: webcrypto,
  fetchImpl: async (_url, options) => {
    observedSignal = options.signal;
    return new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        reject(new DOMException("Aborted", "AbortError"));
      }, { once: true });
    });
  },
});
const pending = abortManager.load(descriptor);
await Promise.resolve();
abortManager.dispose();
await assert.rejects(pending, (error) => error.name === "AbortError");
assert.equal(observedSignal.aborted, true);

console.log("PHASE4C1_VOLUME_TEXTURE_MANAGER=PASS");
