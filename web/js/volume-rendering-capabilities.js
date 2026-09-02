const DEFAULT_MAX_CLIENT_VOLUME_BYTES = 512 * 1024 * 1024;


export function qualifyVolumeRenderingCapabilities(renderer) {
  const context = renderer?.getContext?.();
  const webgl2 = typeof WebGL2RenderingContext !== "undefined"
    && context instanceof WebGL2RenderingContext;
  if (!webgl2) {
    return {
      ready: false,
      webgl2: false,
      texture3d: false,
      max3dTextureSize: 0,
      reason: "WebGL2 is required for direct patient volume rendering",
    };
  }

  const max3dTextureSize = Number(context.getParameter(context.MAX_3D_TEXTURE_SIZE)) || 0;
  return {
    ready: max3dTextureSize > 0,
    webgl2: true,
    texture3d: max3dTextureSize > 0,
    max3dTextureSize,
    reason: max3dTextureSize > 0
      ? "WebGL2 3D textures are available"
      : "The browser did not report a usable 3D texture limit",
  };
}


export function qualifyCanonicalVolumeForDevice(
  volume,
  capabilities,
  maxClientBytes = DEFAULT_MAX_CLIENT_VOLUME_BYTES,
) {
  if (!capabilities?.ready) {
    return { ready: false, reason: capabilities?.reason || "3D texture support is unavailable" };
  }
  if (!volume?.ready || !Array.isArray(volume.shape) || volume.shape.length !== 3) {
    return { ready: false, reason: "Canonical patient volume metadata is unavailable" };
  }

  const [slices, rows, columns] = volume.shape.map(Number);
  const dimensions = [columns, rows, slices];
  if (!dimensions.every((value) => Number.isInteger(value) && value > 0)) {
    return { ready: false, reason: "Canonical patient volume dimensions are invalid" };
  }
  if (dimensions.some((value) => value > capabilities.max3dTextureSize)) {
    return {
      ready: false,
      reason: `Patient volume exceeds this GPU's ${capabilities.max3dTextureSize}px 3D texture limit`,
    };
  }

  const byteLength = dimensions.reduce((total, value) => total * value, 2);
  if (!Number.isSafeInteger(byteLength) || byteLength > maxClientBytes) {
    return {
      ready: false,
      reason: "Patient volume requires an adaptive rendering representation",
    };
  }
  return { ready: true, dimensions, byteLength, reason: "Patient volume fits this GPU profile" };
}


export function validateVolumeRenderingDescriptor(descriptor, capabilities) {
  if (!descriptor?.ready || descriptor.encoding !== "linear_uint16_rg8") {
    return { ready: false, reason: "GPU volume descriptor is unavailable or unsupported" };
  }
  if (Number(descriptor.bytes_per_voxel) !== 2) {
    return { ready: false, reason: "GPU volume descriptor component layout is unsupported" };
  }
  if (!Array.isArray(descriptor.texture_dimensions) || descriptor.texture_dimensions.length !== 3) {
    return { ready: false, reason: "GPU volume descriptor dimensions are invalid" };
  }
  if (descriptor.texture_dimensions.some(
    (value) => !Number.isInteger(Number(value)) || Number(value) <= 0,
  )) {
    return { ready: false, reason: "GPU volume descriptor dimensions are invalid" };
  }
  if (descriptor.texture_dimensions.some(
    (value) => Number(value) > Number(capabilities?.max3dTextureSize || 0),
  )) {
    return { ready: false, reason: "GPU volume descriptor exceeds the browser texture limit" };
  }
  const expectedLength = descriptor.texture_dimensions
    .map(Number)
    .reduce((total, value) => total * value, Number(descriptor.bytes_per_voxel));
  if (expectedLength !== Number(descriptor.byte_length)) {
    return { ready: false, reason: "GPU volume descriptor byte length is inconsistent" };
  }
  if (!/^[0-9a-f]{64}$/.test(String(descriptor.revision || ""))) {
    return { ready: false, reason: "GPU volume descriptor revision is invalid" };
  }
  return { ready: true, reason: "GPU volume transport is qualified" };
}
