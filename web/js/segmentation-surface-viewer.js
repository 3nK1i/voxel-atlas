import {
  applySegmentationSurfaceMaterialProfile,
  createSegmentationSurfaceMaterial,
  getSurfacePresentationProfile,
} from "./reconstruction-surface-presentation.js?v=phase6e-b-r1-phase6e-d-r1-phase6f-c-r3";
import {
  resolveStructureInteraction,
} from "./segmentation-structure-interaction.js?v=phase6f-a-r1-phase6f-b-r1";
import {
  patientLpsOffsetToViewer,
} from "./segmentation-exploded-presentation.js?v=phase6f-e-r1";
import {
  applySurfaceClippingToMaterial,
} from "./reconstruction-surface-clipping.js?v=phase6f-d-r1-phase6f-e-r1";

import { segmentationViewerWinding } from "./segmentation-viewer-winding.js?v=post6f-pre6g-b2a-r1";

const LEGACY_SURFACE_MEDIA_TYPE = "application/x-voxelatlas-surface-v1";
const ACCURATE_SURFACE_MEDIA_TYPE = "application/x-voxelatlas-surface-v2";
const SURFACE_MAGIC = "VXSF";
const LEGACY_SURFACE_HEADER_BYTES = 32;
const ACCURATE_SURFACE_HEADER_BYTES = 36;
const MAX_CONCURRENT_SURFACE_LOADS = 2;


function headerValue(response, name) {
  return String(response.headers.get(name) || "").trim();
}


async function sha256Hex(buffer, cryptoImpl) {
  if (!cryptoImpl?.subtle?.digest) {
    throw new Error("Browser SHA256 verification is unavailable");
  }
  const digest = await cryptoImpl.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (value) => (
    value.toString(16).padStart(2, "0")
  )).join("");
}


export function decodeSegmentationSurface(buffer, expected = {}) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < LEGACY_SURFACE_HEADER_BYTES) {
    throw new Error("Segmentation surface payload is truncated");
  }
  const view = new DataView(buffer);
  const magic = String.fromCharCode(...new Uint8Array(buffer, 0, 4));
  const version = view.getUint32(4, true);
  const labelId = view.getUint32(8, true);
  const vertexCount = view.getUint32(12, true);
  const indexCount = view.getUint32(16, true);
  if (
    magic !== SURFACE_MAGIC
    || labelId !== Number(expected.labelId)
    || vertexCount <= 0
    || indexCount <= 0
    || indexCount % 3 !== 0
  ) {
    throw new Error("Segmentation surface payload contract is invalid");
  }

  if (version === 1) {
    const stride = view.getUint32(20, true);
    const positionBytes = view.getUint32(24, true);
    const indexBytes = view.getUint32(28, true);
    if (
      stride <= 0
      || positionBytes !== vertexCount * 3 * 4
      || indexBytes !== indexCount * 4
      || buffer.byteLength !== LEGACY_SURFACE_HEADER_BYTES + positionBytes + indexBytes
    ) {
      throw new Error("Segmentation surface payload contract is invalid");
    }
    const positions = new Float32Array(
      buffer.slice(LEGACY_SURFACE_HEADER_BYTES, LEGACY_SURFACE_HEADER_BYTES + positionBytes),
    );
    const indices = new Uint32Array(
      buffer.slice(LEGACY_SURFACE_HEADER_BYTES + positionBytes),
    );
    return Object.freeze({
      version,
      labelId,
      vertexCount,
      triangleCount: indexCount / 3,
      stride,
      positions,
      normals: null,
      indices,
    });
  }

  if (version === 2 && buffer.byteLength >= ACCURATE_SURFACE_HEADER_BYTES) {
    const positionBytes = view.getUint32(20, true);
    const normalBytes = view.getUint32(24, true);
    const indexBytes = view.getUint32(28, true);
    const flags = view.getUint32(32, true);
    if (
      positionBytes !== vertexCount * 3 * 4
      || normalBytes !== vertexCount * 3 * 4
      || indexBytes !== indexCount * 4
      || flags !== 1
      || buffer.byteLength !== ACCURATE_SURFACE_HEADER_BYTES
        + positionBytes + normalBytes + indexBytes
    ) {
      throw new Error("Segmentation surface payload contract is invalid");
    }
    let offset = ACCURATE_SURFACE_HEADER_BYTES;
    const positions = new Float32Array(buffer.slice(offset, offset + positionBytes));
    offset += positionBytes;
    const normals = new Float32Array(buffer.slice(offset, offset + normalBytes));
    offset += normalBytes;
    const indices = new Uint32Array(buffer.slice(offset));
    return Object.freeze({
      version,
      labelId,
      vertexCount,
      triangleCount: indexCount / 3,
      stride: 1,
      positions,
      normals,
      indices,
    });
  }

  throw new Error("Segmentation surface payload contract is invalid");
}


