const VOLUME_MEDIA_TYPE = "application/x-voxelatlas-volume-rg8";
const SHA256_PATTERN = /^[0-9a-f]{64}$/;


export class VolumeTextureLoadError extends Error {
  constructor(message) {
    super(message);
    this.name = "VolumeTextureLoadError";
  }
}


function requireDescriptor(descriptor) {
  if (!descriptor?.ready || descriptor.encoding !== "linear_uint16_rg8") {
    throw new VolumeTextureLoadError("Patient volume texture descriptor is unavailable");
  }
  if (!SHA256_PATTERN.test(String(descriptor.revision || ""))) {
    throw new VolumeTextureLoadError("Patient volume texture revision is invalid");
  }
  if (!SHA256_PATTERN.test(String(descriptor.artifact_sha256 || ""))) {
    throw new VolumeTextureLoadError("Patient volume texture SHA256 is invalid");
  }
  if (
    descriptor.component_type !== "uint8"
    || Number(descriptor.bytes_per_voxel) !== 2
    || descriptor.component_order?.join(",") !== "low_byte,high_byte"
  ) {
    throw new VolumeTextureLoadError("Patient volume texture component layout is unsupported");
  }
  if (!Array.isArray(descriptor.texture_dimensions) || descriptor.texture_dimensions.length !== 3) {
    throw new VolumeTextureLoadError("Patient volume texture dimensions are invalid");
  }
  const dimensions = descriptor.texture_dimensions.map(Number);
  if (!dimensions.every((value) => Number.isInteger(value) && value > 0)) {
    throw new VolumeTextureLoadError("Patient volume texture dimensions are invalid");
  }
  const expectedLength = dimensions.reduce((total, value) => total * value, 2);
  if (!Number.isSafeInteger(expectedLength) || expectedLength !== Number(descriptor.byte_length)) {
    throw new VolumeTextureLoadError("Patient volume texture byte length is inconsistent");
  }
  return dimensions;
}


function requireHeader(response, name, expected, message) {
  const actual = String(response.headers.get(name) || "").trim().toLowerCase();
  if (actual !== String(expected).toLowerCase()) {
    throw new VolumeTextureLoadError(message);
  }
}


async function sha256Hex(buffer, crypto) {
  if (!crypto?.subtle?.digest) {
    throw new VolumeTextureLoadError("Browser SHA256 verification is unavailable");
  }
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (value) => (
    value.toString(16).padStart(2, "0")
  )).join("");
}


export class PatientVolumeTextureManager {
  constructor({
    three,
    fetchImpl = globalThis.fetch,
    cryptoImpl = globalThis.crypto,
    initializeTexture = null,
  }) {
    if (!three?.Data3DTexture) {
      throw new TypeError("Three.js Data3DTexture support is required");
    }
    if (typeof fetchImpl !== "function") {
      throw new TypeError("A browser fetch implementation is required");
    }
    this.three = three;
    this.fetchImpl = fetchImpl.bind(globalThis);
    this.crypto = cryptoImpl;
    this.initializeTexture = initializeTexture;
    this.current = null;
    this._controller = null;
    this._generation = 0;
  }

  dispose() {
    this._generation += 1;
    if (this._controller) {
      this._controller.abort();
      this._controller = null;
    }
    if (this.current?.texture) {
      this.current.texture.dispose();
    }
    this.current = null;
  }

  async load(descriptor) {
    const [width, height, depth] = requireDescriptor(descriptor);
    this.dispose();
    const generation = this._generation;
    const controller = new AbortController();
    this._controller = controller;
    let texture = null;

    try {
      const url = "/api/studies/latest/volume-rendering/data"
        + `?revision=${encodeURIComponent(descriptor.revision)}`;
      const response = await this.fetchImpl(url, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Accept": VOLUME_MEDIA_TYPE },
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new VolumeTextureLoadError(
          `Patient volume texture download failed (${response.status})`,
        );
      }

      const mediaType = String(response.headers.get("Content-Type") || "")
        .split(";", 1)[0]
        .trim()
        .toLowerCase();
      if (mediaType !== VOLUME_MEDIA_TYPE) {
        throw new VolumeTextureLoadError("Patient volume texture media type is invalid");
      }
      requireHeader(
        response,
        "X-VoxelAtlas-Volume-Revision",
        descriptor.revision,
        "Patient volume texture revision header does not match",
      );
      requireHeader(
        response,
        "X-VoxelAtlas-Volume-SHA256",
        descriptor.artifact_sha256,
        "Patient volume texture SHA256 header does not match",
      );
      requireHeader(
        response,
        "X-Content-Type-Options",
        "nosniff",
        "Patient volume texture response is missing nosniff protection",
      );
      if (!String(response.headers.get("Cache-Control") || "").toLowerCase().includes("no-store")) {
        throw new VolumeTextureLoadError("Patient volume texture response is cacheable");
      }
      const contentLength = Number(response.headers.get("Content-Length"));
      if (!Number.isSafeInteger(contentLength) || contentLength !== Number(descriptor.byte_length)) {
        throw new VolumeTextureLoadError("Patient volume texture content length does not match");
      }

      const buffer = await response.arrayBuffer();
      if (buffer.byteLength !== Number(descriptor.byte_length)) {
        throw new VolumeTextureLoadError("Patient volume texture byte length does not match");
      }
      const artifactSha256 = await sha256Hex(buffer, this.crypto);
      if (artifactSha256 !== descriptor.artifact_sha256) {
        throw new VolumeTextureLoadError("Patient volume texture SHA256 verification failed");
      }
      if (controller.signal.aborted || generation !== this._generation) {
        throw new DOMException("Patient volume texture load was superseded", "AbortError");
      }

      const data = new Uint8Array(buffer);
      texture = new this.three.Data3DTexture(data, width, height, depth);
      texture.name = `Patient volume ${descriptor.revision.slice(0, 12)}`;
      texture.format = this.three.RGFormat;
      texture.type = this.three.UnsignedByteType;
      texture.internalFormat = "RG8";
      texture.minFilter = this.three.NearestFilter;
      texture.magFilter = this.three.NearestFilter;
      texture.wrapS = this.three.ClampToEdgeWrapping;
      texture.wrapT = this.three.ClampToEdgeWrapping;
      texture.wrapR = this.three.ClampToEdgeWrapping;
      texture.generateMipmaps = false;
      texture.unpackAlignment = 1;
      texture.flipY = false;
      texture.colorSpace = this.three.NoColorSpace;
      texture.needsUpdate = true;

      if (typeof this.initializeTexture === "function") {
        await this.initializeTexture(texture);
      }
      if (controller.signal.aborted || generation !== this._generation) {
        throw new DOMException("Patient volume texture load was superseded", "AbortError");
      }

      const resource = Object.freeze({
        texture,
        descriptor,
        revision: descriptor.revision,
        artifactSha256,
        byteLength: buffer.byteLength,
        dimensions: Object.freeze([width, height, depth]),
      });
      this.current = resource;
      texture = null;
      return resource;
    } catch (error) {
      if (texture) texture.dispose();
      if (error?.name === "AbortError" || error instanceof VolumeTextureLoadError) {
        throw error;
      }
      throw new VolumeTextureLoadError("Patient volume texture could not be loaded");
    } finally {
      if (this._controller === controller) {
        this._controller = null;
      }
    }
  }
}
