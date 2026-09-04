const MAX_RAY_STEPS = 512;
export const MIN_RAY_SAMPLING_RATE = 48;
const DEFAULT_SAMPLE_RATE = 384;
export const TRANSFER_POINT_COUNT = 6;

export const MEDICAL_RENDERING_MODES = Object.freeze([
  Object.freeze({
    id: "dvr",
    label: "Volume / DVR",
    code: 0,
    usesDvrControls: true,
    description: "DVR compositing accumulates color and opacity through the patient volume.",
  }),
  Object.freeze({
    id: "mip",
    label: "MIP",
    code: 1,
    usesDvrControls: false,
    description: "Maximum Intensity Projection shows the highest sampled voxel intensity along each ray.",
  }),
  Object.freeze({
    id: "minip",
    label: "MinIP",
    code: 2,
    usesDvrControls: false,
    description: "Minimum Intensity Projection shows the lowest sampled voxel intensity along each ray.",
  }),
  Object.freeze({
    id: "average",
    label: "Average Intensity",
    code: 3,
    usesDvrControls: false,
    description: "Average Intensity displays the arithmetic mean of sampled voxels along each ray.",
  }),
]);

function medicalRenderingMode(modeId) {
  const mode = MEDICAL_RENDERING_MODES.find(({ id }) => id === modeId);
  if (!mode) throw new TypeError("Patient volume rendering mode is invalid");
  return mode;
}

export function listMedicalRenderingModes() {
  return MEDICAL_RENDERING_MODES;
}

export function aggregateMedicalProjection(samples, modeId) {
  const mode = medicalRenderingMode(modeId);
  if (mode.id === "dvr") {
    throw new TypeError("DVR uses front-to-back compositing, not scalar projection");
  }
  if (!Array.isArray(samples) || samples.length === 0) {
    throw new TypeError("Medical projection samples are invalid");
  }
  const values = samples.map((value) => finiteNumber(value, "projection sample"));
  if (mode.id === "mip") return Math.max(...values);
  if (mode.id === "minip") return Math.min(...values);
  return values.reduce((total, value) => total + value, 0) / values.length;
}

const OPACITY_FEATHER_FRACTION = 0.30;
const EDGE_GRADIENT_START = 0.025;
const EDGE_GRADIENT_FULL = 0.65;
const EDGE_FLAT_OPACITY = 0.18;
const EDGE_STRONG_OPACITY = 2.60;
const SHADING_AMBIENT = 0.24;
const SHADING_HEADLIGHT = 0.38;
const SHADING_KEYLIGHT = 0.48;
const SHADING_SPECULAR = 0.16;

function clampUnit(value) {
  return Math.min(1, Math.max(0, value));
}

function smoothstepValue(edge0, edge1, value) {
  const normalized = clampUnit((value - edge0) / Math.max(edge1 - edge0, 0.000001));
  return normalized * normalized * (3 - 2 * normalized);
}

export function evaluateOpacitySoftnessWeight(
  intensity,
  rangeLow,
  rangeHigh,
  softness,
) {
  const span = Math.max(rangeHigh - rangeLow, 0.000001);
  const boundedSoftness = clampUnit(softness);
  const fadeWidth = span * boundedSoftness * OPACITY_FEATHER_FRACTION;
  if (fadeWidth <= 0.000001) return 1;
  const lower = smoothstepValue(rangeLow, rangeLow + fadeWidth, intensity);
  const upper = 1 - smoothstepValue(rangeHigh - fadeWidth, rangeHigh, intensity);
  return lower * upper;
}

export function evaluateEdgeDefinitionWeight(normalizedGradient, strength) {
  const response = smoothstepValue(
    EDGE_GRADIENT_START,
    EDGE_GRADIENT_FULL,
    Math.max(0, normalizedGradient),
  );
  const definedOpacity = EDGE_FLAT_OPACITY
    + (EDGE_STRONG_OPACITY - EDGE_FLAT_OPACITY) * response;
  return 1 + (definedOpacity - 1) * clampUnit(strength);
}

export function evaluateDepthShadingFactor(
  headlightAlignment,
  keylightAlignment,
  specularAlignment,
  strength,
) {
  const lighting = SHADING_AMBIENT
    + SHADING_HEADLIGHT * clampUnit(headlightAlignment)
    + SHADING_KEYLIGHT * clampUnit(keylightAlignment)
    + SHADING_SPECULAR * clampUnit(specularAlignment);
  return 1 + (lighting - 1) * clampUnit(strength);
}

