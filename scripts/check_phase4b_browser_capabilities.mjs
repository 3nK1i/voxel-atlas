#!/usr/bin/env node
import {
  qualifyCanonicalVolumeForDevice,
  qualifyVolumeRenderingCapabilities,
  validateVolumeRenderingDescriptor,
} from "../web/js/volume-rendering-capabilities.js";


globalThis.WebGL2RenderingContext = class WebGL2RenderingContext {
  constructor(maximum3dTextureSize) {
    this.MAX_3D_TEXTURE_SIZE = 0x8073;
    this.maximum3dTextureSize = maximum3dTextureSize;
  }

  getParameter(parameter) {
    return parameter === this.MAX_3D_TEXTURE_SIZE ? this.maximum3dTextureSize : null;
  }
};

const context = new globalThis.WebGL2RenderingContext(2048);
const capabilities = qualifyVolumeRenderingCapabilities({ getContext: () => context });
const source = qualifyCanonicalVolumeForDevice(
  { ready: true, shape: [112, 512, 574] },
  capabilities,
);
const descriptor = validateVolumeRenderingDescriptor(
  {
    ready: true,
    revision: "a".repeat(64),
    encoding: "linear_uint16_rg8",
    texture_dimensions: [574, 512, 112],
    bytes_per_voxel: 2,
    byte_length: 574 * 512 * 112 * 2,
  },
  capabilities,
);
const oversized = qualifyCanonicalVolumeForDevice(
  { ready: true, shape: [112, 512, 4096] },
  capabilities,
);
const unsupportedLayout = validateVolumeRenderingDescriptor(
  {
    ready: true,
    revision: "b".repeat(64),
    encoding: "linear_uint16_rg8",
    texture_dimensions: [574, 512, 112],
    bytes_per_voxel: 4,
    byte_length: 574 * 512 * 112 * 4,
  },
  capabilities,
);

if (
  !capabilities.ready
  || capabilities.max3dTextureSize !== 2048
  || !source.ready
  || !descriptor.ready
  || oversized.ready
  || unsupportedLayout.ready
) {
  console.error("PHASE4B_BROWSER_CAPABILITIES=FAIL");
  console.error(JSON.stringify({
    capabilities,
    source,
    descriptor,
    oversized,
    unsupportedLayout,
  }, null, 2));
  process.exit(1);
}

console.log("PHASE4B_BROWSER_CAPABILITIES=PASS");
