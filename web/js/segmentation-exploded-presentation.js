export const MAX_ANATOMICAL_GROUP_EXPLODE_MM = 40;
const GOLDEN_ANGLE_RADIANS = Math.PI * (3 - Math.sqrt(5));

function finite(value, fallback = 0) {
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : fallback;
}

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, finite(value, minimum)));
}

function normalizeOffset(value) {
  if (!Array.isArray(value) || value.length !== 3) return [0, 0, 0];
  return value.map((component) => {
    const normalized = finite(component, 0);
    return Math.abs(normalized) < 1e-12 ? 0 : normalized;
  });
}

function requirePresentation(presentation) {
  if (!(presentation?.structures instanceof Map) || !Array.isArray(presentation?.groups)) {
    throw new TypeError("Segmentation anatomical group presentation is invalid");
  }
  return presentation;
}

function orderedGroupIds(presentation) {
  const seen = new Set();
  const result = [];
  for (const group of presentation.groups) {
    const groupId = String(group?.groupId || "").trim();
    if (!groupId || seen.has(groupId)) continue;
    seen.add(groupId);
    result.push(groupId);
  }
  for (const structure of presentation.structures.values()) {
    const groupId = String(structure?.groupId || "other").trim() || "other";
    if (seen.has(groupId)) continue;
    seen.add(groupId);
    result.push(groupId);
  }
  return result;
}

function groupDirection(index, count) {
  if (count <= 1) return [1, 0, 0];
  const z = 1 - (2 * (index + 0.5)) / count;
  const radius = Math.sqrt(Math.max(0, 1 - z * z));
  const angle = GOLDEN_ANGLE_RADIANS * index;
  return [
    radius * Math.cos(angle),
    radius * Math.sin(angle),
    z,
  ];
}

export function resolveAnatomicalGroupExplosion(presentation, requestedMm) {
  requirePresentation(presentation);
  const amountMm = clamp(requestedMm, 0, MAX_ANATOMICAL_GROUP_EXPLODE_MM);
  const groupIds = orderedGroupIds(presentation);
  const directions = new Map(
    groupIds.map((groupId, index) => [groupId, groupDirection(index, groupIds.length)]),
  );
  const offsets = new Map();
  for (const structure of presentation.structures.values()) {
    const groupId = String(structure?.groupId || "other").trim() || "other";
    const direction = directions.get(groupId) || [1, 0, 0];
    offsets.set(
      Number(structure.labelId),
      direction.map((component) => component * amountMm),
    );
  }
  return Object.freeze({
    amountMm,
    maximumMm: MAX_ANATOMICAL_GROUP_EXPLODE_MM,
    groupCount: groupIds.length,
    groupIds: Object.freeze([...groupIds]),
    offsets,
  });
}

export function applyAnatomicalGroupExplosion(presentation, requestedMm) {
  requirePresentation(presentation);
  const plan = resolveAnatomicalGroupExplosion(presentation, requestedMm);
  presentation.explodedSeparationMm = plan.amountMm;
  for (const structure of presentation.structures.values()) {
    structure.explodedOffsetLpsMm = normalizeOffset(plan.offsets.get(structure.labelId));
  }
  return plan;
}

export function resetAnatomicalGroupExplosion(presentation) {
  return applyAnatomicalGroupExplosion(presentation, 0);
}

export function patientLpsOffsetToViewer(offsetLpsMm, volumePresentation) {
  const offset = normalizeOffset(offsetLpsMm);
  const maximumExtentMm = Number(volumePresentation?.maximumExtentMm);
  if (!Number.isFinite(maximumExtentMm) || maximumExtentMm <= 0) {
    return Object.freeze([0, 0, 0]);
  }
  const scale = 2 / maximumExtentMm;
  return Object.freeze([
    offset[0] === 0 ? 0 : -scale * offset[0],
    offset[2] === 0 ? 0 : scale * offset[2],
    offset[1] === 0 ? 0 : -scale * offset[1],
  ]);
}