export function constrainMedicalIntensityInterval(
  sourceRange,
  requestedMinimum,
  requestedMaximum,
  changedBoundary,
) {
  if (!Array.isArray(sourceRange) || sourceRange.length !== 2) {
    throw new TypeError("Patient volume source intensity range is invalid");
  }
  const sourceLow = finiteNumber(sourceRange[0], "source intensity minimum");
  const sourceHigh = finiteNumber(sourceRange[1], "source intensity maximum");
  if (sourceHigh <= sourceLow) {
    throw new TypeError("Patient volume source intensity range is invalid");
  }
  if (changedBoundary !== "minimum" && changedBoundary !== "maximum") {
    throw new TypeError("Patient volume intensity boundary selection is invalid");
  }
  const minimumGap = Math.max((sourceHigh - sourceLow) / 65535, 0.000001);
  let minimum = Math.min(sourceHigh, Math.max(
    sourceLow,
    finiteNumber(requestedMinimum, "visible intensity minimum"),
  ));
  let maximum = Math.min(sourceHigh, Math.max(
    sourceLow,
    finiteNumber(requestedMaximum, "visible intensity maximum"),
  ));
  if (maximum - minimum < minimumGap) {
    if (changedBoundary === "minimum") {
      if (maximum <= sourceLow + minimumGap) {
        minimum = sourceLow;
        maximum = sourceLow + minimumGap;
      } else {
        minimum = maximum - minimumGap;
      }
    } else {
      if (minimum >= sourceHigh - minimumGap) {
        minimum = sourceHigh - minimumGap;
        maximum = sourceHigh;
      } else {
        maximum = minimum + minimumGap;
      }
    }
  }
  return Object.freeze({ minimum, maximum });
}

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
uniform float uWindowCenter;
uniform float uWindowWidth;
uniform vec3 uIntensityBounds;
uniform float uDensityScale;
uniform float uGlobalOpacity;
uniform float uSamplingRate;
uniform vec3 uTextureTexelSize;
uniform float uOpacitySoftness;
uniform float uEdgeDefinition;
uniform float uShadingStrength;
uniform int uRenderingMode;
uniform mat4 uLocalToPatientLps;
uniform vec3 uClipPlanePositions;
uniform vec3 uClipPlaneKeepSigns;
uniform vec3 uClipPlaneEnabled;

in vec3 vRayOrigin;
in vec3 vRayDirection;
out vec4 outColor;

const int RENDER_MODE_DVR = 0;
const int RENDER_MODE_MIP = 1;
const int RENDER_MODE_MINIP = 2;
const int RENDER_MODE_AVERAGE = 3;

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

float windowMedicalIntensity(float intensity) {
  float windowMinimum = uWindowCenter - 0.5 * uWindowWidth;
  return clamp((intensity - windowMinimum) / max(uWindowWidth, 0.000001), 0.0, 1.0);
}

float opacityBoundaryWeight(float intensity) {
  float rangeSpan = max(uIntensityBounds.y - uIntensityBounds.x, 0.000001);
  float fadeWidth = rangeSpan * uOpacitySoftness * ${OPACITY_FEATHER_FRACTION.toFixed(2)};
  if (fadeWidth <= 0.000001) return 1.0;
  float lowerWeight = smoothstep(
    uIntensityBounds.x,
    uIntensityBounds.x + fadeWidth,
    intensity
  );
  float upperWeight = 1.0 - smoothstep(
    uIntensityBounds.y - fadeWidth,
    uIntensityBounds.y,
    intensity
  );
  return lowerWeight * upperWeight;
}

vec3 sampleMedicalGradient(vec3 textureCoordinate) {
  vec3 halfTexel = 0.5 * uTextureTexelSize;
  vec3 minimumCoordinate = halfTexel;
  vec3 maximumCoordinate = vec3(1.0) - halfTexel;
  vec3 xOffset = vec3(uTextureTexelSize.x, 0.0, 0.0);
  vec3 yOffset = vec3(0.0, uTextureTexelSize.y, 0.0);
  vec3 zOffset = vec3(0.0, 0.0, uTextureTexelSize.z);
  float xLow = decodeMedicalIntensity(clamp(textureCoordinate - xOffset, minimumCoordinate, maximumCoordinate));
  float xHigh = decodeMedicalIntensity(clamp(textureCoordinate + xOffset, minimumCoordinate, maximumCoordinate));
  float yLow = decodeMedicalIntensity(clamp(textureCoordinate - yOffset, minimumCoordinate, maximumCoordinate));
  float yHigh = decodeMedicalIntensity(clamp(textureCoordinate + yOffset, minimumCoordinate, maximumCoordinate));
  float zLow = decodeMedicalIntensity(clamp(textureCoordinate - zOffset, minimumCoordinate, maximumCoordinate));
  float zHigh = decodeMedicalIntensity(clamp(textureCoordinate + zOffset, minimumCoordinate, maximumCoordinate));
  return vec3(
    (xHigh - xLow) / max(2.0 * uTextureTexelSize.x, 0.000001),
    (yHigh - yLow) / max(2.0 * uTextureTexelSize.y, 0.000001),
    (zHigh - zLow) / max(2.0 * uTextureTexelSize.z, 0.000001)
  );
}

