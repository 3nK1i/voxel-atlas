const MAX_RAY_STEPS = 512;
const INTERACTIVE_SAMPLE_RATE = 384;
export const TRANSFER_POINT_COUNT = 6;

export const PATIENT_LPS_TO_VIEWER = Object.freeze([
  -1, 0, 0, 0,
  0, 0, 1, 0,
  0, -1, 0, 0,
  0, 0, 0, 1,
]);

const LOCAL_BOX_TO_TEXTURE = Object.freeze([
  1, 0, 0, 0.5,
  0, 1, 0, 0.5,
  0, 0, 1, 0.5,
  0, 0, 0, 1,
]);

const VERTEX_SHADER = `
out vec3 vRayOrigin;
out vec3 vRayDirection;

void main() {
  vRayOrigin = (inverse(modelMatrix) * vec4(cameraPosition, 1.0)).xyz;
  vRayDirection = position - vRayOrigin;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const FRAGMENT_SHADER = `
precision highp float;
precision highp int;
precision highp sampler3D;

uniform highp sampler3D uVolume;
uniform float uDecodeOffset;
uniform float uDecodeScale;
uniform float uTransferIntensities[${TRANSFER_POINT_COUNT}];
uniform float uTransferOpacities[${TRANSFER_POINT_COUNT}];
uniform vec3 uTransferColors[${TRANSFER_POINT_COUNT}];
uniform float uDensityScale;
uniform float uGlobalOpacity;
uniform float uSamplingRate;
uniform mat4 uLocalToPatientLps;
uniform vec3 uClipPlanePositions;
uniform vec3 uClipPlaneKeepSigns;
uniform vec3 uClipPlaneEnabled;

in vec3 vRayOrigin;
in vec3 vRayDirection;
out vec4 outColor;

vec2 intersectUnitBox(vec3 origin, vec3 direction) {
  const vec3 boxMinimum = vec3(-0.5);
  const vec3 boxMaximum = vec3(0.5);
  vec3 inverseDirection = 1.0 / direction;
  vec3 first = (boxMinimum - origin) * inverseDirection;
  vec3 second = (boxMaximum - origin) * inverseDirection;
  vec3 nearVector = min(first, second);
  vec3 farVector = max(first, second);
  float entry = max(max(nearVector.x, nearVector.y), nearVector.z);
  float exit = min(min(farVector.x, farVector.y), farVector.z);
  return vec2(entry, exit);
}

bool clipAgainstPatientPlane(
  float rayOrigin,
  float rayDirection,
  float planePosition,
  float keepSign,
  inout float entry,
  inout float exit
) {
  float signedOrigin = keepSign * (rayOrigin - planePosition);
  float signedDirection = keepSign * rayDirection;
  if (abs(signedDirection) < 0.000001) {
    return signedOrigin >= 0.0;
  }
  float boundary = -signedOrigin / signedDirection;
  if (signedDirection > 0.0) {
    entry = max(entry, boundary);
  } else {
    exit = min(exit, boundary);
  }
  return exit > entry;
}

vec2 clipPatientRayInterval(vec3 localOrigin, vec3 localDirection, vec2 boxInterval) {
  float entry = max(boxInterval.x, 0.0);
  float exit = boxInterval.y;
  vec3 patientOrigin = (uLocalToPatientLps * vec4(localOrigin, 1.0)).xyz;
  vec3 patientDirection = (uLocalToPatientLps * vec4(localDirection, 0.0)).xyz;

  if (
    uClipPlaneEnabled.x > 0.5
    && !clipAgainstPatientPlane(
      patientOrigin.x,
      patientDirection.x,
      uClipPlanePositions.x,
      uClipPlaneKeepSigns.x,
      entry,
      exit
    )
  ) return vec2(1.0, -1.0);
  if (
    uClipPlaneEnabled.y > 0.5
    && !clipAgainstPatientPlane(
      patientOrigin.y,
      patientDirection.y,
      uClipPlanePositions.y,
      uClipPlaneKeepSigns.y,
      entry,
      exit
    )
  ) return vec2(1.0, -1.0);
  if (
    uClipPlaneEnabled.z > 0.5
    && !clipAgainstPatientPlane(
      patientOrigin.z,
      patientDirection.z,
      uClipPlanePositions.z,
      uClipPlaneKeepSigns.z,
      entry,
      exit
    )
  ) return vec2(1.0, -1.0);
  return vec2(entry, exit);
}

