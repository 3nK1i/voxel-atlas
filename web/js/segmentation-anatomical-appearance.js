// CT-B2: visual-only, 3D segmentation surface colors; no changes to label catalog or MPR.
// Use the canonical structure groups, never infer anatomical identity from RGB or label number.
const ANATOMICAL_3D_COLORS = Object.freeze({
  spine: "#ded0b2",
  skeletal: "#d8c9a5",
  muscles: "#a66c62",
});

export function build3dAnatomicalColorOverrides(presentation) {
  if (!(presentation?.structures instanceof Map)) return new Map();
  const overrides = new Map();
  for (const structure of presentation.structures.values()) {
    // Costal cartilage is not bone; do not paint it as ivory.
    const supported = structure?.name !== "costal_cartilages"
      && Object.hasOwn(ANATOMICAL_3D_COLORS, structure?.groupId);
    const color = supported ? ANATOMICAL_3D_COLORS[structure.groupId] : null;
    if (color && Number.isInteger(structure.labelId) && structure.labelId > 0) {
      overrides.set(structure.labelId, color);
    }
  }
  return overrides;
}

export function resolve3dAppearanceContext(mode, descriptor, presentation) {
  if (mode !== "scientific" && mode !== "anatomical") {
    throw new RangeError("Unknown segmentation 3D color appearance");
  }
  const ready = descriptor?.ready === true
    && typeof descriptor.label_map_id === "string"
    && descriptor.label_map_id.length > 0
    && descriptor.label_map_id === presentation?.labelMapId
    && presentation?.structures instanceof Map;
  return {
    ready,
    overrides: ready && mode === "anatomical"
      ? build3dAnatomicalColorOverrides(presentation)
      : new Map(),
  };
}
