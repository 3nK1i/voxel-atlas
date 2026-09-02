const MAX_RAY_STEPS = 512;
const INTERACTIVE_SAMPLE_RATE = 384;

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
uniform float uIntensityLow;
uniform float uIntensityHigh;
uniform float uAbsorption;
uniform float uGlobalOpacity;
uniform float uSamplingRate;
uniform vec3 uColorLow;
uniform vec3 uColorHigh;

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

float decodeMedicalIntensity(vec3 textureCoordinate) {
  vec2 encoded = texture(uVolume, textureCoordinate).rg;
  float lowByte = floor(encoded.r * 255.0 + 0.5);
  float highByte = floor(encoded.g * 255.0 + 0.5);
  return uDecodeOffset + uDecodeScale * (lowByte + highByte * 256.0);
}

void main() {
  vec3 direction = normalize(vRayDirection);
  vec2 intersection = intersectUnitBox(vRayOrigin, direction);
  float entry = max(intersection.x, 0.0);
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
    float density = smoothstep(uIntensityLow, uIntensityHigh, intensity);
    float sampleAlpha = 1.0 - exp(
      -density * uAbsorption * uGlobalOpacity * stepLength
    );
    vec3 sampleColor = mix(uColorLow, uColorHigh, density);
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
    extentMm: Object.freeze(extentMm.map(stableNumber)),
    normalizedExtent: Object.freeze(extentMm.map((value) => stableNumber(value * scale))),
    maximumExtentMm: stableNumber(maximumExtentMm),
    viewerCenterLpsMm: Object.freeze(center.map(stableNumber)),
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

export function selectBaselineTransferFunction(descriptor) {
  const [sourceLow, sourceHigh] = sourceRange(descriptor);
  const span = Math.max(sourceHigh - sourceLow, 1);
  const modality = String(descriptor?.source_modality || "").toUpperCase();
  const units = String(descriptor?.source_intensity_units || "");
  if (modality === "CT" && units === "HU") {
    let intensityLow = Math.max(sourceLow, -250);
    let intensityHigh = Math.min(sourceHigh, 900);
    if (intensityHigh <= intensityLow) {
      intensityLow = sourceLow - 0.5;
      intensityHigh = sourceHigh + 0.5;
    }
    return Object.freeze({
      modality,
      units,
      intensityLow,
      intensityHigh,
      absorption: 7.5,
      colorLow: Object.freeze([0.38, 0.44, 0.50]),
      colorHigh: Object.freeze([1.0, 0.91, 0.78]),
    });
  }
  if (sourceHigh === sourceLow) {
    return Object.freeze({
      modality: modality || "UNKNOWN",
      units: units || "modality",
      intensityLow: sourceLow - 0.5,
      intensityHigh: sourceHigh + 0.5,
      absorption: 7.0,
      colorLow: Object.freeze([0.30, 0.38, 0.48]),
      colorHigh: Object.freeze([0.92, 0.96, 1.0]),
    });
  }
  return Object.freeze({
    modality: modality || "UNKNOWN",
    units: units || "modality",
    intensityLow: sourceLow + span * 0.12,
    intensityHigh: sourceLow + span * 0.82,
    absorption: 7.0,
    colorLow: Object.freeze([0.30, 0.38, 0.48]),
    colorHigh: Object.freeze([0.92, 0.96, 1.0]),
  });
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
    if (!three?.BoxGeometry || !three?.ShaderMaterial || !three?.Mesh || !three?.Group) {
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
        uIntensityLow: { value: transfer.intensityLow },
        uIntensityHigh: { value: transfer.intensityHigh },
        uAbsorption: { value: transfer.absorption },
        uGlobalOpacity: { value: 1 },
        uSamplingRate: { value: Math.min(Math.max(...dimensions), INTERACTIVE_SAMPLE_RATE) },
        uColorLow: { value: transfer.colorLow },
        uColorHigh: { value: transfer.colorHigh },
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
    });
    this.current = resource;
    return resource;
  }

  setOpacity(value) {
    if (!this.current) return;
    const opacity = Math.min(1, Math.max(0, finiteNumber(value, "opacity")));
    this.current.material.uniforms.uGlobalOpacity.value = opacity;
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