float decodeMedicalIntensity(vec3 textureCoordinate) {
  vec2 encoded = texture(uVolume, textureCoordinate).rg;
  float lowByte = floor(encoded.r * 255.0 + 0.5);
  float highByte = floor(encoded.g * 255.0 + 0.5);
  return uDecodeOffset + uDecodeScale * (lowByte + highByte * 256.0);
}

vec4 sampleMedicalTransfer(float intensity) {
  if (intensity <= uTransferIntensities[0]) {
    return vec4(uTransferColors[0], uTransferOpacities[0]);
  }
  for (int point = 1; point < ${TRANSFER_POINT_COUNT}; point += 1) {
    if (intensity <= uTransferIntensities[point]) {
      float interval = max(
        uTransferIntensities[point] - uTransferIntensities[point - 1],
        0.000001
      );
      float blend = clamp(
        (intensity - uTransferIntensities[point - 1]) / interval,
        0.0,
        1.0
      );
      return vec4(
        mix(uTransferColors[point - 1], uTransferColors[point], blend),
        mix(uTransferOpacities[point - 1], uTransferOpacities[point], blend)
      );
    }
  }
  return vec4(
    uTransferColors[${TRANSFER_POINT_COUNT - 1}],
    uTransferOpacities[${TRANSFER_POINT_COUNT - 1}]
  );
}

