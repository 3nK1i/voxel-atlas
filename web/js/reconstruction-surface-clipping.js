const SURFACE_CLIPPING_AXES = Object.freeze({
  sagittal: Object.freeze({ viewerAxisIndex: 0, sign: -1, centerIndex: 0 }),
  axial: Object.freeze({ viewerAxisIndex: 1, sign: 1, centerIndex: 1 }),
  coronal: Object.freeze({ viewerAxisIndex: 2, sign: -1, centerIndex: 2 }),
});

function finite(value, label) {
  const normalized = Number(value);
  if (!Number.isFinite(normalized)) throw new TypeError(`${label} must be finite`);
  return normalized;
}

function clippingPresentation(presentation) {
  const center = presentation?.viewerCenterLpsMm;
  const maximumExtentMm = Number(presentation?.maximumExtentMm);
  if (
    !Array.isArray(center)
    || center.length !== 3
    || !center.every(Number.isFinite)
    || !Number.isFinite(maximumExtentMm)
    || maximumExtentMm <= 0
  ) {
    return null;
  }
  return Object.freeze({ center, scale: 2 / maximumExtentMm });
}

function viewerBoundary(axis, patientLpsMm, presentation) {
  return axis.sign * presentation.scale * patientLpsMm
    - presentation.scale * presentation.center[axis.centerIndex];
}

function planeDescriptor(viewerAxisIndex, normalSign, boundary) {
  const normal = [0, 0, 0];
  normal[viewerAxisIndex] = normalSign;
  return Object.freeze({
    normal: Object.freeze(normal),
    constant: -normalSign * boundary,
  });
}

export function resolvePatientSurfaceClippingDescriptors(presentation, clipping = {}) {
  const normalizedPresentation = clippingPresentation(presentation);
  if (!normalizedPresentation) return Object.freeze([]);

  const descriptors = [];
  for (const [planeName, axis] of Object.entries(SURFACE_CLIPPING_AXES)) {
    const entry = clipping?.[planeName];
    if (entry?.enabled !== true) continue;
    const minimum = finite(entry.minimumLpsMm, `${planeName} minimum Patient LPS bound`);
    const maximum = finite(entry.maximumLpsMm, `${planeName} maximum Patient LPS bound`);
    if (maximum < minimum) {
      throw new RangeError(`${planeName} Patient LPS clipping bounds are invalid`);
    }
    const viewerAtMinimum = viewerBoundary(axis, minimum, normalizedPresentation);
    const viewerAtMaximum = viewerBoundary(axis, maximum, normalizedPresentation);
    if (axis.sign > 0) {
      descriptors.push(planeDescriptor(axis.viewerAxisIndex, 1, viewerAtMinimum));
      descriptors.push(planeDescriptor(axis.viewerAxisIndex, -1, viewerAtMaximum));
    } else {
      descriptors.push(planeDescriptor(axis.viewerAxisIndex, -1, viewerAtMinimum));
      descriptors.push(planeDescriptor(axis.viewerAxisIndex, 1, viewerAtMaximum));
    }
  }
  return Object.freeze(descriptors);
}

export function createThreeSurfaceClippingPlanes(THREE, presentation, clipping = {}, viewerOffset = [0, 0, 0]) {
  const descriptors = resolvePatientSurfaceClippingDescriptors(presentation, clipping);
  if (descriptors.length === 0) return [];
  if (!THREE?.Plane || !THREE?.Vector3) {
    throw new TypeError("Three.js clipping plane support is required");
  }
  const offset = Array.isArray(viewerOffset) && viewerOffset.length === 3
    ? viewerOffset.map((value) => Number.isFinite(Number(value)) ? Number(value) : 0)
    : [0, 0, 0];
  return descriptors.map((descriptor) => {
    const normalDotOffset = descriptor.normal.reduce(
      (total, component, index) => total + component * offset[index],
      0,
    );
    return new THREE.Plane(
      new THREE.Vector3(...descriptor.normal),
      descriptor.constant - normalDotOffset,
    );
  });
}

export function applySurfaceClippingToMaterial(
  material,
  THREE,
  presentation,
  clipping,
  enabled = true,
  viewerOffset = [0, 0, 0],
) {
  if (!material) return Object.freeze([]);
  const planes = enabled
    ? createThreeSurfaceClippingPlanes(THREE, presentation, clipping, viewerOffset)
    : [];
  const previousCount = Array.isArray(material.clippingPlanes)
    ? material.clippingPlanes.length
    : 0;
  material.clippingPlanes = planes;
  material.clipIntersection = false;
  if (previousCount !== planes.length) material.needsUpdate = true;
  return Object.freeze([...planes]);
}

export function enableSurfaceLocalClipping(renderer) {
  if (!renderer || !("localClippingEnabled" in renderer)) {
    throw new TypeError("Three.js renderer local clipping support is required");
  }
  renderer.localClippingEnabled = true;
  return renderer.localClippingEnabled;
}
