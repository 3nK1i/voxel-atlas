/**
 * Non-destructive visibility of conservative, non-anatomical CT triangle regions.
 * The mesh's vertex positions/normals and its original triangle index order stay
 * resident.  Display subsets are written into the *same* fixed-size GPU index
 * attribute; drawRange controls how many complete faces may be drawn.
 *
 * Labels are tied to a verified, exact surface ID by the caller.  No rank is
 * automatically assumed to represent the patient or an acquisition support.
 */
export function createDirectCtRegionVisibility(geometry, faceRegions) {
  const attribute = geometry?.index;
  const indices = attribute?.array;
  if (!(indices instanceof Uint32Array) || indices.length === 0 || indices.length % 3 !== 0
      || typeof geometry.setDrawRange !== "function"
      || !(faceRegions instanceof Uint8Array)
      || faceRegions.length !== indices.length / 3) {
    throw new TypeError("Direct CT region visibility requires a complete indexed mesh and matching face labels");
  }
  const counts = [0, 0, 0];
  for (const label of faceRegions) {
    if (label > 2) throw new TypeError("Direct CT face-region labels must be 0, 1, or 2");
    counts[label] += 1;
  }
  const complete = new Uint32Array(indices);
  const labels = new Uint8Array(faceRegions);
  const available = counts[1] > 0 && counts[2] > 0;
  let currentMode = "all";

  function show(mode) {
    if (!["all", "hide-region-1", "hide-region-2"].includes(mode)) {
      throw new TypeError("Unknown Direct CT region display mode");
    }
    if (mode !== "all" && !available) {
      throw new Error("Two distinct ranked regions are required for region visibility control");
    }
    // Fail closed if another feature has replaced this geometry/index buffer.
    if (geometry.index !== attribute || attribute.array !== indices || indices.length !== complete.length) {
      throw new Error("Direct CT geometry changed after region binding");
    }
    if (mode === "all") {
      indices.set(complete);
      geometry.setDrawRange(0, complete.length);
    } else {
      const hidden = mode === "hide-region-1" ? 1 : 2;
      let write = 0;
      for (let face = 0; face < labels.length; face += 1) {
        // Unresolved label 0 and all other components ALWAYS remain visible.
        if (labels[face] === hidden) continue;
        const offset = face * 3;
        indices[write++] = complete[offset];
        indices[write++] = complete[offset + 1];
        indices[write++] = complete[offset + 2];
      }
      geometry.setDrawRange(0, write);
    }
    attribute.needsUpdate = true;
    currentMode = mode;
    return Object.freeze({ mode, visibleTriangles: geometry.drawRange.count / 3 });
  }

  // Initial state is always the COMPLETE mesh, with all regions visible.
  geometry.setDrawRange(0, complete.length);
  return Object.freeze({
    available,
    faceCounts: Object.freeze([...counts]),
    get mode() { return currentMode; },
    show,
  });
}
