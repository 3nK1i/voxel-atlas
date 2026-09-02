import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import {
  qualifyCanonicalVolumeForDevice,
  qualifyVolumeRenderingCapabilities,
  validateVolumeRenderingDescriptor,
} from "./volume-rendering-capabilities.js";
import { PatientVolumeTextureManager } from "./volume-texture-manager.js?v=phase4c1-r1";
import { PatientVolumeRayMarcher } from "./patient-volume-ray-marcher.js?v=phase4c2";

const SKULL_URL = "/assets/models/skull_full.glb";
const THEME_KEY = "voxelatlas-theme";
const DEFAULT_OPACITY = 1.0;
const INITIAL_VIEW_DISTANCE_SCALE = 1.18;

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
const directionalCutPanel = document.getElementById("directionalCutPanel");
const opacitySlider = document.getElementById("opacitySlider");
const opacityValue = document.getElementById("opacityValue");
const resetButton = document.getElementById("resetButton");
const autoRotateButton = document.getElementById("autoRotateButton");
const logoutButton = document.getElementById("logoutButton");
const accountName = document.getElementById("accountName");
const themeToggle = document.getElementById("themeToggle");
const rotateToolButton = document.getElementById("rotateToolButton");
const panToolButton = document.getElementById("panToolButton");
const fitViewButton = document.getElementById("fitViewButton");
const zoomInButton = document.getElementById("zoomInButton");
const zoomOutButton = document.getElementById("zoomOutButton");
const fullscreenButton = document.getElementById("fullscreenButton");
const primaryInteractionHint = document.getElementById("primaryInteractionHint");
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
const mprPanels = Array.from(document.querySelectorAll(".mpr-panel"));
const mprVolumeMessages = Array.from(document.querySelectorAll("[data-mpr-message]"));
const mprViews = Array.from(document.querySelectorAll("[data-mpr-view]"));
const mprRegistry = new Map([
  ["axial", {
    panel: document.getElementById("mprAxial"),
    view: document.querySelector('[data-mpr-view="axial"]'),
    surface: document.querySelector('[data-mpr-surface="axial"]'),
    canvas: document.getElementById("mprAxialCanvas"),
    index: document.getElementById("mprAxialIndex"),
    position: document.getElementById("mprAxialPosition"),
    wl: document.getElementById("mprAxialWl"),
    message: document.querySelector('[data-mpr-message="axial"]'),
  }],
  ["coronal", {
    panel: document.getElementById("mprCoronal"),
    view: document.querySelector('[data-mpr-view="coronal"]'),
    surface: document.querySelector('[data-mpr-surface="coronal"]'),
    canvas: document.getElementById("mprCoronalCanvas"),
    index: document.getElementById("mprCoronalIndex"),
    position: document.getElementById("mprCoronalPosition"),
    wl: document.getElementById("mprCoronalWl"),
    message: document.querySelector('[data-mpr-message="coronal"]'),
  }],
  ["sagittal", {
    panel: document.getElementById("mprSagittal"),
    view: document.querySelector('[data-mpr-view="sagittal"]'),
    surface: document.querySelector('[data-mpr-surface="sagittal"]'),
    canvas: document.getElementById("mprSagittalCanvas"),
    index: document.getElementById("mprSagittalIndex"),
    position: document.getElementById("mprSagittalPosition"),
    wl: document.getElementById("mprSagittalWl"),
    message: document.querySelector('[data-mpr-message="sagittal"]'),
  }],
]);
const orientationGizmo = document.getElementById("orientationGizmo");
const gizmoEdges = Array.from(document.querySelectorAll("[data-gizmo-edge]"));
const gizmoAxisS = document.getElementById("gizmoAxisS");
const gizmoAxisA = document.getElementById("gizmoAxisA");
const gizmoAxisR = document.getElementById("gizmoAxisR");
const gizmoAxisL = document.getElementById("gizmoAxisL");
const gizmoLabelS = document.getElementById("gizmoLabelS");
const gizmoLabelA = document.getElementById("gizmoLabelA");
const gizmoLabelR = document.getElementById("gizmoLabelR");
const gizmoLabelL = document.getElementById("gizmoLabelL");

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
  viewerInteractionMode: "rotate",
  studyLoaded: false,
  study: null,
  mpr: {
    descriptor: null,
    crosshairLpsMm: [0, 0, 0],
    window: 400,
    level: 40,
  },
  size: new THREE.Vector3(1, 1, 1),
  min: new THREE.Vector3(),
  max: new THREE.Vector3(),
  cameraPosition: new THREE.Vector3(),
  cameraTarget: new THREE.Vector3(),
  sectionPlane: new THREE.Plane(new THREE.Vector3(0, -1, 0), 0),
};

