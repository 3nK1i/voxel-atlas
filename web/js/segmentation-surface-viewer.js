const SURFACE_MEDIA_TYPE = "application/x-voxelatlas-surface-v1";
const SURFACE_MAGIC = "VXSF";
const SURFACE_HEADER_BYTES = 32;


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
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < SURFACE_HEADER_BYTES) {
    throw new Error("Segmentation surface payload is truncated");
  }
  const view = new DataView(buffer);
  const magic = String.fromCharCode(...new Uint8Array(buffer, 0, 4));
  const version = view.getUint32(4, true);
  const labelId = view.getUint32(8, true);
  const vertexCount = view.getUint32(12, true);
  const indexCount = view.getUint32(16, true);
  const stride = view.getUint32(20, true);
  const positionBytes = view.getUint32(24, true);
  const indexBytes = view.getUint32(28, true);
  if (
    magic !== SURFACE_MAGIC
    || version !== 1
    || labelId !== Number(expected.labelId)
    || vertexCount <= 0
    || indexCount <= 0
    || indexCount % 3 !== 0
    || stride <= 0
    || positionBytes !== vertexCount * 3 * 4
    || indexBytes !== indexCount * 4
    || buffer.byteLength !== SURFACE_HEADER_BYTES + positionBytes + indexBytes
  ) {
    throw new Error("Segmentation surface payload contract is invalid");
  }
  const positions = new Float32Array(
    buffer.slice(SURFACE_HEADER_BYTES, SURFACE_HEADER_BYTES + positionBytes),
  );
  const indices = new Uint32Array(
    buffer.slice(SURFACE_HEADER_BYTES + positionBytes),
  );
  return Object.freeze({
    labelId,
    vertexCount,
    triangleCount: indexCount / 3,
    stride,
    positions,
    indices,
  });
}


function patientLpsToViewerMatrix(THREE, presentation) {
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
    if (!three?.BufferGeometry || !three?.Mesh || !three?.MeshPhongMaterial) {
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
    parent.add(this.group);
    this.descriptor = null;
    this.enabled = true;
    this.current = null;
    this.controller = null;
    this.generation = 0;
  }

  _status(state, message) {
    this.onStatusChange(Object.freeze({ state, message }));
  }

  _disposeMesh() {
    if (!this.current) return;
    this.group.remove(this.current.mesh);
    this.current.geometry.dispose();
    this.current.material.dispose();
    this.current = null;
  }

  clear() {
    this.generation += 1;
    this.controller?.abort();
    this.controller = null;
    this._disposeMesh();
    this.descriptor = null;
    this._status("unavailable", "No 3D segmentation surface available.");
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
      this._disposeMesh();
    }
    this.descriptor = descriptor;
    this._status("ready", "Select a structure to show its 3D surface.");
  }

  setEnabled(enabled) {
    this.enabled = Boolean(enabled);
    this.group.visible = this.enabled;
    if (!this.enabled) {
      this.controller?.abort();
      this._status("disabled", "Selected 3D surface hidden.");
    }
    this.requestRender();
  }

  async sync(presentation) {
    const selected = presentation?.structures?.get(presentation.selectedLabelId);
    if (!this.enabled || !this.descriptor || !selected || !selected.visible) {
      if (this.current?.mesh) this.current.mesh.visible = false;
      this._status(this.enabled ? "ready" : "disabled", this.enabled
        ? "Select a visible structure to show its 3D surface."
        : "Selected 3D surface hidden.");
      this.requestRender();
      return null;
    }
    if (this.current?.labelId === selected.labelId) {
      this.current.mesh.visible = true;
      this.current.material.color.set(selected.colorHex);
      this.current.material.opacity = selected.opacity;
      this.current.material.transparent = selected.opacity < 1;
      this._status(
        "qualified",
        `${selected.displayName} · ${this.current.triangleCount.toLocaleString()} triangles`,
      );
      this.requestRender();
      return this.current;
    }

    const presentationTransform = patientLpsToViewerMatrix(
      this.three,
      this.readVolumePresentation(),
    );
    const generation = ++this.generation;
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    this._status("loading", `Building ${selected.displayName} surface...`);
    const params = new URLSearchParams({
      label_map_id: this.descriptor.label_map_id,
      quality: this.descriptor.default_quality || "preview",
    });
    try {
      const response = await this.fetchImpl(
        `/api/studies/latest/segmentation-surfaces/${selected.labelId}?${params}`,
        {
          credentials: "same-origin",
          cache: "no-store",
          headers: { "Accept": SURFACE_MEDIA_TYPE },
          signal: controller.signal,
        },
      );
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `Segmentation surface failed (${response.status})`);
      }
      const mediaType = headerValue(response, "Content-Type").split(";", 1)[0].toLowerCase();
      if (
        mediaType !== SURFACE_MEDIA_TYPE
        || headerValue(response, "X-Content-Type-Options").toLowerCase() !== "nosniff"
        || !headerValue(response, "Cache-Control").toLowerCase().includes("no-store")
        || headerValue(response, "X-VoxelAtlas-Label-Map-Id") !== this.descriptor.label_map_id
        || Number(headerValue(response, "X-VoxelAtlas-Label-Id")) !== selected.labelId
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
      const decoded = decodeSegmentationSurface(buffer, { labelId: selected.labelId });
      if (
        decoded.vertexCount !== Number(headerValue(response, "X-VoxelAtlas-Surface-Vertices"))
        || decoded.triangleCount !== Number(headerValue(response, "X-VoxelAtlas-Surface-Triangles"))
      ) {
        throw new Error("Segmentation surface count headers do not match");
      }
      if (generation !== this.generation || controller.signal.aborted) return null;

      const geometry = new this.three.BufferGeometry();
      geometry.setAttribute("position", new this.three.BufferAttribute(decoded.positions, 3));
      geometry.setIndex(new this.three.BufferAttribute(decoded.indices, 1));
      geometry.applyMatrix4(presentationTransform);
      geometry.computeVertexNormals();
      geometry.computeBoundingSphere();
      const material = new this.three.MeshPhongMaterial({
        color: selected.colorHex,
        opacity: selected.opacity,
        transparent: selected.opacity < 1,
        side: this.three.DoubleSide,
        depthTest: true,
        depthWrite: true,
        shininess: 32,
        specular: 0x223344,
      });
      const mesh = new this.three.Mesh(geometry, material);
      mesh.name = `Segmentation surface label ${selected.labelId}`;
      mesh.userData.labelMapId = this.descriptor.label_map_id;
      mesh.userData.labelId = selected.labelId;
      mesh.userData.coordinateSystem = "patient_lps";
      this._disposeMesh();
      this.group.add(mesh);
      this.current = {
        labelId: selected.labelId,
        mesh,
        geometry,
        material,
        triangleCount: decoded.triangleCount,
      };
      this._status(
        "qualified",
        `${selected.displayName} · ${decoded.triangleCount.toLocaleString()} triangles`,
      );
      this.requestRender();
      return this.current;
    } catch (error) {
      if (error?.name === "AbortError") return null;
      if (generation === this.generation) {
        this._status("error", error instanceof Error
          ? error.message
          : "Segmentation surface unavailable");
      }
      return null;
    } finally {
      if (this.controller === controller) this.controller = null;
    }
  }

  dispose() {
    this.clear();
    this.group.removeFromParent();
  }
}
