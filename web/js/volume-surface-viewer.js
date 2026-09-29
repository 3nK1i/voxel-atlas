import {
  applyVolumeSurfaceMaterialProfile,
  createVolumeSurfaceMaterial,
  getSurfacePresentationProfile,
  resolveDirectCtSurfaceCompositionPolicy,
} from "./reconstruction-surface-presentation.js?v=phase6e-b-r1-phase6e-d-r1-phase6f-c-r3";
import {
  applySurfaceClippingToMaterial,
} from "./reconstruction-surface-clipping.js?v=phase6f-d-r1";
import { createDirectCtRegionVisibility } from "./direct-ct-region-visibility.js?v=post6f-b1b2a-r1-post6f-b1b2b-r1";

const VOLUME_SURFACE_MEDIA_TYPE = "application/x-voxelatlas-volume-surface-v1";
const VOLUME_SURFACE_MAGIC = "VXVS";
const VOLUME_SURFACE_HEADER_BYTES = 32;

function directSurfaceLabel(descriptor) {
  return descriptor?.source_modality === "MR" ? "Direct MR" : "Direct CT";
}

function directSurfaceUnits(descriptor) {
  return String(descriptor?.surface_intensity_units || "");
}

function formatIsovalue(descriptor, value) {
  const level = Number(value);
  if (!Number.isFinite(level)) return "--";
  return descriptor?.source_modality === "MR" ? level.toFixed(2) : level.toFixed(0);
}

function headerValue(response, name) {
  return String(response.headers.get(name) || "").trim();
}

async function sha256Hex(buffer, cryptoImpl) {
  if (!cryptoImpl?.subtle?.digest) throw new Error("Browser SHA256 verification is unavailable");
  const digest = await cryptoImpl.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

export function decodeVolumeSurface(buffer) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < VOLUME_SURFACE_HEADER_BYTES) {
    throw new Error("Volume-derived surface payload is truncated");
  }
  const view = new DataView(buffer);
  const magic = String.fromCharCode(...new Uint8Array(buffer, 0, 4));
  const version = view.getUint32(4, true);
  const vertexCount = view.getUint32(8, true);
  const indexCount = view.getUint32(12, true);
  const positionBytes = view.getUint32(16, true);
  const normalBytes = view.getUint32(20, true);
  const indexBytes = view.getUint32(24, true);
  const flags = view.getUint32(28, true);
  if (
    magic !== VOLUME_SURFACE_MAGIC
    || version !== 1
    || flags !== 1
    || vertexCount <= 0
    || indexCount <= 0
    || indexCount % 3 !== 0
    || positionBytes !== vertexCount * 3 * 4
    || normalBytes !== vertexCount * 3 * 4
    || indexBytes !== indexCount * 4
    || buffer.byteLength !== VOLUME_SURFACE_HEADER_BYTES + positionBytes + normalBytes + indexBytes
  ) {
    throw new Error("Volume-derived surface payload contract is invalid");
  }
  let offset = VOLUME_SURFACE_HEADER_BYTES;
  const positions = new Float32Array(buffer.slice(offset, offset + positionBytes));
  offset += positionBytes;
  const normals = new Float32Array(buffer.slice(offset, offset + normalBytes));
  offset += normalBytes;
  const indices = new Uint32Array(buffer.slice(offset));
  return Object.freeze({ version, vertexCount, triangleCount: indexCount / 3, positions, normals, indices });
}

function patientLpsToViewerMatrix(THREE, presentation) {
  const center = presentation?.viewerCenterLpsMm;
  const maximumExtentMm = Number(presentation?.maximumExtentMm);
  if (
    !Array.isArray(center) || center.length !== 3 || !center.every(Number.isFinite)
    || !Number.isFinite(maximumExtentMm) || maximumExtentMm <= 0
  ) {
    throw new Error("Patient volume presentation is unavailable for volume-derived surfaces");
  }
  const scale = 2 / maximumExtentMm;
  return new THREE.Matrix4().set(
    -scale, 0, 0, -scale * center[0],
    0, 0, scale, -scale * center[1],
    0, -scale, 0, -scale * center[2],
    0, 0, 0, 1,
  );
}