export function patientLpsToViewerMatrix(THREE, presentation) {
  const center = presentation?.viewerCenterLpsMm;
  const maximumExtentMm = Number(presentation?.maximumExtentMm);
  if (
    !Array.isArray(center)
    || center.length !== 3
    || !center.every(Number.isFinite)
    || !Number.isFinite(maximumExtentMm)
    || maximumExtentMm <= 0
  ) {
    throw new Error("Patient volume presentation is unavailable for segmentation surfaces");
  }
  const scale = 2 / maximumExtentMm;
  return new THREE.Matrix4().set(
    -scale, 0, 0, -scale * center[0],
    0, 0, scale, -scale * center[1],
    0, -scale, 0, -scale * center[2],
    0, 0, 0, 1,
  );
}


export class PatientSegmentationSurfaceLayer {
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
      throw new TypeError("Three.js segmentation surface support is required");
    }
    if (!parent?.add || typeof fetchImpl !== "function") {
      throw new TypeError("Segmentation surface layer dependencies are invalid");
    }
    this.three = three;
    this.fetchImpl = fetchImpl.bind(globalThis);
    this.crypto = cryptoImpl;
    this.requestRender = requestRender;
    this.readVolumePresentation = readVolumePresentation;
    this.onStatusChange = onStatusChange;
    this.group = new three.Group();
    this.group.name = "Patient segmentation surfaces";
    this.group.userData.patientSpace = "DICOM Patient LPS millimetres";
    this.group.userData.presentation = "phase6c-polished-multi-structure";
    parent.add(this.group);
    this.descriptor = null;
    this.enabled = true;
    this.presentationVisible = true;
    this.presentationProfile = "fidelity";
    this.items = new Map();
    this.controllers = new Map();
    this.queue = [];
    this.activeLoads = 0;
    this.maxConcurrentLoads = MAX_CONCURRENT_SURFACE_LOADS;
    this.generation = 0;
    this.presentation = null;
    this.desiredLabels = new Set();
    this.failedLabels = new Map();
    this.clipping = Object.freeze({});
  }

  _surfaceState(labelId) {
    if (this.items.has(labelId)) return "ready";
    if (this.controllers.has(labelId)) return "building";
    if (this.queue.some((entry) => entry.labelId === labelId && entry.generation === this.generation)) {
      return "queued";
    }
    if (this.failedLabels.has(labelId)) return "failed";
    return "idle";
  }

  _surfaceStatusSnapshot() {
    const labels = [];
    const presentationStructures = this.presentation?.structures;
    if (presentationStructures instanceof Map) {
      for (const structure of presentationStructures.values()) {
        const item = this.items.get(structure.labelId) || null;
        labels.push(Object.freeze({
          labelId: structure.labelId,
          displayName: structure.displayName,
          desired: this.desiredLabels.has(structure.labelId),
          resident: Boolean(item),
          state: this._surfaceState(structure.labelId),
          quality: item?.surfaceQuality || null,
          fallback: Boolean(item?.presentationFallback),
        }));
      }
    }
    return Object.freeze(labels);
  }

  _status(state, message) {
    const labels = this._surfaceStatusSnapshot();
    const countState = (value) => labels.filter((entry) => entry.desired && entry.state === value).length;
    this.onStatusChange(Object.freeze({
      state,
      message,
      labels,
      requestedCount: this.desiredLabels.size,
      readyCount: countState("ready"),
      queuedCount: countState("queued"),
      buildingCount: countState("building"),
      failedCount: countState("failed"),
      fallbackCount: labels.filter((entry) => entry.desired && entry.fallback).length,
    }));
  }

  _disposeItem(item) {
    if (!item) return;
    this.group.remove(item.mesh);
    item.geometry.dispose();
    item.material.dispose();
  }

  _disposeAllMeshes() {
    for (const item of this.items.values()) this._disposeItem(item);
    this.items.clear();
  }

  _abortPending() {
    for (const controller of this.controllers.values()) controller.abort();
    this.controllers.clear();
    this.queue = [];
  }

  clear() {
    this.generation += 1;
    this._abortPending();
    this._disposeAllMeshes();
    this.descriptor = null;
    this.presentation = null;
    this.desiredLabels.clear();
    this.failedLabels.clear();
    this._status("unavailable", "No 3D segmentation surfaces available.");
    this.requestRender();
  }

  setDescriptor(descriptor) {
    if (
      descriptor?.ready !== true
      || descriptor.coordinate_system !== "patient_lps"
      || !Array.isArray(descriptor.present_labels)
      || !descriptor.present_labels.every((label) => Number.isInteger(label) && label > 0)
    ) {
      this.clear();
      return;
    }
    if (this.descriptor?.label_map_id !== descriptor.label_map_id) {
      this.generation += 1;
      this._abortPending();
      this._disposeAllMeshes();
      this.desiredLabels.clear();
      this.failedLabels.clear();
    }
    this.descriptor = descriptor;
    this._status("ready", "Select visible structures to add refined 3D surfaces.");
  }

  setEnabled(enabled) {
    this.enabled = Boolean(enabled);
    this.group.visible = this.enabled && this.presentationVisible;
    if (!this.enabled) {
      this._abortPending();
      this._status("disabled", "3D segmentation surfaces hidden.");
    } else {
      this._pumpQueue();
      this._updateStatus();
    }
    this.requestRender();
  }

  setPresentationVisible(visible) {
    this.presentationVisible = Boolean(visible);
    this.group.visible = this.enabled && this.presentationVisible;
    this.requestRender();
    return this.group.visible;
  }

  setPresentationProfile(profileId) {
    const profile = getSurfacePresentationProfile(profileId);
    this.presentationProfile = profile.id;
    const structures = this.presentation?.structures;
    for (const item of this.items.values()) {
      const structure = structures instanceof Map ? structures.get(item.labelId) : null;
      if (!structure) continue;
      applySegmentationSurfaceMaterialProfile(
        item.material,
        structure,
        profile.id,
        structure.labelId === this.presentation?.selectedLabelId,
      );
    }
    this.requestRender();
    return this.presentationProfile;
  }

  setClippingPlanes(clipping = {}) {
    this.clipping = clipping && typeof clipping === "object"
      ? clipping
      : Object.freeze({});
    const structures = this.presentation?.structures;
    for (const item of this.items.values()) {
      const structure = structures instanceof Map ? structures.get(item.labelId) : null;
      const interaction = structure && this.presentation
        ? resolveStructureInteraction(this.presentation, item.labelId)
        : null;
      const viewerOffset = patientLpsOffsetToViewer(
        interaction?.explodedOffsetLpsMm,
        this.readVolumePresentation(),
      );
      applySurfaceClippingToMaterial(
        item.material,
        this.three,
        this.readVolumePresentation(),
        this.clipping,
        interaction?.clippingEnabled !== false,
        viewerOffset,
      );
    }
    this.requestRender();
    return this.clipping;
  }

  _makeMaterial(structure) {
    return createSegmentationSurfaceMaterial(
      this.three,
      structure,
      this.presentationProfile,
      structure?.labelId === this.presentation?.selectedLabelId,
    );
  }

  _updateItemPresentation(item, structure, selectedLabelId) {
    const interaction = structure && this.presentation
      ? resolveStructureInteraction(this.presentation, item.labelId)
      : null;
    const shouldShow = Boolean(
      this.enabled
      && interaction?.effectiveSurfaceVisible
      && this.desiredLabels.has(item.labelId)
    );
    item.mesh.visible = shouldShow;
    if (!structure) return;
    applySegmentationSurfaceMaterialProfile(
      item.material,
      structure,
      this.presentationProfile,
      structure.labelId === selectedLabelId,
    );
    const viewerOffset = patientLpsOffsetToViewer(
      interaction.explodedOffsetLpsMm,
      this.readVolumePresentation(),
    );
    if (item.mesh.position?.set) item.mesh.position.set(...viewerOffset);
    item.mesh.userData.explodedOffsetLpsMm = [...interaction.explodedOffsetLpsMm];
    applySurfaceClippingToMaterial(
      item.material,
      this.three,
      this.readVolumePresentation(),
      this.clipping,
      interaction.clippingEnabled,
      viewerOffset,
    );
    item.mesh.renderOrder = structure.labelId === selectedLabelId ? 2 : 1;
  }

  _desiredStructures(presentation) {
    if (!presentation?.structures || !(presentation.structures instanceof Map)) return [];
    const desired = Array.from(presentation.structures.values()).filter((structure) => (
      structure.visible && structure.surfaceVisible === true
    ));
    desired.sort((left, right) => {
      if (left.labelId === presentation.selectedLabelId) return -1;
      if (right.labelId === presentation.selectedLabelId) return 1;
      return left.labelId - right.labelId;
    });
    return desired;
  }

  _updateStatus() {
    if (!this.descriptor) {
      this._status("unavailable", "No 3D segmentation surfaces available.");
      return;
    }
    if (!this.enabled) {
      this._status("disabled", "3D segmentation surfaces hidden.");
      return;
    }
    const desiredCount = this.desiredLabels.size;
    if (desiredCount === 0) {
      this._status("ready", "Select visible structures to add refined 3D surfaces.");
      return;
    }
    let readyCount = 0;
    let fallbackCount = 0;
    let triangleCount = 0;
    for (const labelId of this.desiredLabels) {
      const item = this.items.get(labelId);
      if (!item) continue;
      readyCount += 1;
      if (item.presentationFallback) fallbackCount += 1;
      triangleCount += item.triangleCount;
    }
    const failedCount = Array.from(this.failedLabels.keys())
      .filter((labelId) => this.desiredLabels.has(labelId)).length;
    const pendingCount = Math.max(0, desiredCount - readyCount - failedCount);
    if (pendingCount > 0 || this.activeLoads > 0) {
      const selectedLabelId = this.presentation?.selectedLabelId;
      const selected = this.presentation?.structures?.get(selectedLabelId);
      const selectedState = Number.isInteger(selectedLabelId)
        ? this._surfaceState(selectedLabelId)
        : "idle";
      let activity = "Building refined surfaces";
      if (selected?.displayName && selectedState === "building") {
        activity = `Building ${selected.displayName} surface…`;
      } else if (selected?.displayName && selectedState === "queued") {
        activity = `Queued ${selected.displayName} surface…`;
      }
      this._status(
        "loading",
        `${activity} · ${readyCount}/${desiredCount} ready`,
      );
      return;
    }
    if (failedCount > 0) {
      const fallbackText = fallbackCount > 0 ? ` · ${fallbackCount} accurate fallback` : "";
      this._status(
        "error",
        `${readyCount}/${desiredCount} surfaces ready${fallbackText} · ${failedCount} failed`,
      );
      return;
    }
    const noun = readyCount === 1 ? "structure" : "structures";
    if (fallbackCount > 0) {
      const refinedCount = readyCount - fallbackCount;
      this._status(
        "qualified",
        `${readyCount} ${noun} · ${refinedCount} refined · ${fallbackCount} accurate fallback · ${triangleCount.toLocaleString()} triangles`,
      );
      return;
    }
    this._status(
      "qualified",
      `${readyCount} refined ${noun} · ${triangleCount.toLocaleString()} triangles`,
    );
  }

  _enqueue(labelId, generation) {
    if (
      this.items.has(labelId)
      || this.controllers.has(labelId)
      || this.queue.some((entry) => entry.labelId === labelId && entry.generation === generation)
      || this.failedLabels.has(labelId)
    ) return;
    this.queue.push({ labelId, generation });
  }

  _pumpQueue() {
    if (!this.enabled || !this.descriptor) return;
    while (this.activeLoads < this.maxConcurrentLoads && this.queue.length > 0) {
      const entry = this.queue.shift();
      if (
        entry.generation !== this.generation
        || !this.desiredLabels.has(entry.labelId)
        || this.items.has(entry.labelId)
        || this.controllers.has(entry.labelId)
      ) continue;
      this.activeLoads += 1;
      void this._loadSurface(entry.labelId, entry.generation).finally(() => {
        this.activeLoads = Math.max(0, this.activeLoads - 1);
        this.controllers.delete(entry.labelId);
        this._pumpQueue();
        this._updateStatus();
      });
    }
  }

  async _loadSurface(labelId, generation) {
    const descriptor = this.descriptor;
    const presentationTransform = patientLpsToViewerMatrix(
      this.three,
      this.readVolumePresentation(),
    );
    const controller = new AbortController();
    this.controllers.set(labelId, controller);
    const fallbackQuality = this.descriptor.default_quality || "accurate";
    const requestedQuality = this.descriptor.presentation_quality || fallbackQuality;
    const primaryRequest = {
      label_map_id: descriptor.label_map_id,
      quality: requestedQuality,
    };

    const requestQuality = async (quality) => {
      const usesV2Surface = quality === "accurate" || quality === "refined";
      const params = new URLSearchParams({
        label_map_id: descriptor.label_map_id,
        quality,
      });
      const response = await this.fetchImpl(
        `/api/studies/latest/segmentation-surfaces/${labelId}?${params}`,
        {
          credentials: "same-origin",
          cache: "no-store",
          headers: {
            "Accept": usesV2Surface
              ? ACCURATE_SURFACE_MEDIA_TYPE
              : LEGACY_SURFACE_MEDIA_TYPE,
          },
          signal: controller.signal,
        },
      );
      return { response, quality, usesV2Surface };
    };

    try {
      let result = await requestQuality(primaryRequest.quality);
      let presentationFallback = false;
      let presentationFallbackReason = "";
      if (
        !result.response.ok
        && requestedQuality === "refined"
        && fallbackQuality === "accurate"
        && result.response.status === 422
      ) {
        const detail = await result.response.json().catch(() => ({}));
        presentationFallbackReason = String(
          detail?.detail || "Refined segmentation surface unavailable",
        );
        result = await requestQuality(fallbackQuality);
        presentationFallback = true;
      }

      const { response, quality: servedQuality, usesV2Surface } = result;
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `Segmentation surface failed (${response.status})`);
      }
      const mediaType = headerValue(response, "Content-Type").split(";", 1)[0].toLowerCase();
      const expectedMediaType = usesV2Surface
        ? ACCURATE_SURFACE_MEDIA_TYPE
        : LEGACY_SURFACE_MEDIA_TYPE;
      if (
        mediaType !== expectedMediaType
        || headerValue(response, "X-Content-Type-Options").toLowerCase() !== "nosniff"
        || !headerValue(response, "Cache-Control").toLowerCase().includes("no-store")
        || headerValue(response, "X-VoxelAtlas-Label-Map-Id") !== descriptor.label_map_id
        || Number(headerValue(response, "X-VoxelAtlas-Label-Id")) !== labelId
        || headerValue(response, "X-VoxelAtlas-Surface-Quality") !== servedQuality
      ) {
        throw new Error("Segmentation surface response binding is invalid");
      }
      const buffer = await response.arrayBuffer();
      const expectedDigest = headerValue(response, "X-VoxelAtlas-Surface-SHA256");
      if (!/^[0-9a-f]{64}$/.test(expectedDigest)) {
        throw new Error("Segmentation surface digest is invalid");
      }
      const actualDigest = await sha256Hex(buffer, this.crypto);
      if (actualDigest !== expectedDigest) {
        throw new Error("Segmentation surface SHA256 verification failed");
      }
      const decoded = decodeSegmentationSurface(buffer, { labelId });
      if (
        decoded.vertexCount !== Number(headerValue(response, "X-VoxelAtlas-Surface-Vertices"))
        || decoded.triangleCount !== Number(headerValue(response, "X-VoxelAtlas-Surface-Triangles"))
        || decoded.version !== Number(headerValue(response, "X-VoxelAtlas-Surface-Schema"))
      ) {
        throw new Error("Segmentation surface count headers do not match");
      }
      const surfaceId = headerValue(response, "X-VoxelAtlas-Surface-Id");
      const provenanceSha256 = headerValue(response, "X-VoxelAtlas-Surface-Provenance-SHA256");
      if (usesV2Surface && (
        !/^surf-[0-9a-f]{32}$/.test(surfaceId)
        || !/^[0-9a-f]{64}$/.test(provenanceSha256)
        || headerValue(response, "X-VoxelAtlas-Surface-Extraction")
          !== descriptor.accurate_surface?.extraction
        || decoded.normals === null
      )) {
        throw new Error("Patient-LPS segmentation surface provenance binding is invalid");
      }
      if (servedQuality === "refined") {
        const referenceSurfaceId = headerValue(response, "X-VoxelAtlas-Surface-Reference-Id");
        const referenceSha256 = headerValue(response, "X-VoxelAtlas-Surface-Reference-SHA256");
        const maxDisplacementMm = Number(
          headerValue(response, "X-VoxelAtlas-Surface-Max-Displacement-Mm"),
        );
        const displacementLimitMm = Number(
          headerValue(response, "X-VoxelAtlas-Surface-Displacement-Limit-Mm"),
        );
        const triangleRetention = Number(
          headerValue(response, "X-VoxelAtlas-Surface-Triangle-Retention"),
        );
        const decimationApplied = headerValue(
          response, "X-VoxelAtlas-Surface-Decimation-Applied",
        );
        const decimationCellIndex = Number(
          headerValue(response, "X-VoxelAtlas-Surface-Decimation-Cell-Index"),
        );
        const allowedCells = descriptor.refined_surface?.cluster_cell_sizes_index || [];
        if (
          headerValue(response, "X-VoxelAtlas-Surface-Refinement")
            !== descriptor.refined_surface?.refinement
          || !/^surf-[0-9a-f]{32}$/.test(referenceSurfaceId)
          || !/^[0-9a-f]{64}$/.test(referenceSha256)
          || !Number.isFinite(maxDisplacementMm)
          || !Number.isFinite(displacementLimitMm)
          || maxDisplacementMm < 0
          || displacementLimitMm <= 0
          || maxDisplacementMm > displacementLimitMm + 1e-6
          || !Number.isFinite(triangleRetention)
          || triangleRetention < Number(
            descriptor.refined_surface?.minimum_triangle_retention_ratio,
          ) - 1e-9
          || triangleRetention > 1 + 1e-9
          || !["true", "false"].includes(decimationApplied)
          || !Number.isFinite(decimationCellIndex)
          || (decimationApplied === "false" && Math.abs(decimationCellIndex) > 1e-9)
          || (
            decimationApplied === "true"
            && !allowedCells.some((value) => (
              Number.isFinite(Number(value))
              && Math.abs(Number(value) - decimationCellIndex) <= 1e-9
            ))
          )
        ) {
          throw new Error("Refined segmentation surface binding is invalid");
        }
      }
      if (generation !== this.generation || controller.signal.aborted) return null;

      const geometry = new this.three.BufferGeometry();
      geometry.setAttribute("position", new this.three.BufferAttribute(decoded.positions, 3));
      if (decoded.normals) {
        geometry.setAttribute("normal", new this.three.BufferAttribute(decoded.normals, 3));
      }
      geometry.setIndex(new this.three.BufferAttribute(segmentationViewerWinding(decoded.indices), 1));
      geometry.applyMatrix4(presentationTransform);
      if (!decoded.normals) geometry.computeVertexNormals();
      geometry.computeBoundingSphere();

      const structure = this.presentation?.structures?.get(labelId);
      const material = this._makeMaterial(structure);
      const mesh = new this.three.Mesh(geometry, material);
      mesh.name = `Segmentation surface label ${labelId}`;
      mesh.userData.labelMapId = descriptor.label_map_id;
      mesh.userData.labelId = labelId;
      mesh.userData.coordinateSystem = "patient_lps";
      mesh.userData.surfaceId = surfaceId;
      mesh.userData.provenanceSha256 = provenanceSha256;
      mesh.userData.surfaceSchemaVersion = decoded.version;
      mesh.userData.surfaceQuality = servedQuality;
      mesh.userData.presentationFallback = presentationFallback;
      mesh.userData.presentationFallbackFrom = presentationFallback ? requestedQuality : "";
      mesh.userData.presentationFallbackReason = presentationFallbackReason;
      mesh.userData.refinement = headerValue(response, "X-VoxelAtlas-Surface-Refinement");
      mesh.userData.referenceSurfaceId = headerValue(
        response, "X-VoxelAtlas-Surface-Reference-Id",
      );
      this.group.add(mesh);
      const item = {
        labelId,
        mesh,
        geometry,
        material,
        triangleCount: decoded.triangleCount,
        surfaceQuality: servedQuality,
        presentationFallback,
      };
      this.items.set(labelId, item);
      this.failedLabels.delete(labelId);
      this._updateItemPresentation(
        item,
        this.presentation?.structures?.get(labelId),
        this.presentation?.selectedLabelId,
      );
      this.requestRender();
      return item;
    } catch (error) {
      if (error?.name === "AbortError") return null;
      if (generation === this.generation) {
        this.failedLabels.set(
          labelId,
          error instanceof Error ? error.message : "Segmentation surface unavailable",
        );
      }
      return null;
    }
  }

  async sync(presentation) {
    this.presentation = presentation || null;
    if (!this.descriptor) {
      this._updateStatus();
      return null;
    }
    const desiredStructures = this._desiredStructures(presentation);
    this.desiredLabels = new Set(desiredStructures.map((structure) => structure.labelId));
    for (const [labelId, controller] of this.controllers) {
      if (!this.desiredLabels.has(labelId)) controller.abort();
    }
    for (const labelId of Array.from(this.failedLabels.keys())) {
      if (!this.desiredLabels.has(labelId)) this.failedLabels.delete(labelId);
    }

    for (const [labelId, item] of this.items) {
      this._updateItemPresentation(
        item,
        presentation?.structures?.get(labelId),
        presentation?.selectedLabelId,
      );
    }

    this.queue = this.queue.filter((entry) => (
      entry.generation === this.generation && this.desiredLabels.has(entry.labelId)
    ));
    for (const structure of desiredStructures) {
      this._enqueue(structure.labelId, this.generation);
    }
    this._pumpQueue();
    this._updateStatus();
    this.requestRender();
    return this.items.get(presentation?.selectedLabelId) || null;
  }

  dispose() {
    this.clear();
    this.group.removeFromParent();
  }
}