vec3 patientSpaceMedicalGradient(vec3 textureCoordinate) {
  vec3 textureGradient = sampleMedicalGradient(textureCoordinate);
  mat3 textureToPatient = mat3(uLocalToPatientLps);
  return transpose(inverse(textureToPatient)) * textureGradient;
}

float edgeDefinitionOpacityWeight(vec3 patientGradient) {
  float normalizedGradient = length(patientGradient) / max(uWindowWidth, 0.000001);
  float edgeResponse = smoothstep(
    ${EDGE_GRADIENT_START.toFixed(3)},
    ${EDGE_GRADIENT_FULL.toFixed(2)},
    normalizedGradient
  );
  float definedOpacity = mix(
    ${EDGE_FLAT_OPACITY.toFixed(2)},
    ${EDGE_STRONG_OPACITY.toFixed(2)},
    edgeResponse
  );
  return mix(1.0, definedOpacity, uEdgeDefinition);
}

vec3 applyMedicalDepthShading(vec3 color, vec3 patientGradient, vec3 rayDirection) {
  if (uShadingStrength <= 0.0001 || length(patientGradient) <= 0.000001) return color;
  mat3 localToPatient = mat3(uLocalToPatientLps);
  vec3 viewDirection = normalize(-(localToPatient * rayDirection));
  vec3 patientNormal = normalize(patientGradient);
  if (dot(patientNormal, viewDirection) < 0.0) patientNormal = -patientNormal;
  vec3 keyDirection = normalize(viewDirection + vec3(-0.46, 0.34, 0.58));
  vec3 halfwayDirection = normalize(viewDirection + keyDirection);
  float headlight = max(dot(patientNormal, viewDirection), 0.0);
  float keylight = max(dot(patientNormal, keyDirection), 0.0);
  float specular = pow(max(dot(patientNormal, halfwayDirection), 0.0), 20.0);
  float lighting = ${SHADING_AMBIENT.toFixed(2)}
    + ${SHADING_HEADLIGHT.toFixed(2)} * headlight
    + ${SHADING_KEYLIGHT.toFixed(2)} * keylight
    + ${SHADING_SPECULAR.toFixed(2)} * specular;
  return color * mix(1.0, lighting, uShadingStrength);
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
  float projectedIntensity = 0.0;
  float projectionSampleCount = 0.0;

  for (int index = 0; index < ${MAX_RAY_STEPS}; index += 1) {
    if (float(index) >= sampleCount) break;
    vec3 textureCoordinate = samplePosition + vec3(0.5);
    float intensity = decodeMedicalIntensity(textureCoordinate);

    if (uRenderingMode != RENDER_MODE_DVR) {
      if (intensity < uIntensityBounds.x || intensity > uIntensityBounds.y) {
        samplePosition += stepVector;
        continue;
      }
      if (projectionSampleCount < 0.5) {
        projectedIntensity = intensity;
      } else if (uRenderingMode == RENDER_MODE_MIP) {
        projectedIntensity = max(projectedIntensity, intensity);
      } else if (uRenderingMode == RENDER_MODE_MINIP) {
        projectedIntensity = min(projectedIntensity, intensity);
      } else if (uRenderingMode == RENDER_MODE_AVERAGE) {
        projectedIntensity += intensity;
      }
      projectionSampleCount += 1.0;
      samplePosition += stepVector;
      continue;
    }

    if (intensity < uIntensityBounds.x || intensity > uIntensityBounds.y) {
      samplePosition += stepVector;
      continue;
    }
    float displayIntensity = mix(
      uIntensityBounds.x,
      uIntensityBounds.y,
      windowMedicalIntensity(intensity)
    );
    vec4 transferSample = sampleMedicalTransfer(displayIntensity);
    float boundaryWeight = opacityBoundaryWeight(intensity);
    vec3 patientGradient = vec3(0.0);
    float edgeOpacityWeight = 1.0;
    if (
      transferSample.a * boundaryWeight > 0.002
      && (uEdgeDefinition > 0.0001 || uShadingStrength > 0.0001)
    ) {
      patientGradient = patientSpaceMedicalGradient(textureCoordinate);
      edgeOpacityWeight = edgeDefinitionOpacityWeight(patientGradient);
    }
    vec3 sampleColor = applyMedicalDepthShading(
      transferSample.rgb,
      patientGradient,
      direction
    );
    float sampleAlpha = 1.0 - exp(
      -transferSample.a
      * boundaryWeight
      * edgeOpacityWeight
      * uDensityScale
      * uGlobalOpacity
      * stepLength
    );
    float remaining = 1.0 - accumulated.a;
    accumulated.rgb += remaining * sampleAlpha * sampleColor;
    accumulated.a += remaining * sampleAlpha;
    if (accumulated.a >= 0.98) break;
    samplePosition += stepVector;
  }

  if (uRenderingMode != RENDER_MODE_DVR) {
    if (projectionSampleCount < 0.5) discard;
    if (uRenderingMode == RENDER_MODE_AVERAGE) {
      projectedIntensity /= projectionSampleCount;
    }
    projectedIntensity = clamp(
      projectedIntensity,
      uIntensityBounds.x,
      uIntensityBounds.y
    );
    float projectedDisplayIntensity = windowMedicalIntensity(projectedIntensity);
    float projectionAlpha = clamp(uGlobalOpacity, 0.0, 1.0);
    if (projectionAlpha <= 0.001) discard;
    vec3 projectionColor = vec3(projectedDisplayIntensity);
    outColor = vec4(projectionColor * projectionAlpha, projectionAlpha);
    return;
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
    windowMode: "absolute",
    window: Object.freeze([40, 400]),
    densityScale: 12.0,
    opacitySoftness: 0.30,
    edgeDefinition: 0.25,
    shadingStrength: 0.35,
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
    windowMode: "absolute",
    window: Object.freeze([40, 400]),
    densityScale: 14.0,
    opacitySoftness: 0.45,
    edgeDefinition: 0.30,
    shadingStrength: 0.35,
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
    windowMode: "absolute",
    window: Object.freeze([500, 1500]),
    densityScale: 12.0,
    opacitySoftness: 0.18,
    edgeDefinition: 0.60,
    shadingStrength: 0.55,
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
    windowMode: "absolute",
    window: Object.freeze([-600, 1500]),
    densityScale: 10.0,
    opacitySoftness: 0.40,
    edgeDefinition: 0.35,
    shadingStrength: 0.25,
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
    windowMode: "relative",
    window: Object.freeze([0.03, 0.98]),
    densityScale: 10.0,
    opacitySoftness: 0.35,
    edgeDefinition: 0.25,
    shadingStrength: 0.30,
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
    windowMode: "relative",
    window: Object.freeze([0.02, 0.68]),
    densityScale: 11.0,
    opacitySoftness: 0.40,
    edgeDefinition: 0.30,
    shadingStrength: 0.25,
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
    windowMode: "relative",
    window: Object.freeze([0.24, 0.98]),
    densityScale: 10.0,
    opacitySoftness: 0.30,
    edgeDefinition: 0.40,
    shadingStrength: 0.35,
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
    windowMode: "relative",
    window: Object.freeze([0.05, 0.95]),
    densityScale: 9.0,
    opacitySoftness: 0.35,
    edgeDefinition: 0.25,
    shadingStrength: 0.30,
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

function resolvedPresetWindow(preset, sourceLow, sourceHigh) {
  const span = sourceHigh - sourceLow;
  if (preset.windowMode === "relative") {
    const low = sourceLow + span * preset.window[0];
    const high = sourceLow + span * preset.window[1];
    return [(low + high) / 2, high - low];
  }
  return [preset.window[0], preset.window[1]];
}

function normalizedDisplayParameter(value, fallback, field) {
  if (value === undefined) return fallback;
  const normalized = finiteNumber(value, `transfer-function ${field}`);
  if (normalized < 0 || normalized > 1) {
    throw new TypeError(`Patient volume transfer-function ${field} is invalid`);
  }
  return normalized;
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
  const [presetWindowCenter, presetWindowWidth] = resolvedPresetWindow(
    preset,
    sourceLow,
    sourceHigh,
  );
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

  const requestedWindowCenter = adjustments.windowCenter === undefined
    ? presetWindowCenter
    : finiteNumber(adjustments.windowCenter, "transfer-function window center");
  const requestedWindowWidth = adjustments.windowWidth === undefined
    ? presetWindowWidth
    : finiteNumber(adjustments.windowWidth, "transfer-function window width");
  if (requestedWindowWidth < minimumInterval) {
    throw new TypeError("Patient volume transfer-function window width is invalid");
  }
  const windowCenter = Math.max(sourceLow, Math.min(sourceHigh, requestedWindowCenter));
  const windowWidth = Math.max(
    minimumInterval,
    Math.min((sourceHigh - sourceLow) * 2, requestedWindowWidth),
  );

  const densityMultiplier = adjustments.densityMultiplier === undefined
    ? 1
    : finiteNumber(adjustments.densityMultiplier, "transfer-function density");
  if (densityMultiplier < 0.25 || densityMultiplier > 2) {
    throw new TypeError("Patient volume transfer-function density is invalid");
  }

  const opacitySoftness = normalizedDisplayParameter(adjustments.opacitySoftness,
    preset.opacitySoftness, "opacity softness");
  const edgeDefinition = normalizedDisplayParameter(adjustments.edgeDefinition,
    preset.edgeDefinition, "edge definition");
  const shadingStrength = normalizedDisplayParameter(adjustments.shadingStrength,
    preset.shadingStrength, "shading strength");

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
    windowCenter,
    windowWidth,
    densityMultiplier,
    densityScale: preset.densityScale * densityMultiplier,
    opacitySoftness,
    edgeDefinition,
    shadingStrength,
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
  material.uniforms.uWindowCenter.value = transfer.windowCenter;
  material.uniforms.uWindowWidth.value = transfer.windowWidth;
  material.uniforms.uIntensityBounds.value.set(transfer.rangeLow, transfer.rangeHigh, 0);
  material.uniforms.uDensityScale.value = transfer.densityScale;
  material.uniforms.uOpacitySoftness.value = transfer.opacitySoftness;
  material.uniforms.uEdgeDefinition.value = transfer.edgeDefinition;
  material.uniforms.uShadingStrength.value = transfer.shadingStrength;
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
    const renderingMode = medicalRenderingMode("dvr");
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
        uWindowCenter: { value: transfer.windowCenter },
        uWindowWidth: { value: transfer.windowWidth },
        uIntensityBounds: {
          value: new THREE.Vector3(transfer.rangeLow, transfer.rangeHigh, 0),
        },
        uDensityScale: { value: transfer.densityScale },
        uGlobalOpacity: { value: 1 },
        uSamplingRate: { value: Math.min(Math.max(...dimensions), DEFAULT_SAMPLE_RATE) },
        uTextureTexelSize: {
          value: new THREE.Vector3(
            1 / dimensions[0],
            1 / dimensions[1],
            1 / dimensions[2],
          ),
        },
        uOpacitySoftness: { value: transfer.opacitySoftness },
        uEdgeDefinition: { value: transfer.edgeDefinition },
        uShadingStrength: { value: transfer.shadingStrength },
        uRenderingMode: { value: renderingMode.code },
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
      renderingModeState: { current: renderingMode },
      clippingState: { current: clipping },
      qualityState: {
        samplingRate: Math.min(Math.max(...dimensions), DEFAULT_SAMPLE_RATE),
      },
    });
    this.current = resource;
    return resource;
  }

  setOpacity(value) {
    if (!this.current) return;
    const opacity = Math.min(1, Math.max(0, finiteNumber(value, "opacity")));
    this.current.material.uniforms.uGlobalOpacity.value = opacity;
  }

  setSamplingRate(value) {
    if (!this.current) return null;
    const samplingRate = Math.round(Math.min(
      MAX_RAY_STEPS,
      Math.max(MIN_RAY_SAMPLING_RATE, finiteNumber(value, "sampling rate")),
    ));
    this.current.material.uniforms.uSamplingRate.value = samplingRate;
    this.current.qualityState.samplingRate = samplingRate;
    return samplingRate;
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

  setRenderingMode(modeId) {
    if (!this.current) {
      throw new TypeError("A patient volume must be active before changing its rendering mode");
    }
    const mode = medicalRenderingMode(modeId);
    const uniforms = this.current.material.uniforms;
    uniforms.uRenderingMode.value = mode.code;
    this.current.material.uniformsNeedUpdate = true;
    this.current.renderingModeState.current = mode;
    return mode;
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
