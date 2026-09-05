// Opt-in local engineering evidence. No patient identifiers, pixels or network calls.
export const QUALIFICATION_MODES = Object.freeze(['dvr', 'mip', 'minip', 'average', 'slice', 'thick-slab']);
export const QUALIFICATION_SLOTS = Object.freeze(['CT-1', 'MR-1', 'CT-2', 'MR-2']);
const CAPACITY = 600;

export function isQualificationLocation(location) {
  return ['http:', 'https:'].includes(location?.protocol)
    && ['localhost', '127.0.0.1', '[::1]'].includes(location?.hostname)
    && new URLSearchParams(location.search).get('qualification') === 'phase4h6';
}

function summary(values) {
  if (!values.length) return { count: 0, medianMs: null, p95Ms: null, maximumMs: null };
  const sorted = [...values].sort((a, b) => a - b);
  return {
    count: sorted.length,
    medianMs: sorted[Math.ceil(sorted.length / 2) - 1],
    p95Ms: sorted[Math.ceil(sorted.length * 0.95) - 1],
    maximumMs: sorted.at(-1),
  };
}

export class QualificationFrames {
  constructor() { this.reset(); }
  reset() {
    this.previous = null;
    this.frames = Object.fromEntries(QUALIFICATION_MODES.map((mode) => [mode, {
      total: 0, submittedCpuMs: { values: [], count: 0 }, continuousFrameIntervalMs: { values: [], count: 0 },
    }]));
  }
  pause() { this.previous = null; }
  record(timestamp, cpuMs, mode, continuous, visible) {
    if (!visible || !QUALIFICATION_MODES.includes(mode) || !Number.isFinite(timestamp)
        || !Number.isFinite(cpuMs) || cpuMs < 0) { this.pause(); return; }
    const bucket = this.frames[mode];
    const push = (ring, value) => {
      ring.values[ring.count % CAPACITY] = value;
      ring.count += 1;
    };
    bucket.total += 1;
    push(bucket.submittedCpuMs, cpuMs);
    if (continuous && this.previous?.mode === mode && timestamp > this.previous.timestamp) {
      // Do not discard slow foreground frames: that would hide rendering stalls.
      push(bucket.continuousFrameIntervalMs, timestamp - this.previous.timestamp);
    }
    this.previous = continuous ? { timestamp, mode } : null;
  }
  snapshot() {
    return Object.fromEntries(QUALIFICATION_MODES.map((mode) => [mode, {
      totalRenderedFrames: this.frames[mode].total,
      submittedCpuMs: summary(this.frames[mode].submittedCpuMs.values),
      continuousFrameIntervalMs: summary(this.frames[mode].continuousFrameIntervalMs.values),
    }]));
  }
}

// Explicit allowlist: never spread a study, descriptor, error object or URL here.
export function sanitizeRuntimeSnapshot(raw) {
  const number = (value) => Number.isFinite(value) && value >= 0 ? value : null;
  return {
    modality: ['CT', 'MR'].includes(raw.modality) ? raw.modality : null,
    dimensions: Array.isArray(raw.dimensions) && raw.dimensions.length === 3
      && raw.dimensions.every((v) => Number.isSafeInteger(v) && v > 0) ? [...raw.dimensions] : null,
    ready: raw.ready === true,
    mode: QUALIFICATION_MODES.includes(raw.mode) ? raw.mode : null,
    qualityPolicy: ['interactive', 'balanced', 'high', 'maximum'].includes(raw.qualityPolicy) ? raw.qualityPolicy : null,
    samplingRate: number(raw.samplingRate), pixelRatio: number(raw.pixelRatio),
    canvasWidth: number(raw.canvasWidth), canvasHeight: number(raw.canvasHeight),
    geometries: number(raw.geometries), textures: number(raw.textures), programs: number(raw.programs),
    shaderErrors: number(raw.shaderErrors),
    overlayNodes: number(raw.overlayNodes),
    contextLost: raw.contextLost === true,
  };
}

export function installRenderingQualification({ window: win, renderer, readSnapshot }) {
  if (!isQualificationLocation(win.location)) return null;
  const frames = new QualificationFrames();
  const captures = new Map();
  const faults = { windowErrors: 0, unhandledRejections: 0, contextLosses: 0 };
  const onError = () => { faults.windowErrors += 1; };
  const onRejection = () => { faults.unhandledRejections += 1; };
  const onLoss = () => { faults.contextLosses += 1; };
  const onVisibility = () => frames.pause();
  win.addEventListener('error', onError);
  win.addEventListener('unhandledrejection', onRejection);
  renderer.domElement.addEventListener('webglcontextlost', onLoss);
  win.document.addEventListener('visibilitychange', onVisibility);
  const report = () => ({
    schema: 'voxelatlas-phase4h6-v1',
    build: 'phase4h6',
    qualification: 'PENDING_REVIEW',
    metricMeaning: 'CPU submission and foreground continuous rendered-frame intervals; not GPU timings or VRAM bytes',
    windowCapacityPerMode: CAPACITY,
    faults: { ...faults },
    captures: QUALIFICATION_SLOTS.filter((slot) => captures.has(slot)).map((slot) => structuredClone(captures.get(slot))),
  });
  const api = Object.freeze({
    resetWindow: () => frames.reset(),
    capture: (slot) => {
      if (!QUALIFICATION_SLOTS.includes(slot)) throw new TypeError('Use CT-1, MR-1, CT-2 or MR-2');
      const runtime = sanitizeRuntimeSnapshot(readSnapshot());
      if (!runtime.ready || runtime.contextLost || !runtime.dimensions || !slot.startsWith(runtime.modality + '-')) {
        throw new Error('Load the matching CT/MR study and wait for rendering ready first');
      }
      const capture = { slot, runtime, modes: frames.snapshot() };
      captures.set(slot, capture);
      return structuredClone(capture);
    },
    report,
    download: () => {
      const blob = new Blob([JSON.stringify(report(), null, 2) + '\n'], { type: 'application/json' });
      const url = win.URL.createObjectURL(blob);
      const anchor = win.document.createElement('a');
      anchor.href = url;
      anchor.download = 'voxelatlas_phase4h6_runtime_evidence.json';
      anchor.click();
      win.setTimeout(() => win.URL.revokeObjectURL(url), 1000);
      return 'Evidence downloaded; qualification still requires review.';
    },
  });
  Object.defineProperty(win, 'voxelatlasH6', { value: api, configurable: true });
  return {
    recordFrame: (...args) => frames.record(...args),
    pause: () => frames.pause(),
    resetWindow: () => frames.reset(),
    dispose: () => {
      win.removeEventListener('error', onError);
      win.removeEventListener('unhandledrejection', onRejection);
      renderer.domElement.removeEventListener('webglcontextlost', onLoss);
      win.document.removeEventListener('visibilitychange', onVisibility);
      delete win.voxelatlasH6;
    },
  };
}