let volumeBuildPromise = null;
let volumeRenderingTask = null;
let mprDescriptorPromise = null;
let mprRenderGeneration = 0;
let mprRenderTimer = null;
let mprAbortController = null;

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
const volumeRenderingCapabilities = qualifyVolumeRenderingCapabilities(renderer);
state.volumeRendering = {
  capabilities: volumeRenderingCapabilities,
  descriptor: null,
  textureResource: null,
};
const volumeTextureManager = new PatientVolumeTextureManager({
  three: THREE,
  initializeTexture: (texture) => renderer.initTexture(texture),
});
const volumeRayMarcher = new PatientVolumeRayMarcher({ three: THREE });

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
    roughness: 0.72,
    metalness: 0.0,
    clearcoat: 0.0,
    clearcoatRoughness: 1.0,
    transparent: false,
    opacity: 1.0,
    depthWrite: true,
    depthTest: true,
    side: THREE.DoubleSide,
    forceSinglePass: true,
    dithering: true,
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
    anatomyNote.textContent = "Direct patient volume rendering is the next active 3D workflow. Skull and brain reconstruction are deferred.";
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
    const isActive = button.dataset.layer === state.layer;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
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

  const volumeActive = state.layer === "volume";
  directionalCutPanel.dataset.volumeDeferred = volumeActive ? "true" : "false";
  sectionSlider.disabled = volumeActive;
  for (const button of sectionButtons) button.disabled = volumeActive;
}

function applyLayerVisibility() {
  const skull = layerRegistry.get("skull");
  const brain = layerRegistry.get("brain");
  const volume = layerRegistry.get("volume");

  if (skull?.root) skull.root.visible = state.layer === "skull" || state.layer === "combined";
  if (brain?.root) brain.root.visible = state.layer === "brain" || state.layer === "combined";
  if (volume?.root) {
    volume.root.visible = state.layer === "volume" && state.opacity > 0.001;
  }
  updateLayerUI();
}

function setLayer(layer) {
  const button = layerButtons.find((candidate) => candidate.dataset.layer === layer);
  if (!button || button.disabled) return;
  if (layer === "volume" && state.sectionDepth > 0.001) {
    state.sectionDepth = 0;
    sectionSlider.value = "0";
    applySection();
  }
  state.layer = layer;
  applyLayerVisibility();
  if (layer === "volume") {
    setStatus("ready", "Patient volume rendering ready");
    anatomyNote.textContent = "True patient volume rendering active. Medical transfer functions and synchronized clipping follow in Phase 4D and Phase 4E.";
  } else if (layer === "skull" && state.studyLoaded) {
    setStatus("ready", "Demo anatomy fallback");
    anatomyNote.textContent = "Demo skull fallback. Select Full Volume to view the actual patient voxel data.";
  }
}

function updateBoundsFromLayer(name) {
  const root = layerRegistry.get(name)?.root;
  if (!root) return null;
  const box = new THREE.Box3().setFromObject(root);
  box.getSize(state.size);
  state.min.copy(box.min);
  state.max.copy(box.max);
  return box;
}

