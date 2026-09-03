const SAFE_SAMPLE_ID = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;

function requiredText(value, field, maximum = 280) {
  if (typeof value !== "string") {
    throw new Error(`Invalid sample catalog ${field}`);
  }
  const text = value.trim();
  if (!text || text.length > maximum) {
    throw new Error(`Invalid sample catalog ${field}`);
  }
  return text;
}

function httpsUrl(value, field) {
  const url = requiredText(value, field, 2048);
  if (!url.startsWith("https://") || /\s/.test(url)) {
    throw new Error(`Invalid sample catalog ${field}`);
  }
  return url;
}

function sameOriginPreview(value) {
  if (value === null || value === undefined) {
    return null;
  }
  const url = requiredText(value, "preview URL", 256);
  if (!/^\/api\/sample-studies\/[a-z0-9-]+\/preview$/.test(url)) {
    throw new Error("Invalid sample catalog preview URL");
  }
  return url;
}

function normalizeSample(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("Invalid sample catalog item");
  }
  const sampleId = requiredText(raw.sample_id, "sample ID", 64);
  if (!SAFE_SAMPLE_ID.test(sampleId)) {
    throw new Error("Invalid sample catalog sample ID");
  }
  const modality = requiredText(raw.modality, "modality", 2).toUpperCase();
  if (modality !== "CT" && modality !== "MR") {
    throw new Error("Invalid sample catalog modality");
  }
  const fileCount = Number(raw.file_count);
  const sizeBytes = Number(raw.size_bytes);
  if (!Number.isSafeInteger(fileCount) || fileCount < 1 ||
      !Number.isSafeInteger(sizeBytes) || sizeBytes < 1) {
    throw new Error("Invalid sample catalog size");
  }
  const previewAvailable = raw.preview_available === true;
  const sample = {
    sampleId,
    title: requiredText(raw.title, "title", 80),
    summary: requiredText(raw.summary, "summary"),
    modality,
    bodyRegion: requiredText(raw.body_region, "body region", 80),
    sourceLabel: requiredText(raw.source_label, "source label", 120),
    sourceUrl: httpsUrl(raw.source_url, "source URL"),
    licenseLabel: requiredText(raw.license_label, "license label", 120),
    licenseUrl: httpsUrl(raw.license_url, "license URL"),
    fileCount,
    sizeBytes,
    featured: raw.featured === true,
    previewAvailable,
    previewUrl: previewAvailable ? sameOriginPreview(raw.preview_url) : null,
  };
  return Object.freeze(sample);
}

export function normalizeSampleCatalog(payload) {
  const rawSamples = payload?.samples;
  if (!Array.isArray(rawSamples) || rawSamples.length > 12) {
    throw new Error("Invalid sample catalog response");
  }
  return Object.freeze(rawSamples.map(normalizeSample));
}

async function jsonResponse(response, fallback) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    throw new Error(payload?.detail || fallback);
  }
  return payload;
}

export class SampleStudyCatalogClient {
  constructor(options = {}) {
    const customFetch = typeof options === "function"
      ? options
      : options.fetchImpl;
    const fetchImplementation = customFetch || globalThis.fetch?.bind(globalThis);
    if (typeof fetchImplementation !== "function") {
      throw new TypeError("A fetch implementation is required");
    }
    this.fetch = fetchImplementation;
  }

  async list() {
    const response = await this.fetch("/api/sample-studies", {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    return normalizeSampleCatalog(
      await jsonResponse(response, "Sample studies could not be loaded"),
    );
  }

  async load(sampleId) {
    if (!SAFE_SAMPLE_ID.test(sampleId)) {
      throw new Error("Invalid sample study selection");
    }
    const response = await this.fetch(
      `/api/sample-studies/${encodeURIComponent(sampleId)}/load`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      },
    );
    return jsonResponse(response, "Sample study could not be opened");
  }
}