export class PatientVolumeSurfaceLayer {
  constructor({
    three,
    parent,
    fetchImpl = globalThis.fetch,
    cryptoImpl = globalThis.crypto,
    requestRender = () => {},
    readVolumePresentation = () => null,
    onStatusChange = () => {},
  }) {
    if (!three?.BufferGeometry || !three?.Mesh || !three?.MeshStandardMaterial) {
      throw new TypeError("Three.js volume-derived surface support is required");
    }
    if (!parent?.add || typeof fetchImpl !== "function") {
      throw new TypeError("Volume-derived surface layer dependencies are invalid");
    }
    this.three = three;
    this.fetchImpl = fetchImpl.bind(globalThis);
    this.crypto = cryptoImpl;
    this.requestRender = requestRender;
    this.readVolumePresentation = readVolumePresentation;
    this.onStatusChange = onStatusChange;
    this.group = new three.Group();
    this.group.name = "Patient volume-derived surface";
    this.group.userData.sourceType = "canonical_volume";
    this.group.userData.coordinateSystem = "patient_lps";
    parent.add(this.group);
    this.descriptor = null;
    this.current = null;
    this.controller = null;
    this.generation = 0;
    this.presentationVisible = true;
    this.presentationProfile = "fidelity";
    this.presentationOpacity = 1;
    this.semanticOverlayActive = false;
    this.clipping = Object.freeze({});
    this.group.visible = true;
  }

  _status(state, message, extra = {}) {
    this.onStatusChange(Object.freeze({ state, message, ...extra }));
  }

  _disposeCurrent() {
    if (!this.current) return;
    this.group.remove(this.current.mesh);
    this.current.geometry.dispose();
    this.current.material.dispose();
    this.current = null;
  }

  clearSurface() {
    this.generation += 1;
    this.controller?.abort();
    this.controller = null;
    this._disposeCurrent();
    if (this.descriptor?.available) {
      const label = directSurfaceLabel(this.descriptor);
      const parameter = this.descriptor.source_modality === "MR" ? "normalized MRI isovalue" : "CT isovalue";
      this._status("ready", `Choose a ${parameter} and build the ${label} surface.`);
    } else {
      this._status("unavailable", this.descriptor?.reason || "Volume-derived surface unavailable.");
    }
    this.requestRender();
  }

  clear() {
    this.generation += 1;
    this.controller?.abort();
    this.controller = null;
    this._disposeCurrent();
    this.descriptor = null;
    this._status("unavailable", "Volume-derived surface available after a qualified CT or MR volume is loaded.");
    this.requestRender();
  }

  setDescriptor(descriptor) {
    if (!descriptor || descriptor.source_type !== "canonical_volume") {
      this.clear();
      return;
    }
    if (this.descriptor?.study_id && this.descriptor.study_id !== descriptor.study_id) {
      this._disposeCurrent();
    }
    this.descriptor = descriptor;
    if (descriptor.available) {
      this._status("ready", `Select Surface or Combined to prepare the ${directSurfaceLabel(descriptor)} surface without segmentation.`);
    } else {
      this._status("unavailable", descriptor.reason || "Volume-derived surface unavailable.");
    }
    this.requestRender();
  }

  setPresentationVisible(visible) {
    this.presentationVisible = Boolean(visible);
    this.group.visible = this.presentationVisible;
    this.requestRender();
    return this.group.visible;
  }

  setPresentationProfile(profileId) {
    const profile = getSurfacePresentationProfile(profileId);
    this.presentationProfile = profile.id;
    if (this.current?.material) {
      applyVolumeSurfaceMaterialProfile(this.current.material, profile.id);
      this._applyPresentationOpacity();
    }
    this.requestRender();
    return this.presentationProfile;
  }

  setClippingPlanes(clipping = {}) {
    this.clipping = clipping && typeof clipping === "object"
      ? clipping
      : Object.freeze({});
    if (this.current?.material) {
      applySurfaceClippingToMaterial(
        this.current.material,
        this.three,
        this.readVolumePresentation(),
        this.clipping,
        true,
      );
    }
    this.requestRender();
    return this.clipping;
  }

  _applyPresentationOpacity() {
    if (!this.current?.material) return;
    const policy = resolveDirectCtSurfaceCompositionPolicy(
      this.presentationOpacity,
      this.semanticOverlayActive,
    );
    this.current.material.opacity = policy.opacity;
    this.current.material.transparent = policy.transparent;
    this.current.material.depthWrite = policy.depthWrite;
    this.current.material.needsUpdate = true;
  }

  setSemanticOverlayActive(active) {
    this.semanticOverlayActive = Boolean(active);
    this._applyPresentationOpacity();
    this.requestRender();
    return this.semanticOverlayActive;
  }

  setPresentationOpacity(opacity) {
    const normalized = Number(opacity);
    if (!Number.isFinite(normalized)) throw new TypeError("Direct volume surface presentation opacity must be finite");
    this.presentationOpacity = Math.min(1, Math.max(0, normalized));
    this._applyPresentationOpacity();
    this.requestRender();
    return this.presentationOpacity;
  }

