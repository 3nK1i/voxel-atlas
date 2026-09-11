import {
  resolveStructureInteraction,
} from "./segmentation-structure-interaction.js?v=phase6f-a-r1-phase6f-b-r1";

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

function rgbKey(red, green, blue) {
  return (red << 16) | (green << 8) | blue;
}

function parseColor(colorHex) {
  if (!/^#[0-9a-f]{6}$/i.test(String(colorHex))) {
    throw new Error("Segmentation presentation color is invalid");
  }
  return [
    Number.parseInt(colorHex.slice(1, 3), 16),
    Number.parseInt(colorHex.slice(3, 5), 16),
    Number.parseInt(colorHex.slice(5, 7), 16),
  ];
}

export function decodeSegmentationLabels(pixels, width, height, palette) {
  const dimensions = validateOverlayPayload(pixels, width, height);
  if (!Array.isArray(palette)) {
    throw new Error("Segmentation overlay palette is invalid");
  }
  const colors = new Map();
  for (const item of palette) {
    const labelId = Number(item?.label_id);
    const [red, green, blue] = parseColor(String(item?.color_hex || ""));
    const key = rgbKey(red, green, blue);
    if (!Number.isInteger(labelId) || labelId <= 0 || colors.has(key)) {
      throw new Error("Segmentation overlay palette is invalid");
    }
    colors.set(key, labelId);
  }
  const labels = new Uint16Array(dimensions.width * dimensions.height);
  for (let source = 0, target = 0; source < pixels.length; source += 4, target += 1) {
    if (pixels[source + 3] === 0) continue;
    const labelId = colors.get(rgbKey(pixels[source], pixels[source + 1], pixels[source + 2]));
    if (!labelId) {
      throw new Error("Segmentation overlay contains an unknown structure color");
    }
    labels[target] = labelId;
  }
  return labels;
}

export function drawSegmentationLabels(
  canvas,
  labels,
  width,
  height,
  presentation,
  opacity = 0.45,
) {
  const normalizedWidth = Number(width);
  const normalizedHeight = Number(height);
  if (
    !(labels instanceof Uint16Array)
    || !Number.isInteger(normalizedWidth)
    || !Number.isInteger(normalizedHeight)
    || normalizedWidth <= 0
    || normalizedHeight <= 0
    || labels.length !== normalizedWidth * normalizedHeight
    || !(presentation?.structures instanceof Map)
  ) {
    throw new Error("Segmentation label presentation is invalid");
  }
  const styles = new Map();
  for (const [labelId, structure] of presentation.structures.entries()) {
    const rgb = parseColor(structure.colorHex);
    const interaction = resolveStructureInteraction(presentation, labelId);
    styles.set(Number(labelId), {
      rgb,
      alpha: interaction.effectiveVisible
        ? Math.round(255 * Math.min(1, Math.max(0, Number(interaction.opacity))))
        : 0,
    });
  }
  canvas.width = normalizedWidth;
  canvas.height = normalizedHeight;
  canvas.style.opacity = String(Math.min(1, Math.max(0, Number(opacity) || 0)));
  canvas.hidden = false;
  const context = canvas.getContext("2d", { alpha: true });
  const image = context.createImageData(normalizedWidth, normalizedHeight);
  for (let source = 0, target = 0; source < labels.length; source += 1, target += 4) {
    const style = styles.get(labels[source]);
    if (!style || style.alpha === 0) continue;
    image.data[target] = style.rgb[0];
    image.data[target + 1] = style.rgb[1];
    image.data[target + 2] = style.rgb[2];
    image.data[target + 3] = style.alpha;
  }
  context.putImageData(image, 0, 0);
}

export function clearSegmentationOverlay(canvas) {
  const context = canvas.getContext("2d", { alpha: true });
  context.clearRect(0, 0, canvas.width, canvas.height);
  canvas.hidden = true;
}
