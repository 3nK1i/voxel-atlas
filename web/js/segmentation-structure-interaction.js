export const STRUCTURE_INTERACTION_SCHEMA_VERSION = 1;

function finiteNumber(value, fallback = 0) {
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : fallback;
}

function clampOpacity(value) {
  return Math.min(1, Math.max(0, finiteNumber(value, 1)));
}

function normalizeExplodedOffset(value) {
  if (!Array.isArray(value) || value.length !== 3) return [0, 0, 0];
  return value.map((component) => finiteNumber(component, 0));
}

function requirePresentation(presentation) {
  if (!(presentation?.structures instanceof Map)) {
    throw new Error("Segmentation structure interaction presentation is invalid");
  }
  return presentation;
}

export function createStructureInteractionState() {
  return {
    schemaVersion: STRUCTURE_INTERACTION_SCHEMA_VERSION,
    isolatedLabelId: null,
  };
}

export function createStructureInteractionDefaults() {
  return {
    clippingEnabled: true,
    explodedOffsetLpsMm: [0, 0, 0],
  };
}

export function resetStructureInteractionState(presentation) {
  requirePresentation(presentation);
  presentation.interaction = createStructureInteractionState();
  for (const structure of presentation.structures.values()) {
    const defaults = createStructureInteractionDefaults();
    structure.clippingEnabled = defaults.clippingEnabled;
    structure.explodedOffsetLpsMm = defaults.explodedOffsetLpsMm;
  }
  return presentation.interaction;
}

export function activateStructureIsolation(presentation, labelId) {
  requirePresentation(presentation);
  const normalizedLabelId = Number(labelId);
  if (!Number.isInteger(normalizedLabelId) || !presentation.structures.has(normalizedLabelId)) {
    throw new Error("Segmentation structure interaction selection is invalid");
  }
  if (!presentation.interaction || presentation.interaction.schemaVersion !== STRUCTURE_INTERACTION_SCHEMA_VERSION) {
    presentation.interaction = createStructureInteractionState();
  }
  presentation.interaction.isolatedLabelId = normalizedLabelId;
  return normalizedLabelId;
}

export function restoreStructureIsolation(presentation) {
  requirePresentation(presentation);
  if (!presentation.interaction || presentation.interaction.schemaVersion !== STRUCTURE_INTERACTION_SCHEMA_VERSION) {
    presentation.interaction = createStructureInteractionState();
    return null;
  }
  const previous = presentation.interaction.isolatedLabelId;
  presentation.interaction.isolatedLabelId = null;
  return Number.isInteger(previous) ? previous : null;
}

export function resolveStructureInteraction(presentation, labelId) {
  requirePresentation(presentation);
  const normalizedLabelId = Number(labelId);
  const structure = presentation.structures.get(normalizedLabelId);
  if (!structure) {
    throw new Error("Segmentation structure interaction selection is invalid");
  }

  const rawIsolation = presentation.interaction?.isolatedLabelId;
  const isolationActive = Number.isInteger(rawIsolation)
    && presentation.structures.has(rawIsolation);
  const isolated = isolationActive && rawIsolation === normalizedLabelId;
  const userVisible = Boolean(structure.visible);
  const effectiveVisible = isolationActive ? isolated : userVisible;
  const surfaceRequested = structure.surfaceVisible === true;

  return Object.freeze({
    labelId: normalizedLabelId,
    groupId: String(structure.groupId || ""),
    userVisible,
    surfaceRequested,
    isolated,
    effectiveVisible,
    effectiveSurfaceVisible: effectiveVisible && surfaceRequested,
    opacity: clampOpacity(structure.opacity),
    clippingEnabled: structure.clippingEnabled !== false,
    explodedOffsetLpsMm: Object.freeze(normalizeExplodedOffset(structure.explodedOffsetLpsMm)),
  });
}
