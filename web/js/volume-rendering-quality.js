const LIGHT_VOLUME_VOXELS = 64 * 1024 * 1024;
const BALANCED_VOLUME_VOXELS = 192 * 1024 * 1024;
const DEFAULT_SETTLE_DELAY_MS = 180;
const DEFAULT_TARGET_FRAME_MS = 1000 / 30;
const MAX_QUALIFIED_RAY_SAMPLES = 512;
export const FRAME_PRESSURE_SAMPLE_COUNT = 12;
export const FRAME_PRESSURE_THRESHOLD = 1.2;

export const RENDERING_QUALITY_POLICIES = Object.freeze([
  Object.freeze({ id: "interactive", label: "Interactive" }),
  Object.freeze({ id: "balanced", label: "Balanced" }),
  Object.freeze({ id: "high", label: "High" }),
  Object.freeze({ id: "maximum", label: "Maximum" }),
]);

const QUALITY_POLICY_SETTINGS = Object.freeze({
  interactive: Object.freeze({
    settledLimits: Object.freeze([256, 192, 144]),
    interactiveLimits: Object.freeze([144, 112, 96]),
    settledPixelRatios: Object.freeze([1, 1, 0.9]),
    interactivePixelRatios: Object.freeze([0.9, 0.85, 0.8]),
  }),
  balanced: Object.freeze({
    settledLimits: Object.freeze([384, 352, 320]),
    interactiveLimits: Object.freeze([256, 192, 144]),
    settledPixelRatios: Object.freeze([2, 1.5, 1.25]),
    interactivePixelRatios: Object.freeze([1, 1, 0.9]),
  }),
  high: Object.freeze({
    settledLimits: Object.freeze([448, 416, 384]),
    interactiveLimits: Object.freeze([288, 224, 176]),
    settledPixelRatios: Object.freeze([2, 1.75, 1.5]),
    interactivePixelRatios: Object.freeze([1.1, 1, 1]),
  }),
  maximum: Object.freeze({
    settledLimits: Object.freeze([512, 512, 448]),
    interactiveLimits: Object.freeze([320, 256, 192]),
    settledPixelRatios: Object.freeze([2, 2, 1.75]),
    interactivePixelRatios: Object.freeze([1.25, 1.1, 1]),
  }),
});

export function normalizeRenderingQualityPolicy(policy = "balanced") {
  const normalized = String(policy || "balanced").toLowerCase();
  if (!Object.prototype.hasOwnProperty.call(QUALITY_POLICY_SETTINGS, normalized)) {
    throw new TypeError("Adaptive rendering quality policy is invalid");
  }
  return normalized;
}

function positiveFinite(value, field) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    throw new TypeError(`Adaptive rendering ${field} is invalid`);
  }
  return number;
}

function textureDimensions(descriptor) {
  const dimensions = descriptor?.texture_dimensions;
  if (!descriptor?.ready || !Array.isArray(dimensions) || dimensions.length !== 3) {
    throw new TypeError("Adaptive rendering requires a ready patient volume descriptor");
  }
  const normalized = dimensions.map((value) => Number(value));
  if (!normalized.every((value) => Number.isInteger(value) && value > 0)) {
    throw new TypeError("Adaptive rendering texture dimensions are invalid");
  }
  return normalized;
}

function devicePixelRatioLimit(value) {
  return Math.min(2, Math.max(1, positiveFinite(value || 1, "device pixel ratio")));
}

