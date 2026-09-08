export const SEGMENTATION_OVERLAY_MEDIA_TYPE = "application/x-voxelatlas-rgba8";

export function validateOverlayPayload(buffer, width, height) {
  const normalizedWidth = Number(width);
  const normalizedHeight = Number(height);
  if (
    !(buffer instanceof Uint8Array)
    || !Number.isInteger(normalizedWidth)
    || !Number.isInteger(normalizedHeight)
    || normalizedWidth <= 0
    || normalizedHeight <= 0
    || buffer.length !== normalizedWidth * normalizedHeight * 4
  ) {
    throw new Error("Segmentation overlay payload is invalid");
  }
  return { width: normalizedWidth, height: normalizedHeight };
}

export function drawSegmentationRgba(canvas, pixels, width, height, opacity = 0.45) {
  const dimensions = validateOverlayPayload(pixels, width, height);
  const normalizedOpacity = Math.min(1, Math.max(0, Number(opacity) || 0));
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;
  canvas.style.opacity = String(normalizedOpacity);
  canvas.hidden = false;
  const context = canvas.getContext("2d", { alpha: true });
  const image = context.createImageData(dimensions.width, dimensions.height);
  image.data.set(pixels);
  context.putImageData(image, 0, 0);
}

export function clearSegmentationOverlay(canvas) {
  const context = canvas.getContext("2d", { alpha: true });
  context.clearRect(0, 0, canvas.width, canvas.height);
  canvas.hidden = true;
}
