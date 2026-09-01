import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const SKULL_URL = "/assets/models/skull_full.glb";
const THEME_KEY = "voxelatlas-theme";
const DEFAULT_OPACITY = 0.94;

const viewport = document.getElementById("viewport");
const viewerStage = document.getElementById("viewerStage");
const modelStatus = document.getElementById("modelStatus");
const statusText = document.getElementById("statusText");
const modelChip = document.getElementById("modelChip");
const sectionSlider = document.getElementById("sectionSlider");
const sectionValue = document.getElementById("sectionValue");
const sectionButtons = Array.from(document.querySelectorAll("[data-section-axis]"));
const layerButtons = Array.from(document.querySelectorAll("[data-layer]"));
const anatomyNote = document.getElementById("anatomyNote");
const opacitySlider = document.getElementById("opacitySlider");
const opacityValue = document.getElementById("opacityValue");
const resetButton = document.getElementById("resetButton");
const autoRotateButton = document.getElementById("autoRotateButton");
const logoutButton = document.getElementById("logoutButton");
const accountName = document.getElementById("accountName");
const themeToggle = document.getElementById("themeToggle");
const fitViewButton = document.getElementById("fitViewButton");
const zoomInButton = document.getElementById("zoomInButton");
const zoomOutButton = document.getElementById("zoomOutButton");
const fullscreenButton = document.getElementById("fullscreenButton");
const themeColorMeta = document.querySelector('meta[name="theme-color"]');
const uploadDicomButton = document.getElementById("uploadDicomButton");
const uploadDicomLabel = document.getElementById("uploadDicomLabel");
const dicomFileInput = document.getElementById("dicomFileInput");
const uploadStatus = document.getElementById("uploadStatus");
const studyCard = document.querySelector(".study-card");
const studyLabel = document.getElementById("studyLabel");
const studyId = document.getElementById("studyId");
const studyModality = document.getElementById("studyModality");
const studyDate = document.getElementById("studyDate");
const studyModalityValue = document.getElementById("studyModalityValue");
const studyInstanceCount = document.getElementById("studyInstanceCount");
const studySeriesCount = document.getElementById("studySeriesCount");
const seriesDescription = document.getElementById("seriesDescription");
const seriesManufacturer = document.getElementById("seriesManufacturer");
const seriesPixelSpacing = document.getElementById("seriesPixelSpacing");
const seriesMatrix = document.getElementById("seriesMatrix");
const seriesSliceThickness = document.getElementById("seriesSliceThickness");
const seriesButton = document.getElementById("seriesButton");
const seriesButtonLabel = document.getElementById("seriesButtonLabel");
const seriesDialog = document.getElementById("seriesDialog");
const seriesDialogClose = document.getElementById("seriesDialogClose");
const seriesDialogList = document.getElementById("seriesDialogList");
const workflowData = document.getElementById("workflowData");
const workflowReconstruction = document.getElementById("workflowReconstruction");
const workflowVisualization = document.getElementById("workflowVisualization");
const volumeStatusRow = document.getElementById("volumeStatusRow");
const volumeStatusText = document.getElementById("volumeStatusText");

const layerRegistry = new Map([
  ["volume", { available: false, root: null, meshes: [] }],
  ["skull", { available: false, root: null, meshes: [] }],
  ["brain", { available: false, root: null, meshes: [] }],
]);

const state = {
  sectionAxis: "y",
  sectionDepth: 0,
  opacity: DEFAULT_OPACITY,
  layer: "skull",
  autoRotate: false,
  studyLoaded: false,
  study: null,
  size: new THREE.Vector3(1, 1, 1),
  min: new THREE.Vector3(),
  max: new THREE.Vector3(),
  cameraPosition: new THREE.Vector3(),
  cameraTarget: new THREE.Vector3(),
  sectionPlane: new THREE.Plane(new THREE.Vector3(0, -1, 0), 0),
};

const scene = new THREE.Scene();
const anatomyGroup = new THREE.Group();
scene.add(anatomyGroup);