  /** Bind verified per-face region evidence to the resident, exact surface. */
  bindRegionEvidence(surfaceId, faceRegions) {
    if (!this.current || surfaceId !== this.current.surfaceId) {
      throw new Error("Direct CT region evidence does not match the resident surface");
    }
    if (this.current.regionVisibility) {
      // Never rebind while a subset is drawn; restore full geometry first.
      this.current.regionVisibility.show("all");
    }
    const state = createDirectCtRegionVisibility(this.current.geometry, faceRegions);
    this.current.regionVisibility = state;
    this.requestRender();
    return Object.freeze({ available: state.available, faceCounts: state.faceCounts });
  }

  /** Fetch authenticated labels for the current exact resident CT surface, never extract. */
  async loadRegionEvidence() {
    if (this.descriptor?.source_modality !== "CT") {
      throw new Error("Direct CT region evidence is unavailable for MRI surfaces");
    }
    const target = this.current;
    if (!target?.surfaceId || !target.payloadSha256) {
      throw new Error("Direct CT surface must be resident before region qualification");
    }
    const response = await this.fetchImpl(
      `/api/studies/latest/volume-surface/regions?surface_id=${encodeURIComponent(target.surfaceId)}`,
      { credentials: "same-origin", headers: { "Accept": "application/x-voxelatlas-direct-ct-regions-v1" } },
    );
    if (!response.ok) throw new Error(`Direct CT region evidence unavailable (${response.status})`);
    const contentType = String(response.headers.get("content-type") || "").split(";", 1)[0].trim();
    const surfaceId = headerValue(response, "X-VoxelAtlas-Volume-Surface-Id");
    const surfaceSha = headerValue(response, "X-VoxelAtlas-Volume-Surface-SHA256");
    const labelsSha = headerValue(response, "X-VoxelAtlas-Region-Labels-SHA256");
    const triangleCountText = headerValue(response, "X-VoxelAtlas-Region-Triangles");
    const countsText = headerValue(response, "X-VoxelAtlas-Region-Face-Counts");
    const bodyCountText = headerValue(response, "X-VoxelAtlas-Region-Body-Count");
    if (contentType !== "application/x-voxelatlas-direct-ct-regions-v1"
        || surfaceId !== target.surfaceId || surfaceSha !== target.payloadSha256
        || !/^[0-9a-f]{64}$/.test(labelsSha)
        || triangleCountText !== String(target.triangleCount)
        || headerValue(response, "X-VoxelAtlas-Region-Classification") !== "not_anatomical"
        || !/^[0-9]+$/.test(bodyCountText) || Number(bodyCountText) < 1
        || !/^[0-9]+,[0-9]+,[0-9]+$/.test(countsText)) {
      throw new Error("Direct CT region evidence source binding is invalid");
    }
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength !== target.triangleCount || await sha256Hex(bytes, this.crypto) !== labelsSha) {
      throw new Error("Direct CT region evidence integrity verification failed");
    }
    const labels = new Uint8Array(bytes);
    const counts = [0, 0, 0];
    for (const label of labels) {
      if (label > 2) throw new Error("Direct CT region evidence has invalid face labels");
      counts[label] += 1;
    }
    if (counts.join(",") !== countsText || this.current !== target) {
      throw new Error("Direct CT region evidence does not match the resident surface");
    }
    return this.bindRegionEvidence(target.surfaceId, labels);
  }

  /** Explicit presentation-only choice; never starts a network request or rebuild. */
  setRegionDisplayMode(mode) {
    if (!this.current?.regionVisibility) {
      throw new Error("Direct CT region evidence is not available for the current surface");
    }
    const selection = this.current.regionVisibility.show(mode);
    this.requestRender();
    return selection;
  }

  async build(isovalue) {
    if (!this.descriptor?.available) throw new Error(this.descriptor?.reason || "Volume-derived surface unavailable");
    const level = Number(isovalue);
    const [minimum, maximum] = this.descriptor.surface_isovalue_range || [];
    if (!Number.isFinite(level) || !Number.isFinite(minimum) || !Number.isFinite(maximum) || !(minimum < level && level < maximum)) {
      const basis = this.descriptor.source_modality === "MR" ? "normalized MRI signal range" : "CT intensity range";
      throw new Error(`Choose an isovalue inside the ${basis}`);
    }
    const generation = ++this.generation;
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    const label = directSurfaceLabel(this.descriptor);
    const unitsLabel = this.descriptor.source_modality === "MR" ? "normalized signal" : "HU";
    this._status("loading", `Building ${label} surface at ${formatIsovalue(this.descriptor, level)} ${unitsLabel}…`, { isovalue: level });
    try {
      const response = await this.fetchImpl("/api/studies/latest/volume-surface", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Accept": VOLUME_SURFACE_MEDIA_TYPE, "Content-Type": "application/json" },
        body: JSON.stringify({ isovalue: level }),
        signal: controller.signal,
      });
      if (!response.ok) {
        let message = `Volume surface build failed (${response.status})`;
        try { const payload = await response.json(); if (payload?.detail) message = payload.detail; } catch {}
        throw new Error(message);
      }
      const contentType = String(response.headers.get("content-type") || "").split(";", 1)[0].trim();
      const surfaceId = headerValue(response, "X-VoxelAtlas-Volume-Surface-Id");
      const sourceType = headerValue(response, "X-VoxelAtlas-Volume-Surface-Source");
      const responseLevel = Number(headerValue(response, "X-VoxelAtlas-Volume-Surface-Isovalue"));
      const units = headerValue(response, "X-VoxelAtlas-Volume-Surface-Units");
      const extraction = headerValue(response, "X-VoxelAtlas-Volume-Surface-Extraction");
      const expectedSha = headerValue(response, "X-VoxelAtlas-Volume-Surface-SHA256");
      const provenanceSha = headerValue(response, "X-VoxelAtlas-Volume-Surface-Provenance-SHA256");
      const expectedVertices = Number(headerValue(response, "X-VoxelAtlas-Volume-Surface-Vertices"));
      const expectedTriangles = Number(headerValue(response, "X-VoxelAtlas-Volume-Surface-Triangles"));
      if (
        contentType !== VOLUME_SURFACE_MEDIA_TYPE
        || !/^vsurf-[0-9a-f]{32}$/.test(surfaceId)
        || sourceType !== "canonical_volume"
        || !Number.isFinite(responseLevel) || Math.abs(responseLevel - level) > 1e-6
        || units !== directSurfaceUnits(this.descriptor)
        || extraction !== "marching_cubes_isovalue"
        || !/^[0-9a-f]{64}$/.test(expectedSha)
        || !/^[0-9a-f]{64}$/.test(provenanceSha)
        || !Number.isInteger(expectedVertices) || expectedVertices <= 0
        || !Number.isInteger(expectedTriangles) || expectedTriangles <= 0
      ) {
        throw new Error("Volume-derived surface response binding is invalid");
      }
      const buffer = await response.arrayBuffer();
      const actualSha = await sha256Hex(buffer, this.crypto);
      if (actualSha !== expectedSha) throw new Error("Volume-derived surface SHA256 verification failed");
      const decoded = decodeVolumeSurface(buffer);
      if (decoded.vertexCount !== expectedVertices || decoded.triangleCount !== expectedTriangles) {
        throw new Error("Volume-derived surface geometry metadata is inconsistent");
      }
      if (generation !== this.generation || controller.signal.aborted) return null;

      const geometry = new this.three.BufferGeometry();
      geometry.setAttribute("position", new this.three.BufferAttribute(decoded.positions, 3));
      geometry.setAttribute("normal", new this.three.BufferAttribute(decoded.normals, 3));
      geometry.setIndex(new this.three.BufferAttribute(decoded.indices, 1));
      geometry.applyMatrix4(patientLpsToViewerMatrix(this.three, this.readVolumePresentation()));
      geometry.computeBoundingSphere();
      const material = createVolumeSurfaceMaterial(this.three, this.presentationProfile);
      const mesh = new this.three.Mesh(geometry, material);
      mesh.name = `Volume-derived ${this.descriptor.source_modality} surface ${formatIsovalue(this.descriptor, level)} ${units}`;
      mesh.userData.sourceType = "canonical_volume";
      mesh.userData.coordinateSystem = "patient_lps";
      mesh.userData.surfaceId = surfaceId;
      mesh.userData.provenanceSha256 = provenanceSha;
      mesh.userData.isovalue = level;
      mesh.userData.intensityUnits = units;

      const previous = this.current;
      this.current = { mesh, geometry, material, isovalue: level, triangleCount: decoded.triangleCount, surfaceId, payloadSha256: expectedSha, regionVisibility: null, sourceModality: this.descriptor.source_modality, intensityUnits: units };
      this._applyPresentationOpacity();
      applySurfaceClippingToMaterial(
        material,
        this.three,
        this.readVolumePresentation(),
        this.clipping,
        true,
      );
      this.group.add(mesh);
      if (previous) {
        this.group.remove(previous.mesh);
        previous.geometry.dispose();
        previous.material.dispose();
      }
      this._status("qualified", `${label} surface ready · ${decoded.triangleCount.toLocaleString()} triangles · ${formatIsovalue(this.descriptor, level)} ${unitsLabel}`, {
        isovalue: level,
        triangleCount: decoded.triangleCount,
        surfaceId,
      });
      this.requestRender();
      return this.current;
    } catch (error) {
      if (generation !== this.generation || error?.name === "AbortError") return null;
      this._status("error", error instanceof Error ? error.message : "Volume-derived surface build failed");
      throw error;
    } finally {
      if (this.controller === controller) this.controller = null;
    }
  }

  dispose() {
    this.clear();
    this.group.parent?.remove(this.group);
  }
}