export function createAdaptiveRenderingProfile(
  descriptor,
  capabilities = {},
  devicePixelRatio = 1,
  policy = "balanced",
) {
  const dimensions = textureDimensions(descriptor);
  const voxelCount = dimensions.reduce((total, value) => total * value, 1);
  if (!Number.isSafeInteger(voxelCount)) {
    throw new TypeError("Adaptive rendering voxel count is invalid");
  }
  const maximumDimension = Math.max(...dimensions);
  const textureLimit = Number(capabilities?.max3dTextureSize || maximumDimension);
  if (capabilities?.ready === false || maximumDimension > textureLimit) {
    throw new TypeError("Adaptive rendering volume exceeds the qualified GPU profile");
  }

  let workload;
  let workloadIndex;
  if (voxelCount <= LIGHT_VOLUME_VOXELS) {
    workload = "light";
    workloadIndex = 0;
  } else if (voxelCount <= BALANCED_VOLUME_VOXELS) {
    workload = "balanced";
    workloadIndex = 1;
  } else {
    workload = "heavy";
    workloadIndex = 2;
  }

  const normalizedPolicy = normalizeRenderingQualityPolicy(policy);
  const policySettings = QUALITY_POLICY_SETTINGS[normalizedPolicy];
  const settledLimit = policySettings.settledLimits[workloadIndex];
  const interactiveLimit = policySettings.interactiveLimits[workloadIndex];
  const settledPixelRatioLimit = policySettings.settledPixelRatios[workloadIndex];
  const interactivePixelRatioLimit = policySettings.interactivePixelRatios[workloadIndex];
  const qualifiedPixelRatio = devicePixelRatioLimit(devicePixelRatio);
  const settledSamplingRate = Math.min(
    maximumDimension,
    MAX_QUALIFIED_RAY_SAMPLES,
    settledLimit,
  );
  const interactiveSamplingRate = Math.min(settledSamplingRate, interactiveLimit);
  const minimumInteractiveSamplingRate = Math.max(
    64,
    Math.min(interactiveSamplingRate, Math.round(interactiveSamplingRate * 0.5)),
  );

  return Object.freeze({
    policy: normalizedPolicy,
    workload,
    textureDimensions: Object.freeze(dimensions),
    voxelCount,
    maximumDimension,
    settledSamplingRate,
    interactiveSamplingRate,
    minimumInteractiveSamplingRate,
    settledPixelRatio: Math.min(qualifiedPixelRatio, settledPixelRatioLimit),
    interactivePixelRatio: Math.min(qualifiedPixelRatio, interactivePixelRatioLimit),
    settleDelayMs: DEFAULT_SETTLE_DELAY_MS,
    targetFrameMs: DEFAULT_TARGET_FRAME_MS,
  });
}

export class AdaptiveVolumeRenderingQuality {
  constructor({
    renderer,
    rayMarcher,
    devicePixelRatio = 1,
    now = () => performance.now(),
    requestRender = () => {},
    onStateChange = () => {},
    policy = "balanced",
  }) {
    if (!renderer?.setPixelRatio || !rayMarcher?.setSamplingRate) {
      throw new TypeError("Adaptive rendering requires renderer and ray marcher controls");
    }
    this.renderer = renderer;
    this.rayMarcher = rayMarcher;
    this.devicePixelRatio = devicePixelRatioLimit(devicePixelRatio);
    this.now = now;
    this.requestRender = requestRender;
    this.onStateChange = onStateChange;
    this.policy = normalizeRenderingQualityPolicy(policy);
    this.descriptor = null;
    this.capabilities = null;
    this.profile = null;
    this.mode = "inactive";
    this.samplingRate = null;
    this.pixelRatio = this.devicePixelRatio;
    this.activeInteractions = new Set();
    this.settleDeadline = null;
    this.frameSamples = [];
  }

  activate(descriptor, capabilities, policy = this.policy) {
    this.policy = normalizeRenderingQualityPolicy(policy);
    this.descriptor = descriptor;
    this.capabilities = capabilities;
    this.profile = createAdaptiveRenderingProfile(
      descriptor,
      capabilities,
      this.devicePixelRatio,
      this.policy,
    );
    this.activeInteractions.clear();
    this.settleDeadline = null;
    this.frameSamples = [];
    this.applyMode("settled");
    return this.snapshot();
  }

  deactivate() {
    this.profile = null;
    this.mode = "inactive";
    this.samplingRate = null;
    this.pixelRatio = this.devicePixelRatio;
    this.renderer.setPixelRatio(this.pixelRatio);
    this.activeInteractions.clear();
    this.settleDeadline = null;
    this.frameSamples = [];
    this.descriptor = null;
    this.capabilities = null;
    this.requestRender();
    this.onStateChange(this.snapshot());
  }