function fitCamera(box) {
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const radius = Math.max(sphere.radius, 0.01);
  const offset = new THREE.Vector3(
    radius * 1.30,
    radius * 0.42,
    radius * 2.55,
  );
  offset.multiplyScalar(INITIAL_VIEW_DISTANCE_SCALE);
  const position = sphere.center.clone().add(offset);
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

const GIZMO_CENTER = 48;
const GIZMO_CUBE_SCALE = 15.5;
const GIZMO_AXIS_SCALE = 27;
const GIZMO_LABEL_SCALE = 34;
const GIZMO_CORNERS = [
  new THREE.Vector3(-1, -1, -1),
  new THREE.Vector3(1, -1, -1),
  new THREE.Vector3(1, 1, -1),
  new THREE.Vector3(-1, 1, -1),
  new THREE.Vector3(-1, -1, 1),
  new THREE.Vector3(1, -1, 1),
  new THREE.Vector3(1, 1, 1),
  new THREE.Vector3(-1, 1, 1),
];
const GIZMO_EDGE_PAIRS = [
  [0, 1], [1, 2], [2, 3], [3, 0],
  [4, 5], [5, 6], [6, 7], [7, 4],
  [0, 4], [1, 5], [2, 6], [3, 7],
];
const gizmoInverseCameraQuaternion = new THREE.Quaternion();

function anatomyDirectionInView(localDirection) {
  gizmoInverseCameraQuaternion.copy(camera.quaternion).invert();
  return localDirection
    .clone()
    .applyQuaternion(anatomyGroup.quaternion)
    .applyQuaternion(gizmoInverseCameraQuaternion);
}

function gizmoPoint(localPoint, scale) {
  const view = anatomyDirectionInView(localPoint);
  return {
    x: GIZMO_CENTER + view.x * scale,
    y: GIZMO_CENTER - view.y * scale,
    z: view.z,
  };
}

function setGizmoLine(line, start, end) {
  if (!line) return;
  line.setAttribute("x1", start.x.toFixed(2));
  line.setAttribute("y1", start.y.toFixed(2));
  line.setAttribute("x2", end.x.toFixed(2));
  line.setAttribute("y2", end.y.toFixed(2));
}

function setGizmoLabel(label, point) {
  if (!label) return;
  label.setAttribute("x", point.x.toFixed(2));
  label.setAttribute("y", point.y.toFixed(2));
}

function updateOrientationGizmo() {
  if (!orientationGizmo) return;

  const projectedCorners = GIZMO_CORNERS.map((corner) => gizmoPoint(corner, GIZMO_CUBE_SCALE));
  GIZMO_EDGE_PAIRS.forEach(([from, to], index) => {
    setGizmoLine(gizmoEdges[index], projectedCorners[from], projectedCorners[to]);
  });

  const center = { x: GIZMO_CENTER, y: GIZMO_CENTER };
  const directions = [
    [gizmoAxisS, gizmoLabelS, new THREE.Vector3(0, 1, 0)],
    [gizmoAxisA, gizmoLabelA, new THREE.Vector3(0, 0, 1)],
    [gizmoAxisR, gizmoLabelR, new THREE.Vector3(1, 0, 0)],
    [gizmoAxisL, gizmoLabelL, new THREE.Vector3(-1, 0, 0)],
  ];

  for (const [line, label, direction] of directions) {
    setGizmoLine(line, center, gizmoPoint(direction, GIZMO_AXIS_SCALE));
    setGizmoLabel(label, gizmoPoint(direction, GIZMO_LABEL_SCALE));
  }
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

function clinicalVisualOpacity(opacity) {
  const clamped = THREE.MathUtils.clamp(opacity, 0, 1);
  if (clamped <= 0.001 || clamped >= 0.999) return clamped;
  return Math.pow(clamped, 0.55);
}

function applyOpacity() {
  const visualOpacity = clinicalVisualOpacity(state.opacity);
  const skull = layerRegistry.get("skull");
  if (skull) {
    for (const mesh of skull.meshes) {
      const nextTransparent = state.opacity < 0.999;
      const nextSide = nextTransparent ? THREE.FrontSide : THREE.DoubleSide;
      const transparencyModeChanged = mesh.material.transparent !== nextTransparent;
      const sideModeChanged = mesh.material.side !== nextSide;

      mesh.visible = state.opacity > 0.001;
      mesh.material.opacity = visualOpacity;
      mesh.material.transparent = nextTransparent;
      mesh.material.side = nextTransparent ? THREE.FrontSide : THREE.DoubleSide;
      mesh.material.depthWrite = true;
      mesh.material.depthTest = true;
      mesh.material.forceSinglePass = true;

      if (transparencyModeChanged || sideModeChanged) {
        mesh.material.needsUpdate = true;
      }
    }
  }
  volumeRayMarcher.setOpacity(state.opacity);
  const volume = layerRegistry.get("volume");
  if (volume?.root) {
    volume.root.visible = state.layer === "volume" && state.opacity > 0.001;
  }
  opacityValue.textContent = `${Math.round(state.opacity * 100)}%`;
}

function prepareSkull(root) {
  registerLayer("skull", root, createClinicalMaterial);
  const volumeReady = Boolean(layerRegistry.get("volume")?.available);
  if (!volumeReady) {
    const box = updateBoundsFromLayer("skull");
    if (box) fitCamera(box);
  }
  state.layer = volumeReady ? "volume" : "skull";
  applyLayerVisibility();
  setStatus("ready", volumeReady ? "Patient volume rendering ready" : "Demo anatomy ready");
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

function clearPatientVolumeRendering() {
  const entry = layerRegistry.get("volume");
  volumeRayMarcher.dispose();
  if (entry) {
    entry.root = null;
    entry.meshes = [];
  }
  if (state.layer === "volume") state.layer = "skull";
  setLayerAvailability("volume", false);
  applyLayerVisibility();
}

async function activatePatientVolumeRendering(textureResource, task) {
  const volumeResource = volumeRayMarcher.create(textureResource);
  const compileScene = new THREE.Scene();
  compileScene.add(volumeResource.root);
  try {
    await renderer.compileAsync(compileScene, camera);
  } finally {
    compileScene.remove(volumeResource.root);
  }
  if (volumeRenderingTask !== task || volumeRayMarcher.current !== volumeResource) {
    throw new DOMException("Patient volume rendering was superseded", "AbortError");
  }

  const entry = layerRegistry.get("volume");
  entry.root = volumeResource.root;
  entry.meshes = [volumeResource.mesh];
  anatomyGroup.add(volumeResource.root);
  volumeResource.root.updateMatrixWorld(true);
  setLayerAvailability("volume", true);
  applyOpacity();

  const box = updateBoundsFromLayer("volume");
  if (box) fitCamera(box);
  setLayer("volume");
  setWorkflowStep(workflowVisualization, "complete");
  volumeStatusRow.dataset.state = "ready";
  volumeStatusText.textContent = "Patient volume rendered";
  return volumeResource;
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
  state.layer = layerRegistry.get("volume")?.available ? "volume" : "skull";
  state.autoRotate = false;
  autoRotateButton.classList.remove("is-active");
  autoRotateButton.setAttribute("aria-pressed", "false");
  autoRotateButton.textContent = "Auto rotate";

  anatomyGroup.rotation.set(0, 0, 0);
  applyOpacity();
  applySection();
  applyLayerVisibility();
  setViewerInteractionMode("rotate");
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

function setWorkflowForStudy(study) {
  if (study) {
    setWorkflowStep(workflowData, "complete");
    if (study.volume_ready) {
      setWorkflowStep(workflowReconstruction, "complete");
      setWorkflowStep(workflowVisualization, "pending");
      volumeStatusRow.dataset.state = "ready";
      volumeStatusText.textContent = "Patient volume ready";
    } else {
      setWorkflowStep(workflowReconstruction, "active");
      setWorkflowStep(workflowVisualization, "pending");
      volumeStatusRow.dataset.state = study.reconstruction_ready ? "ready" : "pending";
      volumeStatusText.textContent = study.reconstruction_ready
        ? "Geometry ready - volume reconstruction pending"
        : "Geometry needs review before reconstruction";
    }
  } else {
    setWorkflowStep(workflowData, "active");
    setWorkflowStep(workflowReconstruction, "pending");
    setWorkflowStep(workflowVisualization, "pending");
    volumeStatusRow.dataset.state = "pending";
    volumeStatusText.textContent = "Awaiting DICOM";
  }
}

function setMprVolumeState(study) {
  const ready = Boolean(study?.volume_ready);
  clearPatientVolumeRendering();
  volumeTextureManager.dispose();
  volumeRenderingTask = null;
  state.volumeRendering.descriptor = null;
  state.volumeRendering.textureResource = null;
  for (const panel of mprPanels) {
    panel.dataset.volumeState = ready ? "loading" : "empty";
  }
  for (const message of mprVolumeMessages) {
    message.textContent = ready ? "Loading patient volume..." : "DICOM volume not loaded";
  }
  if (!ready) {
    state.mpr.descriptor = null;
    for (const entry of mprRegistry.values()) {
      entry.index.textContent = "-- / --";
      entry.position.textContent = `${entry.panel.id === "mprAxial" ? "Z" : entry.panel.id === "mprCoronal" ? "Y" : "X"}: --`;
      entry.wl.textContent = "W: --   L: --";
    }
  }
}

async function ensureVolumeRenderingFoundation() {
  if (!state.study?.volume_ready) return null;
  if (state.volumeRendering.textureResource) return state.volumeRendering.descriptor;
  if (volumeRenderingTask) return volumeRenderingTask.promise;

  const deviceQualification = qualifyCanonicalVolumeForDevice(
    state.study.volume,
    state.volumeRendering.capabilities,
  );
  if (!deviceQualification.ready) {
    anatomyNote.textContent = `${deviceQualification.reason}. Synchronized MPR remains available.`;
    return null;
  }

  const task = { promise: null };
  task.promise = (async () => {
    anatomyNote.textContent = "Preparing patient volume for GPU rendering...";
    const response = await fetch("/api/studies/latest/volume-rendering", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(
        payload.detail || `3D volume preparation failed (${response.status})`,
      );
    }
    if (volumeRenderingTask !== task) {
      throw new DOMException("Patient volume texture load was superseded", "AbortError");
    }
    const descriptor = payload.volume_rendering;
    const qualification = validateVolumeRenderingDescriptor(
      descriptor,
      state.volumeRendering.capabilities,
    );
    if (!qualification.ready) throw new Error(qualification.reason);
    anatomyNote.textContent = "Downloading and verifying the patient volume texture...";
    const textureResource = await volumeTextureManager.load(descriptor);
    if (volumeRenderingTask !== task) {
      throw new DOMException("Patient volume texture load was superseded", "AbortError");
    }
    anatomyNote.textContent = "Compiling the true patient-volume ray marcher...";
    await activatePatientVolumeRendering(textureResource, task);
    if (volumeRenderingTask !== task) {
      throw new DOMException("Patient volume rendering was superseded", "AbortError");
    }
    state.volumeRendering.descriptor = descriptor;
    state.volumeRendering.textureResource = textureResource;
    anatomyNote.textContent = "True patient volume rendering active. Medical transfer functions and synchronized clipping follow in Phase 4D and Phase 4E.";
    return descriptor;
  })();
  volumeRenderingTask = task;

  try {
    return await task.promise;
  } catch (error) {
    if (volumeRenderingTask === task) {
      clearPatientVolumeRendering();
      volumeTextureManager.dispose();
      state.volumeRendering.descriptor = null;
      state.volumeRendering.textureResource = null;
      anatomyNote.textContent = error instanceof Error
        ? `${error.message}. Synchronized MPR remains available.`
        : "3D volume preparation failed. Synchronized MPR remains available.";
    }
    return null;
  } finally {
    if (volumeRenderingTask === task) volumeRenderingTask = null;
  }
}

const MPR_AXIS_INDEX = { x: 0, y: 1, z: 2 };

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function mprPlaneIndex(planeDescriptor) {
  const axis = MPR_AXIS_INDEX[planeDescriptor.normal_axis];
  const [minimum] = planeDescriptor.position_range_mm;
  const spacing = Number(planeDescriptor.slice_spacing_mm);
  const raw = Math.round((state.mpr.crosshairLpsMm[axis] - minimum) / spacing);
  return clamp(raw, 0, Number(planeDescriptor.slice_count) - 1);
}

function mprPositionForIndex(planeDescriptor, index) {
  return Number(planeDescriptor.position_range_mm[0])
    + Number(index) * Number(planeDescriptor.slice_spacing_mm);
}

function mprPhysicalMetrics(planeDescriptor) {
  const width = Math.max(1, Number(planeDescriptor.image_width) || 1);
  const height = Math.max(1, Number(planeDescriptor.image_height) || 1);
  const spacing = Array.isArray(planeDescriptor.pixel_spacing_mm)
    ? planeDescriptor.pixel_spacing_mm.map(Number)
    : [1, 1];
  const verticalSpacing = Number.isFinite(spacing[0]) && spacing[0] > 0 ? spacing[0] : 1;
  const horizontalSpacing = Number.isFinite(spacing[1]) && spacing[1] > 0 ? spacing[1] : 1;
  const hRange = Array.isArray(planeDescriptor.horizontal_range_mm)
    ? planeDescriptor.horizontal_range_mm.map(Number)
    : [0, Math.max(width - 1, 1) * horizontalSpacing];
  const vRange = Array.isArray(planeDescriptor.vertical_range_mm)
    ? planeDescriptor.vertical_range_mm.map(Number)
    : [0, Math.max(height - 1, 1) * verticalSpacing];
  const physicalWidth = Math.abs(hRange[1] - hRange[0])
    || Math.max(width - 1, 1) * horizontalSpacing;
  const physicalHeight = Math.abs(vRange[1] - vRange[0])
    || Math.max(height - 1, 1) * verticalSpacing;
  return { width, height, physicalWidth, physicalHeight };
}

function configureMprSurface(entry, planeDescriptor) {
  const frame = entry.view.getBoundingClientRect();
  const availableWidth = Math.max(frame.width, 1);
  const availableHeight = Math.max(frame.height, 1);
  const { physicalWidth, physicalHeight } = mprPhysicalMetrics(planeDescriptor);
  const aspect = physicalWidth / physicalHeight;

  let displayWidth = availableWidth;
  let displayHeight = displayWidth / aspect;
  if (displayHeight > availableHeight) {
    displayHeight = availableHeight;
    displayWidth = displayHeight * aspect;
  }

  // The diagnostic surface itself always fills the MPR viewport with black.
  // Only the patient image is contained inside that surface, preserving the
  // physical field of view without clipping, cropping or stretching anatomy.
  const imageWidth = Math.max(1, displayWidth);
  const imageHeight = Math.max(1, displayHeight);
  const imageLeft = Math.max(0, (availableWidth - imageWidth) / 2);
  const imageTop = Math.max(0, (availableHeight - imageHeight) / 2);
  const imageRight = imageLeft + imageWidth;
  const imageBottom = imageTop + imageHeight;

  entry.surface.style.width = "100%";
  entry.surface.style.height = "100%";
  entry.surface.style.setProperty("--mpr-image-width", `${imageWidth}px`);
  entry.surface.style.setProperty("--mpr-image-height", `${imageHeight}px`);
  entry.surface.style.setProperty("--mpr-image-left", `${imageLeft}px`);
  entry.surface.style.setProperty("--mpr-image-top", `${imageTop}px`);
  entry.surface.style.setProperty("--mpr-image-right", `${imageRight}px`);
  entry.surface.style.setProperty("--mpr-image-bottom", `${imageBottom}px`);
  entry.surface.style.setProperty("--mpr-image-center-x", `${imageLeft + imageWidth / 2}px`);
  entry.surface.style.setProperty("--mpr-image-center-y", `${imageTop + imageHeight / 2}px`);
  entry.imageRect = {
    left: imageLeft,
    top: imageTop,
    width: imageWidth,
    height: imageHeight,
    right: imageRight,
    bottom: imageBottom,
  };
  updateMprCrosshairOverlayForEntry(entry, planeDescriptor);
}

function updateMprCrosshairOverlayForEntry(entry, planeDescriptor) {
  const imageRect = entry.imageRect;
  if (!imageRect) return;
  const horizontalAxis = MPR_AXIS_INDEX[planeDescriptor.horizontal_axis];
  const verticalAxis = MPR_AXIS_INDEX[planeDescriptor.vertical_axis];
  const [hMin, hMax] = planeDescriptor.horizontal_range_mm.map(Number);
  const [vMin, vMax] = planeDescriptor.vertical_range_mm.map(Number);
  const hFraction = hMax > hMin
    ? (state.mpr.crosshairLpsMm[horizontalAxis] - hMin) / (hMax - hMin)
    : 0.5;
  let vFraction = vMax > vMin
    ? (state.mpr.crosshairLpsMm[verticalAxis] - vMin) / (vMax - vMin)
    : 0.5;
  if (planeDescriptor.vertical_reverse) vFraction = 1 - vFraction;

  const x = imageRect.left + clamp(hFraction, 0, 1) * imageRect.width;
  const y = imageRect.top + clamp(vFraction, 0, 1) * imageRect.height;
  entry.surface.style.setProperty("--mpr-crosshair-x-px", `${x}px`);
  entry.surface.style.setProperty("--mpr-crosshair-y-px", `${y}px`);
}

function updateMprCrosshairOverlays() {
  const descriptor = state.mpr.descriptor;
  if (!descriptor) return;
  for (const [plane, entry] of mprRegistry.entries()) {
    updateMprCrosshairOverlayForEntry(entry, descriptor.planes[plane]);
  }
}

function drawGray8(entry, pixels, width, height, planeDescriptor) {
  entry.canvas.width = width;
  entry.canvas.height = height;
  const context = entry.canvas.getContext("2d", { alpha: false });
  const image = context.createImageData(width, height);
  for (let source = 0, target = 0; source < pixels.length; source += 1, target += 4) {
    const value = pixels[source];
    image.data[target] = value;
    image.data[target + 1] = value;
    image.data[target + 2] = value;
    image.data[target + 3] = 255;
  }
  context.putImageData(image, 0, 0);
  configureMprSurface(entry, planeDescriptor);
}

async function renderMprPlane(plane, generation, signal) {
  const descriptor = state.mpr.descriptor;
  const entry = mprRegistry.get(plane);
  if (!descriptor || !entry) return;
  const planeDescriptor = descriptor.planes[plane];
  const index = mprPlaneIndex(planeDescriptor);
  const position = mprPositionForIndex(planeDescriptor, index);
  const params = new URLSearchParams({
    index: String(index),
    window: String(state.mpr.window),
    level: String(state.mpr.level),
  });
  const response = await fetch(`/api/studies/latest/mpr/${plane}?${params}`, {
    credentials: "same-origin",
    headers: { "Accept": "application/x-voxelatlas-gray8" },
    signal,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `MPR rendering failed (${response.status})`);
  }
  const width = Number(response.headers.get("X-VoxelAtlas-Width"));
  const height = Number(response.headers.get("X-VoxelAtlas-Height"));
  const buffer = new Uint8Array(await response.arrayBuffer());
  if (generation !== mprRenderGeneration) return;
  if (!Number.isInteger(width) || !Number.isInteger(height) || buffer.length !== width * height) {
    throw new Error("MPR image payload is invalid");
  }
  drawGray8(entry, buffer, width, height, planeDescriptor);
  entry.panel.dataset.volumeState = "ready";
  entry.index.textContent = `${index + 1} / ${planeDescriptor.slice_count}`;
  entry.position.textContent = `${planeDescriptor.coordinate}: ${position.toFixed(2)} mm`;
  entry.wl.textContent = `W: ${Math.round(state.mpr.window)}   L: ${Math.round(state.mpr.level)}`;
}

async function renderAllMprPlanes() {
  if (!state.mpr.descriptor) return;
  const generation = ++mprRenderGeneration;
  mprAbortController?.abort();
  mprAbortController = new AbortController();
  const signal = mprAbortController.signal;
  updateMprCrosshairOverlays();
  try {
    await Promise.all([
      renderMprPlane("axial", generation, signal),
      renderMprPlane("coronal", generation, signal),
      renderMprPlane("sagittal", generation, signal),
    ]);
    if (generation === mprRenderGeneration) {
      for (const entry of mprRegistry.values()) entry.panel.dataset.volumeState = "ready";
    }
  } catch (error) {
    if (generation !== mprRenderGeneration || error?.name === "AbortError") return;
    for (const entry of mprRegistry.values()) {
      entry.panel.dataset.volumeState = "loading";
      entry.message.textContent = error instanceof Error ? error.message : "MPR rendering failed";
    }
  }
}

function scheduleMprRender(delay = 0) {
  if (mprRenderTimer !== null) window.clearTimeout(mprRenderTimer);
  mprRenderTimer = window.setTimeout(() => {
    mprRenderTimer = null;
    void renderAllMprPlanes();
  }, delay);
}

async function ensureMprReady() {
  if (!state.study?.volume_ready) return null;
  if (state.mpr.descriptor) {
    scheduleMprRender();
    return state.mpr.descriptor;
  }
  if (mprDescriptorPromise) return mprDescriptorPromise;

  mprDescriptorPromise = (async () => {
    const response = await fetch("/api/studies/latest/mpr", {
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.mpr?.ready) {
      throw new Error(payload.detail || `MPR initialization failed (${response.status})`);
    }
    state.mpr.descriptor = payload.mpr;
    state.mpr.crosshairLpsMm = payload.mpr.crosshair_lps_mm.map(Number);
    state.mpr.window = Number(payload.mpr.default_window.width);
    state.mpr.level = Number(payload.mpr.default_window.level);
    for (const entry of mprRegistry.values()) {
      entry.panel.dataset.volumeState = "loading";
      entry.message.textContent = "Rendering patient volume...";
    }
    await renderAllMprPlanes();
    return payload.mpr;
  })();

  try {
    return await mprDescriptorPromise;
  } catch (error) {
    for (const entry of mprRegistry.values()) {
      entry.panel.dataset.volumeState = "loading";
      entry.message.textContent = error instanceof Error ? error.message : "MPR initialization failed";
    }
    return null;
  } finally {
    mprDescriptorPromise = null;
  }
}

function setMprCrosshairFromPointer(plane, event) {
  const descriptor = state.mpr.descriptor;
  const entry = mprRegistry.get(plane);
  if (!descriptor || !entry) return;
  const planeDescriptor = descriptor.planes[plane];
  const rect = entry.canvas.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) return;
  const x = clamp((event.clientX - rect.left) / rect.width, 0, 1);
  const y = clamp((event.clientY - rect.top) / rect.height, 0, 1);
  const hAxis = MPR_AXIS_INDEX[planeDescriptor.horizontal_axis];
  const vAxis = MPR_AXIS_INDEX[planeDescriptor.vertical_axis];
  const [hMin, hMax] = planeDescriptor.horizontal_range_mm.map(Number);
  const [vMin, vMax] = planeDescriptor.vertical_range_mm.map(Number);
  state.mpr.crosshairLpsMm[hAxis] = hMin + x * (hMax - hMin);
  const verticalFraction = planeDescriptor.vertical_reverse ? 1 - y : y;
  state.mpr.crosshairLpsMm[vAxis] = vMin + verticalFraction * (vMax - vMin);
  updateMprCrosshairOverlays();
  scheduleMprRender(35);
}

function stepMprSlice(plane, direction) {
  const descriptor = state.mpr.descriptor;
  if (!descriptor) return;
  const planeDescriptor = descriptor.planes[plane];
  const axis = MPR_AXIS_INDEX[planeDescriptor.normal_axis];
  const currentIndex = mprPlaneIndex(planeDescriptor);
  const nextIndex = clamp(currentIndex + direction, 0, Number(planeDescriptor.slice_count) - 1);
  state.mpr.crosshairLpsMm[axis] = mprPositionForIndex(planeDescriptor, nextIndex);
  updateMprCrosshairOverlays();
  scheduleMprRender(20);
}

function adjustMprWindowLevel(start, event) {
  const dx = event.clientX - start.x;
  const dy = event.clientY - start.y;
  const widthScale = Math.max(start.window / 240, 0.5);
  state.mpr.window = Math.max(1, start.window + dx * widthScale);
  state.mpr.level = start.level - dy * widthScale;
  for (const entry of mprRegistry.values()) {
    entry.wl.textContent = `W: ${Math.round(state.mpr.window)}   L: ${Math.round(state.mpr.level)}`;
  }
  scheduleMprRender(45);
}

for (const [plane, entry] of mprRegistry.entries()) {
  let pointerMode = null;
  let wlStart = null;
  entry.view.addEventListener("contextmenu", (event) => event.preventDefault());
  entry.view.addEventListener("pointerdown", (event) => {
    if (!state.mpr.descriptor || entry.panel.dataset.volumeState === "empty") return;
    if (event.button === 2) {
      pointerMode = "window-level";
      wlStart = { x: event.clientX, y: event.clientY, window: state.mpr.window, level: state.mpr.level };
      entry.view.dataset.interaction = "window-level";
    } else if (event.button === 0) {
      pointerMode = "crosshair";
      setMprCrosshairFromPointer(plane, event);
    } else {
      return;
    }
    entry.view.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  });
  entry.view.addEventListener("pointermove", (event) => {
    if (pointerMode === "crosshair") setMprCrosshairFromPointer(plane, event);
    if (pointerMode === "window-level" && wlStart) adjustMprWindowLevel(wlStart, event);
  });
  const finishPointer = (event) => {
    if (pointerMode !== null) entry.view.releasePointerCapture?.(event.pointerId);
    pointerMode = null;
    wlStart = null;
    delete entry.view.dataset.interaction;
  };
  entry.view.addEventListener("pointerup", finishPointer);
  entry.view.addEventListener("pointercancel", finishPointer);
  entry.view.addEventListener("wheel", (event) => {
    if (!state.mpr.descriptor) return;
    event.preventDefault();
    stepMprSlice(plane, event.deltaY >= 0 ? 1 : -1);
  }, { passive: false });
}

function centerMprCrosshair() {
  const descriptor = state.mpr.descriptor;
  if (!descriptor) return;
  const bounds = descriptor.patient_bounds_lps_mm;
  state.mpr.crosshairLpsMm = ["x", "y", "z"].map((axis) => {
    const range = Array.isArray(bounds?.[axis]) ? bounds[axis].map(Number) : [0, 0];
    return (range[0] + range[1]) / 2;
  });
  updateMprCrosshairOverlays();
  scheduleMprRender();
}

function resetMprWindowLevel() {
  const descriptor = state.mpr.descriptor;
  if (!descriptor) return;
  state.mpr.window = Number(descriptor.default_window.width);
  state.mpr.level = Number(descriptor.default_window.level);
  for (const entry of mprRegistry.values()) {
    entry.wl.textContent = `W: ${Math.round(state.mpr.window)}   L: ${Math.round(state.mpr.level)}`;
  }
  scheduleMprRender();
}

document.querySelectorAll("[data-mpr-center]").forEach((button) => {
  button.addEventListener("click", centerMprCrosshair);
});

document.querySelectorAll("[data-mpr-reset-window]").forEach((button) => {
  button.addEventListener("click", resetMprWindowLevel);
});


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
  const preferredUid = study.reconstruction_series_uid || study.primary_series_uid;
  return study.series.find((item) => item.series_instance_uid === preferredUid)
    || study.series[0]
    || null;
}

function geometrySummary(series) {
  const geometry = series?.geometry;
  if (!geometry) return "Geometry unavailable";
  if (!geometry.reconstruction_ready) {
    const count = Array.isArray(geometry.issues) ? geometry.issues.length : 0;
    return count > 0 ? `Geometry review - ${count} issue${count === 1 ? "" : "s"}` : "Geometry needs review";
  }
  const orientation = typeof geometry.orientation_label === "string"
    ? geometry.orientation_label.charAt(0).toUpperCase() + geometry.orientation_label.slice(1)
    : "Geometry";
  const spacing = Number(geometry.slice_spacing_mm);
  return Number.isFinite(spacing)
    ? `${orientation} • ${spacing.toFixed(3)} mm slice spacing`
    : `${orientation} • geometry ready`;
}

function setUploadStatus(kind, message) {
  uploadStatus.dataset.state = kind;
  uploadStatus.textContent = message;
}

function setPatientVolumeReadyStatus() {
  setUploadStatus("ready", "Patient volume and synchronized MPR ready.");
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
    const geometry = document.createElement("span");
    geometry.className = "series-dialog-geometry";
    geometry.dataset.state = series.geometry?.reconstruction_ready ? "ready" : "review";
    geometry.textContent = geometrySummary(series);
    const uid = document.createElement("small");
    uid.textContent = series.series_instance_uid || "Series UID unavailable";
    copy.append(title, metadata, geometry, uid);

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
  setWorkflowForStudy(study);
  setMprVolumeState(study);

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
    anatomyNote.textContent = "Upload CT or MRI data to build the canonical patient volume for direct 3D rendering.";
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
  anatomyNote.textContent = study.volume_ready
    ? "Patient volume and synchronized MPR are available. Preparing direct 3D volume rendering."
    : "Canonical patient volume construction is required before direct 3D rendering.";
  renderSeriesDialog(study);
  updateLayerUI();
}

async function ensureCanonicalVolume(study) {
  if (!study?.reconstruction_ready || study.volume_ready) return study;
  if (volumeBuildPromise) return volumeBuildPromise;

  volumeStatusRow.dataset.state = "pending";
  volumeStatusText.textContent = "Building patient volume...";
  setUploadStatus("uploading", "Geometry qualified. Building canonical patient volume...");

  volumeBuildPromise = (async () => {
    const response = await fetch("/api/studies/latest/volume", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `Patient volume construction failed (${response.status})`);
    }
    applyStudy(payload.study || null);
    setUploadStatus(
      "ready",
      "Canonical patient volume built. Loading synchronized MPR views...",
    );
    await ensureMprReady();
    setPatientVolumeReadyStatus();
    await ensureVolumeRenderingFoundation();
    return payload.study || null;
  })();

  try {
    return await volumeBuildPromise;
  } catch (error) {
    setUploadStatus(
      "error",
      error instanceof Error ? error.message : "Patient volume construction failed",
    );
    volumeStatusRow.dataset.state = "pending";
    volumeStatusText.textContent = "Geometry ready - volume construction failed";
    return study;
  } finally {
    volumeBuildPromise = null;
  }
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
      if (payload.study.volume_ready) {
        setUploadStatus("ready", "Stored canonical patient volume restored. Loading MPR views...");
        await ensureMprReady();
        setPatientVolumeReadyStatus();
        await ensureVolumeRenderingFoundation();
      } else if (payload.study.reconstruction_ready) {
        setUploadStatus("uploading", "Stored DICOM geometry restored. Building patient volume...");
        await ensureCanonicalVolume(payload.study);
      } else {
        setUploadStatus("warning", "Stored DICOM study restored. Geometry needs review before reconstruction.");
      }
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
    if (payload.study?.reconstruction_ready) {
      setUploadStatus(
        "ready",
        skipped > 0
          ? `Geometry ready. ${payload.study.file_count} DICOM instances accepted; ${skipped} file${skipped === 1 ? "" : "s"} skipped.`
          : `Geometry ready. ${payload.study.file_count} DICOM instances validated across ${payload.study.series_count} series.`,
      );
      await ensureCanonicalVolume(payload.study);
    } else {
      setUploadStatus("warning", "Study accepted. Geometry needs review before reconstruction.");
    }
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

function setViewerInteractionMode(mode) {
  const nextMode = mode === "pan" ? "pan" : "rotate";
  state.viewerInteractionMode = nextMode;
  if (nextMode === "pan") {
    controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
  } else {
    controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
  }
  controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
  rotateToolButton.classList.toggle("is-active", nextMode === "rotate");
  panToolButton.classList.toggle("is-active", nextMode === "pan");
  rotateToolButton.setAttribute("aria-pressed", nextMode === "rotate" ? "true" : "false");
  panToolButton.setAttribute("aria-pressed", nextMode === "pan" ? "true" : "false");
  renderer.domElement.style.cursor = nextMode === "pan" ? "grab" : "default";
  if (primaryInteractionHint) {
    primaryInteractionHint.textContent = nextMode === "pan" ? "Left drag - Pan" : "Left drag - Rotate";
  }
}

rotateToolButton.addEventListener("click", () => setViewerInteractionMode("rotate"));
panToolButton.addEventListener("click", () => setViewerInteractionMode("pan"));
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
  fullscreenButton.classList.toggle("is-active", active);
  fullscreenButton.setAttribute("title", active ? "Exit fullscreen" : "Fullscreen");
  resize();
});

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  clearPatientVolumeRendering();
  volumeTextureManager.dispose();
  state.volumeRendering.textureResource = null;
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
  if (state.mpr.descriptor) {
    for (const [plane, entry] of mprRegistry.entries()) {
      const planeDescriptor = state.mpr.descriptor.planes[plane];
      configureMprSurface(entry, planeDescriptor);
    }
  }
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
setViewerInteractionMode("rotate");
updateLayerUI();
resize();
loadSkull();
void refreshAccountName();
void refreshLatestStudy();

const timer = new THREE.Timer();
timer.connect(document);
window.addEventListener("pagehide", () => {
  volumeRayMarcher.dispose();
  volumeTextureManager.dispose();
  timer.dispose();
}, { once: true });
function animate(timestamp) {
  timer.update(timestamp);
  const dt = Math.min(timer.getDelta(), 0.05);

  if (state.autoRotate) {
    anatomyGroup.rotation.y += dt * 0.32;
  }

  controls.update();
  updateOrientationGizmo();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