const camera = new THREE.PerspectiveCamera(29, 1, 0.005, 40);
const renderer = new THREE.WebGLRenderer({
  antialias: true,
  alpha: true,
  powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.86;
renderer.localClippingEnabled = true;
viewport.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.enableRotate = true;
controls.enablePan = true;
controls.enableZoom = true;
controls.rotateSpeed = 0.68;
controls.panSpeed = 0.72;
controls.zoomSpeed = 0.88;
controls.screenSpacePanning = true;
controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
controls.touches.ONE = THREE.TOUCH.ROTATE;
controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;

scene.add(new THREE.HemisphereLight(0xe6eef2, 0x07111d, 1.35));

const key = new THREE.DirectionalLight(0xfff7e8, 2.05);
key.position.set(0.7, 1.1, 0.9);
scene.add(key);

const fill = new THREE.DirectionalLight(0x9ac8e7, 0.78);
fill.position.set(-0.8, 0.25, 0.55);
scene.add(fill);

const rim = new THREE.DirectionalLight(0xb8dcf3, 1.05);
rim.position.set(0.2, 0.45, -1.1);
scene.add(rim);

function setStatus(kind, message) {
  modelStatus.dataset.state = kind;
  statusText.textContent = message;
}

function createClinicalMaterial() {
  return new THREE.MeshPhysicalMaterial({
    color: 0xe8e1d6,
    roughness: 0.64,
    metalness: 0.01,
    clearcoat: 0.01,
    clearcoatRoughness: 0.78,
    transparent: true,
    opacity: state.opacity,
    depthWrite: true,
    side: THREE.FrontSide,
    clippingPlanes: [],
  });
}

function registerLayer(name, root, materialFactory = createClinicalMaterial) {
  const entry = layerRegistry.get(name);
  if (!entry) {
    throw new Error(`Unknown anatomy layer: ${name}`);
  }

  if (entry.root && entry.root.parent) {
    entry.root.parent.remove(entry.root);
  }

  entry.root = root;
  entry.meshes = [];

  root.traverse((child) => {
    if (!child.isMesh) return;
    child.material = materialFactory();
    child.castShadow = false;
    child.receiveShadow = false;
    entry.meshes.push(child);
  });

  anatomyGroup.add(root);
  root.updateMatrixWorld(true);
  setLayerAvailability(name, true);
  applyLayerVisibility();
  applySection();
  applyOpacity();
}

function setLayerAvailability(name, available) {
  const entry = layerRegistry.get(name);
  if (entry) {
    entry.available = Boolean(available);
  }

  const skullReady = Boolean(layerRegistry.get("skull")?.available);
  const brainReady = Boolean(layerRegistry.get("brain")?.available);
  const volumeReady = Boolean(layerRegistry.get("volume")?.available);

  for (const button of layerButtons) {
    const layer = button.dataset.layer;
    let enabled = false;
    if (layer === "skull") enabled = skullReady;
    if (layer === "brain") enabled = brainReady;
    if (layer === "volume") enabled = volumeReady;
    if (layer === "combined") enabled = skullReady && brainReady;
    button.disabled = !enabled;
  }

  if (!brainReady && !volumeReady) {
    anatomyNote.textContent = "Patient volume and brain layers activate when the reconstruction pipeline provides them.";
  }
}

function allRegisteredMeshes() {
  const meshes = [];
  for (const entry of layerRegistry.values()) {
    meshes.push(...entry.meshes);
  }
  return meshes;
}

function updateLayerUI() {
  for (const button of layerButtons) {
    button.classList.toggle("is-active", button.dataset.layer === state.layer);
  }

  if (state.layer === "brain") {
    modelChip.textContent = "Patient anatomy - Brain";
  } else if (state.layer === "combined") {
    modelChip.textContent = "Patient anatomy - Skull + Brain";
  } else if (state.layer === "volume") {
    modelChip.textContent = "Patient anatomy - Full Volume";
  } else {
    modelChip.textContent = state.studyLoaded
      ? "Demo skull - patient reconstruction pending"
      : "Demo A0101 - Skull";
  }
}

function applyLayerVisibility() {
  const skull = layerRegistry.get("skull");
  const brain = layerRegistry.get("brain");
  const volume = layerRegistry.get("volume");

  if (skull?.root) skull.root.visible = state.layer === "skull" || state.layer === "combined";
  if (brain?.root) brain.root.visible = state.layer === "brain" || state.layer === "combined";
  if (volume?.root) volume.root.visible = state.layer === "volume";
  updateLayerUI();
}

function setLayer(layer) {
  const button = layerButtons.find((candidate) => candidate.dataset.layer === layer);
  if (!button || button.disabled) return;
  state.layer = layer;
  applyLayerVisibility();
}

function updateBoundsFromSkull() {
  const skullRoot = layerRegistry.get("skull")?.root;
  if (!skullRoot) return null;
  const box = new THREE.Box3().setFromObject(skullRoot);
  box.getSize(state.size);
  state.min.copy(box.min);
  state.max.copy(box.max);
  return box;
}

function fitCamera(box) {
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const radius = Math.max(sphere.radius, 0.01);
  const position = new THREE.Vector3(
    sphere.center.x + radius * 1.30,
    sphere.center.y + radius * 0.42,
    sphere.center.z + radius * 2.55,
  );
  const target = sphere.center.clone();
  target.y += state.size.y * 0.015;

  camera.position.copy(position);
  controls.target.copy(target);
  state.cameraPosition.copy(position);
  state.cameraTarget.copy(target);

  controls.minDistance = radius * 1.15;
  controls.maxDistance = radius * 8;
  camera.near = Math.max(radius / 150, 0.001);
  camera.far = radius * 30;
  camera.updateProjectionMatrix();
  controls.update();
}

function fitSavedView() {
  camera.position.copy(state.cameraPosition);
  controls.target.copy(state.cameraTarget);
  controls.update();
}

function zoomBy(factor) {
  const offset = camera.position.clone().sub(controls.target);
  const currentDistance = Math.max(offset.length(), 0.0001);
  const nextDistance = THREE.MathUtils.clamp(
    currentDistance * factor,
    controls.minDistance || currentDistance * 0.25,
    controls.maxDistance || currentDistance * 4,
  );
  offset.setLength(nextDistance);
  camera.position.copy(controls.target).add(offset);
  controls.update();
}

function updateSectionPlane() {
  const t = THREE.MathUtils.clamp(state.sectionDepth, 0, 1);

  if (state.sectionAxis === "x") {
    const x = THREE.MathUtils.lerp(state.max.x + state.size.x * 0.02, state.min.x, t);
    state.sectionPlane.setFromNormalAndCoplanarPoint(
      new THREE.Vector3(-1, 0, 0),
      new THREE.Vector3(x, 0, 0),
    );
    return;
  }

  if (state.sectionAxis === "z") {
    const z = THREE.MathUtils.lerp(state.max.z + state.size.z * 0.02, state.min.z, t);
    state.sectionPlane.setFromNormalAndCoplanarPoint(
      new THREE.Vector3(0, 0, -1),
      new THREE.Vector3(0, 0, z),
    );
    return;
  }

  const y = THREE.MathUtils.lerp(state.max.y + state.size.y * 0.02, state.min.y, t);
  state.sectionPlane.setFromNormalAndCoplanarPoint(
    new THREE.Vector3(0, -1, 0),
    new THREE.Vector3(0, y, 0),
  );
}

function applySection() {
  updateSectionPlane();
  const enabled = state.sectionDepth > 0.001;

  for (const mesh of allRegisteredMeshes()) {
    const material = mesh.material;
    const hasPlane = Array.isArray(material.clippingPlanes) && material.clippingPlanes.length > 0;

    if (enabled && !hasPlane) {
      material.clippingPlanes = [state.sectionPlane];
      material.needsUpdate = true;
    } else if (!enabled && hasPlane) {
      material.clippingPlanes = [];
      material.needsUpdate = true;
    }
  }

  sectionValue.textContent = `${Math.round(state.sectionDepth * 100)}%`;
}

function applyOpacity() {
  const skull = layerRegistry.get("skull");
  if (skull) {
    for (const mesh of skull.meshes) {
      mesh.material.opacity = state.opacity;
      mesh.material.transparent = state.opacity < 0.995;
      mesh.material.depthWrite = true;
      mesh.material.needsUpdate = true;
    }
  }
  opacityValue.textContent = `${Math.round(state.opacity * 100)}%`;
}

function prepareSkull(root) {
  registerLayer("skull", root, createClinicalMaterial);
  const box = updateBoundsFromSkull();
  if (box) fitCamera(box);
  state.layer = "skull";
  applyLayerVisibility();
  setStatus("ready", "Demo anatomy ready");
}

function loadSkull() {
  setStatus("loading", "Loading demo anatomy...");
  const loader = new GLTFLoader();
  loader.load(
    SKULL_URL,
    (gltf) => prepareSkull(gltf.scene),
    (progress) => {
      if (!progress.total) return;
      const percent = Math.round((progress.loaded / progress.total) * 100);
      setStatus("loading", `Loading demo anatomy... ${percent}%`);
    },
    (error) => {
      console.error(error);
      setStatus("error", "Demo anatomy failed to load");
    },
  );
}

function resetWorkspace() {
  state.sectionDepth = 0;
  sectionSlider.value = "0";
  state.sectionAxis = "y";
  for (const button of sectionButtons) {
    button.classList.toggle("is-active", button.dataset.sectionAxis === "y");
  }

  state.opacity = DEFAULT_OPACITY;
  opacitySlider.value = String(Math.round(DEFAULT_OPACITY * 100));
  state.layer = "skull";
  state.autoRotate = false;
  autoRotateButton.classList.remove("is-active");
  autoRotateButton.setAttribute("aria-pressed", "false");
  autoRotateButton.textContent = "Auto rotate";

  anatomyGroup.rotation.set(0, 0, 0);
  applyOpacity();
  applySection();
  applyLayerVisibility();
  fitSavedView();
}

function preferredTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // Storage can be blocked without affecting viewer operation.
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(theme, persist = false) {
  const normalized = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = normalized;
  themeToggle.setAttribute("aria-pressed", normalized === "light" ? "true" : "false");
  themeToggle.setAttribute(
    "aria-label",
    normalized === "light" ? "Switch to dark mode" : "Switch to light mode",
  );
  if (themeColorMeta) {
    themeColorMeta.setAttribute("content", normalized === "light" ? "#eef5fb" : "#020915");
  }
  if (persist) {
    try {
      localStorage.setItem(THEME_KEY, normalized);
    } catch {
      // Theme persistence is optional.
    }
  }
}

async function refreshAccountName() {
  try {
    const response = await fetch("/api/auth/session", {
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    if (!response.ok) return;
    const payload = await response.json();
    if (payload.authenticated && typeof payload.username === "string" && payload.username.trim()) {
      accountName.textContent = payload.username.trim();
    }
  } catch {
    // The workspace remains usable if account decoration cannot refresh.
  }
}

function setWorkflowStep(element, stateName) {
  element.dataset.state = stateName;
  element.classList.toggle("is-active", stateName === "active");
  if (stateName === "active") {
    element.setAttribute("aria-current", "step");
  } else {
    element.removeAttribute("aria-current");
  }
}

function setWorkflowForStudy(hasStudy) {
  if (hasStudy) {
    setWorkflowStep(workflowData, "complete");
    setWorkflowStep(workflowReconstruction, "active");
    setWorkflowStep(workflowVisualization, "pending");
    volumeStatusRow.dataset.state = "pending";
    volumeStatusText.textContent = "DICOM ready - reconstruction pending";
  } else {
    setWorkflowStep(workflowData, "active");
    setWorkflowStep(workflowReconstruction, "pending");
    setWorkflowStep(workflowVisualization, "pending");
    volumeStatusRow.dataset.state = "pending";
    volumeStatusText.textContent = "Awaiting DICOM";
  }
}

function formatStudyDate(raw) {
  if (typeof raw !== "string" || !/^\d{8}$/.test(raw)) return raw || "-";
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

function formatSpacing(value) {
  if (!Array.isArray(value) || value.length < 2) return "-";
  return `${value.slice(0, 2).map((item) => Number(item).toFixed(3)).join(" × ")} mm`;
}

function primarySeries(study) {
  if (!study || !Array.isArray(study.series)) return null;
  return study.series.find((item) => item.series_instance_uid === study.primary_series_uid)
    || study.series[0]
    || null;
}

function setUploadStatus(kind, message) {
  uploadStatus.dataset.state = kind;
  uploadStatus.textContent = message;
}

function renderSeriesDialog(study) {
  seriesDialogList.replaceChildren();
  if (!study || !Array.isArray(study.series) || study.series.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = "No DICOM series are available.";
    seriesDialogList.appendChild(empty);
    return;
  }

  for (const series of study.series) {
    const item = document.createElement("article");
    item.className = "series-dialog-item";
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = series.series_description || `Series ${series.series_number ?? "-"}`;
    const metadata = document.createElement("span");
    metadata.textContent = `${series.modality || "-"} • ${series.rows || "-"} × ${series.columns || "-"}`;
    const uid = document.createElement("small");
    uid.textContent = series.series_instance_uid || "Series UID unavailable";
    copy.append(title, metadata, uid);

    const count = document.createElement("span");
    count.className = "series-dialog-count";
    count.textContent = `${series.instance_count || 0} instance${series.instance_count === 1 ? "" : "s"}`;
    item.append(copy, count);
    seriesDialogList.appendChild(item);
  }
}

function applyStudy(study) {
  state.study = study;
  state.studyLoaded = Boolean(study);
  setWorkflowForStudy(state.studyLoaded);

  if (!study) {
    studyCard.dataset.studyState = "empty";
    studyLabel.textContent = "No DICOM study loaded";
    studyId.textContent = "-";
    studyModality.textContent = "-";
    studyDate.textContent = "-";
    studyModalityValue.textContent = "-";
    studyInstanceCount.textContent = "-";
    studySeriesCount.textContent = "-";
    seriesDescription.textContent = "Not loaded";
    seriesManufacturer.textContent = "-";
    seriesPixelSpacing.textContent = "-";
    seriesMatrix.textContent = "-";
    seriesSliceThickness.textContent = "-";
    seriesButton.disabled = true;
    seriesButtonLabel.textContent = "DICOM series unavailable";
    uploadDicomLabel.textContent = "Upload DICOM";
    updateLayerUI();
    return;
  }

  const series = primarySeries(study);
  const modalities = Array.isArray(study.modalities) ? study.modalities.join(" / ") : "-";
  studyCard.dataset.studyState = "ready";
  studyLabel.textContent = study.study_description || "DICOM study";
  studyId.textContent = String(study.study_id || "-").slice(0, 12).toUpperCase();
  studyModality.textContent = modalities || "-";
  studyDate.textContent = formatStudyDate(study.study_date);
  studyModalityValue.textContent = modalities || "-";
  studyInstanceCount.textContent = String(study.file_count ?? "-");
  studySeriesCount.textContent = String(study.series_count ?? "-");
  seriesDescription.textContent = series?.series_description || "-";
  seriesManufacturer.textContent = series?.manufacturer || "-";
  seriesPixelSpacing.textContent = formatSpacing(series?.pixel_spacing);
  seriesMatrix.textContent = series?.rows && series?.columns
    ? `${series.rows} × ${series.columns}`
    : "-";
  seriesSliceThickness.textContent = Number.isFinite(Number(series?.slice_thickness))
    ? `${Number(series.slice_thickness).toFixed(3)} mm`
    : "-";
  seriesButton.disabled = false;
  seriesButtonLabel.textContent = `${study.series_count} DICOM series discovered`;
  uploadDicomLabel.textContent = "Replace DICOM Study";
  renderSeriesDialog(study);
  updateLayerUI();
}

async function refreshLatestStudy() {
  try {
    const response = await fetch("/api/studies/latest", {
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    if (!response.ok) return;
    const payload = await response.json();
    applyStudy(payload.study || null);
    if (payload.study) {
      setUploadStatus("ready", "Stored DICOM study restored. Reconstruction has not started yet.");
    }
  } catch {
    // Study restoration is best effort; upload remains available.
  }
}

async function uploadDicomFiles(files) {
  if (!files || files.length === 0) return;
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name || "dicom-instance");
  }

  uploadDicomButton.disabled = true;
  uploadDicomButton.dataset.state = "uploading";
  uploadDicomLabel.textContent = `Uploading ${files.length} file${files.length === 1 ? "" : "s"}...`;
  setUploadStatus("uploading", "Validating DICOM headers and grouping Study/Series metadata...");

  try {
    const response = await fetch("/api/studies/dicom", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
      body: formData,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `DICOM upload failed (${response.status})`);
    }
    applyStudy(payload.study);
    const skipped = Number(payload.study?.skipped_file_count || 0);
    setUploadStatus(
      "ready",
      skipped > 0
        ? `Study ready. ${payload.study.file_count} DICOM instances accepted; ${skipped} file${skipped === 1 ? "" : "s"} skipped.`
        : `Study ready. ${payload.study.file_count} DICOM instances accepted across ${payload.study.series_count} series.`,
    );
  } catch (error) {
    setUploadStatus("error", error instanceof Error ? error.message : "DICOM upload failed");
    uploadDicomLabel.textContent = state.studyLoaded ? "Replace DICOM Study" : "Upload DICOM";
  } finally {
    uploadDicomButton.disabled = false;
    uploadDicomButton.dataset.state = "idle";
    dicomFileInput.value = "";
  }
}

uploadDicomButton.addEventListener("click", () => dicomFileInput.click());

dicomFileInput.addEventListener("change", () => {
  void uploadDicomFiles(Array.from(dicomFileInput.files || []));
});

seriesButton.addEventListener("click", () => {
  if (seriesButton.disabled || !state.study) return;
  renderSeriesDialog(state.study);
  if (typeof seriesDialog.showModal === "function") {
    seriesDialog.showModal();
  }
});

seriesDialogClose.addEventListener("click", () => seriesDialog.close());
seriesDialog.addEventListener("click", (event) => {
  if (event.target === seriesDialog) seriesDialog.close();
});

sectionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const nextAxis = button.dataset.sectionAxis;
    if (!nextAxis || nextAxis === state.sectionAxis) return;
    state.sectionAxis = nextAxis;
    state.sectionDepth = 0;
    sectionSlider.value = "0";
    for (const candidate of sectionButtons) {
      candidate.classList.toggle("is-active", candidate === button);
    }
    applySection();
  });
});