  setPolicy(policy) {
    this.policy = normalizeRenderingQualityPolicy(policy);
    if (!this.descriptor) {
      this.onStateChange(this.snapshot());
      return this.snapshot();
    }
    return this.activate(this.descriptor, this.capabilities, this.policy);
  }

  beginInteraction(source = "viewer") {
    if (!this.profile) return false;
    this.activeInteractions.add(String(source));
    this.settleDeadline = null;
    return this.applyMode("interactive");
  }

  endInteraction(source = "viewer") {
    if (!this.profile) return false;
    this.activeInteractions.delete(String(source));
    if (this.activeInteractions.size === 0) {
      this.settleDeadline = this.now() + this.profile.settleDelayMs;
    }
    return false;
  }

  pulseInteraction(source = "control") {
    if (!this.profile) return false;
    this.activeInteractions.delete(String(source));
    const changed = this.applyMode("interactive");
    this.settleDeadline = this.now() + this.profile.settleDelayMs;
    return changed;
  }

  update(timestamp = this.now()) {
    if (
      !this.profile
      || this.mode !== "interactive"
      || this.activeInteractions.size > 0
      || this.settleDeadline === null
      || Number(timestamp) < this.settleDeadline
    ) {
      return false;
    }
    this.settleDeadline = null;
    return this.applyMode("settled");
  }

  recordFrameDuration(frameMs) {
    if (!this.profile || this.mode !== "interactive") return false;
    const duration = Number(frameMs);
    if (!Number.isFinite(duration) || duration <= 0 || duration > 1000) return false;
    this.frameSamples.push(duration);
    if (this.frameSamples.length < FRAME_PRESSURE_SAMPLE_COUNT) return false;
    const average = this.frameSamples.reduce((total, value) => total + value, 0)
      / this.frameSamples.length;
    this.frameSamples = [];
    if (average <= this.profile.targetFrameMs * FRAME_PRESSURE_THRESHOLD) return false;

    const nextSamplingRate = Math.max(
      this.profile.minimumInteractiveSamplingRate,
      Math.floor(this.samplingRate * 0.85),
    );
    if (nextSamplingRate >= this.samplingRate) return false;
    this.samplingRate = this.rayMarcher.setSamplingRate(nextSamplingRate);
    this.requestRender();
    this.onStateChange(this.snapshot());
    return true;
  }

  isInteractive() {
    return this.mode === "interactive";
  }

  applyMode(mode) {
    if (!this.profile) return false;
    const next = mode === "interactive"
      ? {
        mode: "interactive",
        samplingRate: this.profile.interactiveSamplingRate,
        pixelRatio: this.profile.interactivePixelRatio,
      }
      : {
        mode: "settled",
        samplingRate: this.profile.settledSamplingRate,
        pixelRatio: this.profile.settledPixelRatio,
      };
    const changed = this.mode !== next.mode
      || this.samplingRate !== next.samplingRate
      || this.pixelRatio !== next.pixelRatio;
    this.mode = next.mode;
    this.samplingRate = this.rayMarcher.setSamplingRate(next.samplingRate);
    this.pixelRatio = next.pixelRatio;
    this.renderer.setPixelRatio(next.pixelRatio);
    this.frameSamples = [];
    this.requestRender();
    this.onStateChange(this.snapshot());
    return changed;
  }

  snapshot() {
    return Object.freeze({
      policy: this.policy,
      mode: this.mode,
      workload: this.profile?.workload || null,
      samplingRate: this.samplingRate,
      pixelRatio: this.pixelRatio,
      minimumInteractiveSamplingRate:
        this.profile?.minimumInteractiveSamplingRate || null,
      settleDelayMs: this.profile?.settleDelayMs || null,
      targetFrameMs: this.profile?.targetFrameMs || null,
    });
  }
}