void main() {
  vec3 direction = normalize(vRayDirection);
  vec2 boxIntersection = intersectUnitBox(vRayOrigin, direction);
  vec2 intersection = clipPatientRayInterval(vRayOrigin, direction, boxIntersection);
  float entry = intersection.x;
  float rayLength = intersection.y - entry;
  if (rayLength <= 0.0) discard;

  float sampleCount = clamp(ceil(rayLength * uSamplingRate), 1.0, float(${MAX_RAY_STEPS}));
  float stepLength = rayLength / sampleCount;
  vec3 stepVector = direction * stepLength;
  vec3 samplePosition = vRayOrigin + direction * (entry + 0.5 * stepLength);
  vec4 accumulated = vec4(0.0);

  for (int index = 0; index < ${MAX_RAY_STEPS}; index += 1) {
    if (float(index) >= sampleCount) break;
    vec3 textureCoordinate = samplePosition + vec3(0.5);
    float intensity = decodeMedicalIntensity(textureCoordinate);
    vec4 transferSample = sampleMedicalTransfer(intensity);
    vec3 sampleColor = transferSample.rgb;
    float sampleAlpha = 1.0 - exp(
      -transferSample.a * uDensityScale * uGlobalOpacity * stepLength
    );
    float remaining = 1.0 - accumulated.a;
    accumulated.rgb += remaining * sampleAlpha * sampleColor;
    accumulated.a += remaining * sampleAlpha;
    if (accumulated.a >= 0.98) break;
    samplePosition += stepVector;
  }

  if (accumulated.a <= 0.001) discard;
  outColor = accumulated;
}
`;

function finiteNumber(value, field) {
  const result = Number(value);
  if (!Number.isFinite(result)) {
    throw new TypeError(`Patient volume ${field} is invalid`);
  }
  return result;
}

function descriptorMatrix(value) {
  if (
    !Array.isArray(value)
    || value.length !== 4
    || value.some((row) => !Array.isArray(row) || row.length !== 4)
  ) {
    throw new TypeError("Patient volume texture-to-LPS transform is invalid");
  }
  return value.flat().map((item) => finiteNumber(item, "texture-to-LPS transform"));
}

function multiplyMatrices(left, right) {
  const result = new Array(16).fill(0);
  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 4; column += 1) {
      for (let index = 0; index < 4; index += 1) {
        result[row * 4 + column] += left[row * 4 + index] * right[index * 4 + column];
      }
    }
  }
  return result;
}

function transformPoint(matrix, point) {
  const [x, y, z] = point;
  const homogeneous = [x, y, z, 1];
  return [0, 1, 2].map((row) => (
    matrix[row * 4] * homogeneous[0]
    + matrix[row * 4 + 1] * homogeneous[1]
    + matrix[row * 4 + 2] * homogeneous[2]
    + matrix[row * 4 + 3]
  ));
}

function stableNumber(value) {
  const rounded = Number(value.toFixed(12));
  return Object.is(rounded, -0) ? 0 : rounded;
}

export function buildVolumePresentation(descriptor) {
  const textureToPatientLps = descriptorMatrix(
    descriptor?.texture_coordinate_to_patient_lps,
  );
  const localToPatientLps = multiplyMatrices(textureToPatientLps, LOCAL_BOX_TO_TEXTURE);
  const localToViewerMm = multiplyMatrices(PATIENT_LPS_TO_VIEWER, localToPatientLps);
  const corners = [];
  for (const x of [-0.5, 0.5]) {
    for (const y of [-0.5, 0.5]) {
      for (const z of [-0.5, 0.5]) {
        corners.push(transformPoint(localToViewerMm, [x, y, z]));
      }
    }
  }
  const minimum = [0, 1, 2].map((axis) => Math.min(...corners.map((item) => item[axis])));
  const maximum = [0, 1, 2].map((axis) => Math.max(...corners.map((item) => item[axis])));
  const extentMm = maximum.map((value, axis) => value - minimum[axis]);
  if (extentMm.some((value) => !Number.isFinite(value) || value <= 0)) {
    throw new TypeError("Patient volume physical extent is invalid");
  }
  const maximumExtentMm = Math.max(...extentMm);
  const center = maximum.map((value, axis) => (value + minimum[axis]) / 2);
  const scale = 2 / maximumExtentMm;
  const centerAndScale = [
    scale, 0, 0, -scale * center[0],
    0, scale, 0, -scale * center[1],
    0, 0, scale, -scale * center[2],
    0, 0, 0, 1,
  ];
  const matrix = multiplyMatrices(centerAndScale, localToViewerMm).map(stableNumber);
  return Object.freeze({
    matrix: Object.freeze(matrix),
    localToPatientLps: Object.freeze(localToPatientLps.map(stableNumber)),
    extentMm: Object.freeze(extentMm.map(stableNumber)),
    normalizedExtent: Object.freeze(extentMm.map((value) => stableNumber(value * scale))),
    maximumExtentMm: stableNumber(maximumExtentMm),
    viewerCenterLpsMm: Object.freeze(center.map(stableNumber)),
  });
}

const PATIENT_CLIPPING_PLANES = Object.freeze({
  axial: Object.freeze({ axis: "z", axisIndex: 2 }),
  coronal: Object.freeze({ axis: "y", axisIndex: 1 }),
  sagittal: Object.freeze({ axis: "x", axisIndex: 0 }),
});

function patientBounds(descriptor) {
  const raw = descriptor?.patient_bounds_lps_mm;
  let bounds;
  if (Array.isArray(raw) && raw.length === 6) {
    bounds = raw.map((value) => finiteNumber(value, "LPS bounds"));
  } else {
    const textureToPatientLps = descriptorMatrix(
      descriptor?.texture_coordinate_to_patient_lps,
    );
    const corners = [];
    for (const x of [0, 1]) {
      for (const y of [0, 1]) {
        for (const z of [0, 1]) {
          corners.push(transformPoint(textureToPatientLps, [x, y, z]));
        }
      }
    }
    const minimum = [0, 1, 2].map(
      (axis) => Math.min(...corners.map((point) => point[axis])),
    );
    const maximum = [0, 1, 2].map(
      (axis) => Math.max(...corners.map((point) => point[axis])),
    );
    bounds = [...minimum, ...maximum];
  }
  for (let axis = 0; axis < 3; axis += 1) {
    if (bounds[axis + 3] <= bounds[axis]) {
      throw new TypeError("Patient volume LPS bounds are invalid");
    }
  }
  return bounds;
}

export function createPatientClippingState(descriptor, requestedPlanes = {}) {
  const bounds = patientBounds(descriptor);
  const planes = {};
  const enabled = [0, 0, 0];
  const positionsLpsMm = [0, 0, 0];
  const keepSigns = [-1, -1, -1];

  for (const [name, definition] of Object.entries(PATIENT_CLIPPING_PLANES)) {
    const minimum = bounds[definition.axisIndex];
    const maximum = bounds[definition.axisIndex + 3];
    const request = requestedPlanes?.[name] || {};
    const position = request.positionLpsMm === undefined
      ? (minimum + maximum) / 2
      : finiteNumber(request.positionLpsMm, `${name} clipping position`);
    if (position < minimum || position > maximum) {
      throw new TypeError(`Patient volume ${name} clipping position is outside patient bounds`);
    }
    const retainedSide = request.retainedSide || "minimum";
    if (retainedSide !== "minimum" && retainedSide !== "maximum") {
      throw new TypeError(`Patient volume ${name} retained side is invalid`);
    }
    const plane = Object.freeze({
      enabled: request.enabled === true,
      axis: definition.axis,
      axisIndex: definition.axisIndex,
      minimumLpsMm: minimum,
      maximumLpsMm: maximum,
      positionLpsMm: position,
      retainedSide,
    });
    planes[name] = plane;
    enabled[definition.axisIndex] = plane.enabled ? 1 : 0;
    positionsLpsMm[definition.axisIndex] = position;
    keepSigns[definition.axisIndex] = retainedSide === "maximum" ? 1 : -1;
  }

  return Object.freeze({
    patientSpace: "DICOM Patient LPS millimetres",
    planes: Object.freeze(planes),
    enabled: Object.freeze(enabled),
    positionsLpsMm: Object.freeze(positionsLpsMm),
    keepSigns: Object.freeze(keepSigns),
  });
}

function sourceRange(descriptor) {
  if (!Array.isArray(descriptor?.source_value_range) || descriptor.source_value_range.length !== 2) {
    throw new TypeError("Patient volume source intensity range is invalid");
  }
  const low = finiteNumber(descriptor.source_value_range[0], "source intensity range");
  const high = finiteNumber(descriptor.source_value_range[1], "source intensity range");
  if (high < low) throw new TypeError("Patient volume source intensity range is invalid");
  return [low, high];
}

function transferPoint(position, opacity, color) {
  return Object.freeze({
    position,
    opacity,
    color: Object.freeze(color),
  });
}

const CT_TRANSFER_PRESETS = Object.freeze([
  Object.freeze({
    id: "ct-general",
    label: "General CT",
    description: "Balanced CT overview across air, soft tissue, and dense structures.",
    modality: "CT",
    units: "HU",
    rangeMode: "absolute",
    range: Object.freeze([-1000, 1200]),
    densityScale: 12.0,
    points: Object.freeze([
      transferPoint(0.00, 0.000, [0.03, 0.05, 0.08]),
      transferPoint(0.18, 0.008, [0.16, 0.22, 0.30]),
      transferPoint(0.38, 0.055, [0.48, 0.38, 0.34]),
      transferPoint(0.56, 0.150, [0.78, 0.58, 0.46]),
      transferPoint(0.76, 0.360, [0.96, 0.82, 0.66]),
      transferPoint(1.00, 0.720, [1.00, 0.96, 0.88]),
    ]),
  }),
  Object.freeze({
    id: "ct-soft-tissue",
    label: "Soft Tissue",
    description: "Emphasizes CT soft-tissue intensities while suppressing dense bone.",
    modality: "CT",
    units: "HU",
    rangeMode: "absolute",
    range: Object.freeze([-180, 350]),
    densityScale: 14.0,
    points: Object.freeze([
      transferPoint(0.00, 0.000, [0.12, 0.07, 0.08]),
      transferPoint(0.18, 0.045, [0.42, 0.20, 0.18]),
      transferPoint(0.38, 0.230, [0.72, 0.38, 0.32]),
      transferPoint(0.58, 0.420, [0.94, 0.64, 0.48]),
      transferPoint(0.80, 0.120, [0.92, 0.78, 0.65]),
      transferPoint(1.00, 0.000, [0.96, 0.90, 0.82]),
    ]),
  }),
  Object.freeze({
    id: "ct-bone",
    label: "Bone",
    description: "Emphasizes high-density CT structures using calibrated HU values.",
    modality: "CT",
    units: "HU",
    rangeMode: "absolute",
    range: Object.freeze([150, 1800]),
    densityScale: 12.0,
    points: Object.freeze([
      transferPoint(0.00, 0.000, [0.18, 0.15, 0.12]),
      transferPoint(0.18, 0.008, [0.42, 0.34, 0.25]),
      transferPoint(0.38, 0.080, [0.72, 0.59, 0.42]),
      transferPoint(0.58, 0.260, [0.92, 0.79, 0.60]),
      transferPoint(0.78, 0.560, [1.00, 0.91, 0.76]),
      transferPoint(1.00, 0.880, [1.00, 0.98, 0.92]),
    ]),
  }),
  Object.freeze({
    id: "ct-lung",
    label: "Low-Density CT",
    description: "Emphasizes low-density CT intensities without assigning an organ class.",
    modality: "CT",
    units: "HU",
    rangeMode: "absolute",
    range: Object.freeze([-1000, -250]),
    densityScale: 10.0,
    points: Object.freeze([
      transferPoint(0.00, 0.000, [0.02, 0.05, 0.09]),
      transferPoint(0.18, 0.090, [0.12, 0.32, 0.48]),
      transferPoint(0.38, 0.360, [0.30, 0.62, 0.78]),
      transferPoint(0.58, 0.250, [0.58, 0.78, 0.88]),
      transferPoint(0.80, 0.070, [0.82, 0.88, 0.90]),
      transferPoint(1.00, 0.000, [0.92, 0.92, 0.88]),
    ]),
  }),
]);

const MR_TRANSFER_PRESETS = Object.freeze([
  Object.freeze({
    id: "mr-balanced",
    label: "MR Balanced",
    description: "Balanced relative-intensity MR presentation without sequence assumptions.",
    modality: "MR",
    units: "modality",
    rangeMode: "relative",
    range: Object.freeze([0.03, 0.98]),
    densityScale: 10.0,
    points: Object.freeze([
      transferPoint(0.00, 0.000, [0.02, 0.03, 0.06]),
      transferPoint(0.18, 0.018, [0.12, 0.18, 0.28]),
      transferPoint(0.38, 0.100, [0.32, 0.44, 0.58]),
      transferPoint(0.58, 0.280, [0.58, 0.70, 0.82]),
      transferPoint(0.78, 0.500, [0.82, 0.88, 0.94]),
      transferPoint(1.00, 0.740, [0.98, 0.99, 1.00]),
    ]),
  }),
  Object.freeze({
    id: "mr-lower-intensity",
    label: "MR Lower Intensities",
    description: "Emphasizes lower relative MR signal without assigning a tissue class.",
    modality: "MR",
    units: "modality",
    rangeMode: "relative",
    range: Object.freeze([0.02, 0.68]),
    densityScale: 11.0,
    points: Object.freeze([
      transferPoint(0.00, 0.000, [0.03, 0.05, 0.10]),
      transferPoint(0.18, 0.110, [0.14, 0.28, 0.48]),
      transferPoint(0.38, 0.380, [0.34, 0.58, 0.76]),
      transferPoint(0.58, 0.270, [0.62, 0.78, 0.88]),
      transferPoint(0.80, 0.070, [0.84, 0.90, 0.95]),
      transferPoint(1.00, 0.000, [0.98, 0.99, 1.00]),
    ]),
  }),
  Object.freeze({
    id: "mr-higher-intensity",
    label: "MR Higher Intensities",
    description: "Emphasizes higher relative MR signal without assigning a tissue class.",
    modality: "MR",
    units: "modality",
    rangeMode: "relative",
    range: Object.freeze([0.24, 0.98]),
    densityScale: 10.0,
    points: Object.freeze([
      transferPoint(0.00, 0.000, [0.04, 0.04, 0.08]),
      transferPoint(0.18, 0.012, [0.16, 0.20, 0.34]),
      transferPoint(0.38, 0.090, [0.38, 0.48, 0.68]),
      transferPoint(0.58, 0.300, [0.64, 0.72, 0.88]),
      transferPoint(0.78, 0.580, [0.84, 0.88, 0.98]),
      transferPoint(1.00, 0.840, [1.00, 1.00, 1.00]),
    ]),
  }),
]);

const RELATIVE_TRANSFER_PRESETS = Object.freeze([
  Object.freeze({
    id: "relative-balanced",
    label: "Relative Intensity",
    description: "Generic relative-intensity presentation for an unclassified modality.",
    modality: "UNKNOWN",
    units: "modality",
    rangeMode: "relative",
    range: Object.freeze([0.05, 0.95]),
    densityScale: 9.0,
    points: MR_TRANSFER_PRESETS[0].points,
  }),
]);

function presetDefinitions(descriptor) {
  const modality = String(descriptor?.source_modality || "").toUpperCase();
  const units = String(descriptor?.source_intensity_units || "");
  if (modality === "CT" && units === "HU") {
    return CT_TRANSFER_PRESETS;
  }
  if (modality === "MR") {
    return MR_TRANSFER_PRESETS;
  }
  return RELATIVE_TRANSFER_PRESETS;
}

function effectiveSourceRange(descriptor) {
  const [low, high] = sourceRange(descriptor);
  return high === low ? [low - 0.5, high + 0.5] : [low, high];
}

function resolvedPresetRange(preset, sourceLow, sourceHigh) {
  const span = sourceHigh - sourceLow;
  let low;
  let high;
  if (preset.rangeMode === "relative") {
    low = sourceLow + span * preset.range[0];
    high = sourceLow + span * preset.range[1];
  } else {
    low = Math.max(sourceLow, preset.range[0]);
    high = Math.min(sourceHigh, preset.range[1]);
  }
  if (high <= low) return [sourceLow, sourceHigh];
  return [low, high];
}

export function listMedicalTransferPresets(descriptor) {
  const modality = String(descriptor?.source_modality || "").toUpperCase() || "UNKNOWN";
  const units = String(descriptor?.source_intensity_units || "") || "modality";
  sourceRange(descriptor);
  return Object.freeze(presetDefinitions(descriptor).map((preset) => Object.freeze({
    id: preset.id,
    label: preset.label,
    description: preset.description,
    modality,
    units,
  })));
}

export function createMedicalTransferFunction(descriptor, presetId = null, adjustments = {}) {
  const definitions = presetDefinitions(descriptor);
  const preset = presetId === null
    ? definitions[0]
    : definitions.find(({ id }) => id === presetId);
  if (!preset) throw new TypeError("Patient volume transfer-function preset is invalid");

  const [sourceLow, sourceHigh] = effectiveSourceRange(descriptor);
  const [presetLow, presetHigh] = resolvedPresetRange(preset, sourceLow, sourceHigh);
  const requestedLow = adjustments.rangeLow === undefined
    ? presetLow
    : finiteNumber(adjustments.rangeLow, "transfer-function lower intensity");
  const requestedHigh = adjustments.rangeHigh === undefined
    ? presetHigh
    : finiteNumber(adjustments.rangeHigh, "transfer-function upper intensity");
  const rangeLow = Math.max(sourceLow, Math.min(sourceHigh, requestedLow));
  const rangeHigh = Math.max(sourceLow, Math.min(sourceHigh, requestedHigh));
  const minimumInterval = Math.max((sourceHigh - sourceLow) / 65535, 0.000001);
  if (rangeHigh - rangeLow < minimumInterval) {
    throw new TypeError("Patient volume transfer-function intensity range is invalid");
  }

  const densityMultiplier = adjustments.densityMultiplier === undefined
    ? 1
    : finiteNumber(adjustments.densityMultiplier, "transfer-function density");
  if (densityMultiplier < 0.25 || densityMultiplier > 2) {
    throw new TypeError("Patient volume transfer-function density is invalid");
  }

  const rangeSpan = rangeHigh - rangeLow;
  const controlPoints = Object.freeze(preset.points.map((point) => Object.freeze({
    intensity: rangeLow + rangeSpan * point.position,
    opacity: point.opacity,
    color: point.color,
  })));
  const modality = String(descriptor?.source_modality || "").toUpperCase() || "UNKNOWN";
  const units = String(descriptor?.source_intensity_units || "") || "modality";
  return Object.freeze({
    id: preset.id,
    label: preset.label,
    description: preset.description,
    modality,
    units,
    sourceRange: Object.freeze([sourceLow, sourceHigh]),
    rangeLow,
    rangeHigh,
    densityMultiplier,
    densityScale: preset.densityScale * densityMultiplier,
    controlPoints,
    intensityLow: rangeLow,
    intensityHigh: rangeHigh,
    absorption: preset.densityScale * densityMultiplier,
    colorLow: controlPoints[0].color,
    colorHigh: controlPoints[controlPoints.length - 1].color,
  });
}

export function selectBaselineTransferFunction(descriptor) {
  return createMedicalTransferFunction(descriptor);
}

function transferUniformValues(THREE, transfer) {
  return {
    intensities: transfer.controlPoints.map(({ intensity }) => intensity),
    opacities: transfer.controlPoints.map(({ opacity }) => opacity),
    colors: transfer.controlPoints.map(
      ({ color }) => new THREE.Vector3(color[0], color[1], color[2]),
    ),
  };
}

function applyTransferUniforms(THREE, material, transfer) {
  const values = transferUniformValues(THREE, transfer);
  material.uniforms.uTransferIntensities.value = values.intensities;
  material.uniforms.uTransferOpacities.value = values.opacities;
  material.uniforms.uTransferColors.value = values.colors;
  material.uniforms.uDensityScale.value = transfer.densityScale;
  material.uniformsNeedUpdate = true;
}

function requireTextureResource(textureResource) {
  const descriptor = textureResource?.descriptor;
  if (!textureResource?.texture || descriptor?.ready !== true) {
    throw new TypeError("A verified patient volume texture is required");
  }
  if (!Array.isArray(descriptor.texture_dimensions) || descriptor.texture_dimensions.length !== 3) {
    throw new TypeError("Patient volume texture dimensions are invalid");
  }
  const dimensions = descriptor.texture_dimensions.map((value) => Number(value));
  if (!dimensions.every((value) => Number.isInteger(value) && value > 0)) {
    throw new TypeError("Patient volume texture dimensions are invalid");
  }
  const decodeOffset = finiteNumber(descriptor.decode_offset, "decode offset");
  const decodeScale = finiteNumber(descriptor.decode_scale, "decode scale");
  if (decodeScale <= 0) throw new TypeError("Patient volume decode scale is invalid");
  return { descriptor, dimensions, decodeOffset, decodeScale };
}

export class PatientVolumeRayMarcher {
  constructor({ three }) {
    if (
      !three?.BoxGeometry
      || !three?.ShaderMaterial
      || !three?.Mesh
      || !three?.Group
      || !three?.Matrix4
      || !three?.Vector3
    ) {
      throw new TypeError("Three.js volume ray-marching support is required");
    }
    this.three = three;
    this.current = null;
  }

  create(textureResource) {
    const { descriptor, dimensions, decodeOffset, decodeScale } = requireTextureResource(
      textureResource,
    );
    this.dispose();
    const THREE = this.three;
    const presentation = buildVolumePresentation(descriptor);
    const transfer = selectBaselineTransferFunction(descriptor);
    const clipping = createPatientClippingState(descriptor);
    const transferUniforms = transferUniformValues(THREE, transfer);
    const texture = textureResource.texture;
    texture.minFilter = THREE.NearestFilter;
    texture.magFilter = THREE.NearestFilter;
    texture.needsUpdate = true;

    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.ShaderMaterial({
      name: "VoxelAtlas true patient volume ray marcher",
      glslVersion: THREE.GLSL3,
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms: {
        uVolume: { value: texture },
        uDecodeOffset: { value: decodeOffset },
        uDecodeScale: { value: decodeScale },
        uTransferIntensities: { value: transferUniforms.intensities },
        uTransferOpacities: { value: transferUniforms.opacities },
        uTransferColors: { value: transferUniforms.colors },
        uDensityScale: { value: transfer.densityScale },
        uGlobalOpacity: { value: 1 },
        uSamplingRate: { value: Math.min(Math.max(...dimensions), INTERACTIVE_SAMPLE_RATE) },
        uLocalToPatientLps: {
          value: new THREE.Matrix4().set(...presentation.localToPatientLps),
        },
        uClipPlanePositions: {
          value: new THREE.Vector3(...clipping.positionsLpsMm),
        },
        uClipPlaneKeepSigns: {
          value: new THREE.Vector3(...clipping.keepSigns),
        },
        uClipPlaneEnabled: {
          value: new THREE.Vector3(...clipping.enabled),
        },
      },
      side: THREE.BackSide,
      transparent: true,
      premultipliedAlpha: true,
      depthWrite: false,
      depthTest: true,
      dithering: true,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = "True patient voxel volume";
    mesh.matrixAutoUpdate = false;
    mesh.matrix.set(...presentation.matrix);
    mesh.frustumCulled = false;

    const root = new THREE.Group();
    root.name = "Patient volume ray marcher";
    root.userData.volumeRevision = descriptor.revision;
    root.userData.patientSpace = "DICOM Patient LPS millimetres";
    root.add(mesh);
    root.updateMatrixWorld(true);

    const resource = Object.freeze({
      root,
      mesh,
      geometry,
      material,
      descriptor,
      presentation,
      transfer,
      transferState: { current: transfer },
      clippingState: { current: clipping },
    });
    this.current = resource;
    return resource;
  }

  setOpacity(value) {
    if (!this.current) return;
    const opacity = Math.min(1, Math.max(0, finiteNumber(value, "opacity")));
    this.current.material.uniforms.uGlobalOpacity.value = opacity;
  }

  setTransferPreset(presetId, adjustments = {}) {
    if (!this.current) {
      throw new TypeError("A patient volume must be active before changing its transfer function");
    }
    const transfer = createMedicalTransferFunction(
      this.current.descriptor,
      presetId,
      adjustments,
    );
    applyTransferUniforms(this.three, this.current.material, transfer);
    this.current.transferState.current = transfer;
    return transfer;
  }

  setClippingPlanes(planes = {}) {
    if (!this.current) {
      throw new TypeError("A patient volume must be active before changing clipping planes");
    }
    const clipping = createPatientClippingState(this.current.descriptor, planes);
    const uniforms = this.current.material.uniforms;
    uniforms.uClipPlaneEnabled.value.set(...clipping.enabled);
    uniforms.uClipPlanePositions.value.set(...clipping.positionsLpsMm);
    uniforms.uClipPlaneKeepSigns.value.set(...clipping.keepSigns);
    this.current.material.uniformsNeedUpdate = true;
    this.current.clippingState.current = clipping;
    return clipping;
  }

  dispose() {
    if (!this.current) return;
    if (this.current.root.parent) {
      this.current.root.parent.remove(this.current.root);
    }
    this.current.geometry.dispose();
    this.current.material.dispose();
    this.current = null;
  }
}