sectionSlider.addEventListener("input", () => {
  state.sectionDepth = Number(sectionSlider.value) / 100;
  applySection();
});

opacitySlider.addEventListener("input", () => {
  state.opacity = Number(opacitySlider.value) / 100;
  applyOpacity();
});

layerButtons.forEach((button) => {
  button.addEventListener("click", () => setLayer(button.dataset.layer));
});

resetButton.addEventListener("click", resetWorkspace);

autoRotateButton.addEventListener("click", () => {
  state.autoRotate = !state.autoRotate;
  autoRotateButton.classList.toggle("is-active", state.autoRotate);
  autoRotateButton.setAttribute("aria-pressed", state.autoRotate ? "true" : "false");
  autoRotateButton.textContent = state.autoRotate ? "Stop rotate" : "Auto rotate";
});

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(next, true);
});

fitViewButton.addEventListener("click", fitSavedView);
zoomInButton.addEventListener("click", () => zoomBy(0.82));
zoomOutButton.addEventListener("click", () => zoomBy(1.22));
fullscreenButton.addEventListener("click", async () => {
  try {
    if (document.fullscreenElement === viewerStage) {
      await document.exitFullscreen();
    } else if (viewerStage.requestFullscreen) {
      await viewerStage.requestFullscreen();
    }
  } catch (error) {
    console.error(error);
  }
});

document.addEventListener("fullscreenchange", () => {
  const active = document.fullscreenElement === viewerStage;
  fullscreenButton.setAttribute("aria-pressed", active ? "true" : "false");
  fullscreenButton.setAttribute("title", active ? "Exit fullscreen" : "Fullscreen");
  resize();
});

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
  } finally {
    window.location.assign("/login");
  }
});

function resize() {
  const width = Math.max(viewport.clientWidth, 1);
  const height = Math.max(viewport.clientHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

window.addEventListener("resize", resize, { passive: true });
if (window.ResizeObserver) {
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(viewport);
}

applyTheme(preferredTheme());
setLayerAvailability("volume", false);
setLayerAvailability("brain", false);
applyOpacity();
updateLayerUI();
resize();
loadSkull();
void refreshAccountName();
void refreshLatestStudy();

const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05);

  if (state.autoRotate) {
    anatomyGroup.rotation.y += dt * 0.32;
  }

  controls.update();
  renderer.render(scene, camera);
}
animate();
