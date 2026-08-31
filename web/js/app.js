import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const SKULL_URL = "/assets/models/skull_full.glb";
const BRAIN_URL = "/assets/models/brain.glb";

const viewport = document.getElementById("viewport");
const modelStatus = document.getElementById("modelStatus");
const statusText = document.getElementById("statusText");
const modelChip = document.getElementById("modelChip");
const sectionSlider = document.getElementById("sectionSlider");
const sectionValue = document.getElementById("sectionValue");
const sectionButtons = Array.from(document.querySelectorAll("[data-section-axis]"));
const openingSlider = document.getElementById("openingSlider");
const openingValue = document.getElementById("openingValue");
const openingDescription = document.getElementById("openingDescription");
const layerButtons = Array.from(document.querySelectorAll("[data-layer]"));
const anatomyNote = document.getElementById("anatomyNote");
const opacitySlider = document.getElementById("opacitySlider");
const opacityValue = document.getElementById("opacityValue");
const resetButton = document.getElementById("resetButton");
const autoRotateButton = document.getElementById("autoRotateButton");
const logoutButton = document.getElementById("logoutButton");

const DEFAULT_OPENING = 0.58;
const DEFAULT_OPACITY = 0.94;

const state = {
  sectionAxis: "y",
  sectionDepth: 0,
  opacity: DEFAULT_OPACITY,
  layer: "skull",
  autoRotate: false,
  skullRoot: null,
  brainRoot: null,
  skullMeshes: [],
  brainMeshes: [],
  brainAvailable: false,
  size: new THREE.Vector3(1, 1, 1),
  min: new THREE.Vector3(),
  max: new THREE.Vector3(),
  cameraPosition: new THREE.Vector3(),
  cameraTarget: new THREE.Vector3(),
  sectionPlane: new THREE.Plane(new THREE.Vector3(0, -1, 0), 0),
};

const apertureUniforms = {
  opening: { value: DEFAULT_OPENING },
  center: { value: new THREE.Vector3() },
  maxRadii: { value: new THREE.Vector3() },
  minSuperiorRadius: { value: 0.01 },
};

let targetOpening = DEFAULT_OPENING;
let currentOpening = DEFAULT_OPENING;

const APERTURE = {
  centerXFraction: -0.019,
  centerZFraction: -0.040,
  centerAboveFraction: 0.109,
  maxRadiusXFraction: 0.455,
  maxRadiusYFraction: 0.380,
  maxRadiusZFraction: 0.430,
  minRadiusYFraction: 0.120,
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
renderer.toneMappingExposure = 1.02;
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

scene.add(new THREE.HemisphereLight(0xd6edff, 0x07111d, 2.2));

const key = new THREE.DirectionalLight(0xf2f8ff, 3.2);
key.position.set(0.7, 1.1, 0.9);
scene.add(key);

const fill = new THREE.DirectionalLight(0x8bc8f3, 1.4);
fill.position.set(-0.8, 0.25, 0.55);
scene.add(fill);

const rim = new THREE.DirectionalLight(0xa7dcff, 1.7);
rim.position.set(0.2, 0.45, -1.1);
scene.add(rim);

function setStatus(kind, message) {
  modelStatus.dataset.state = kind;
  statusText.textContent = message;
}

function createClinicalSkullMaterial() {
  const material = new THREE.MeshPhysicalMaterial({
    color: 0xeff5fa,
    roughness: 0.72,
    metalness: 0.01,
    clearcoat: 0.02,
    clearcoatRoughness: 0.62,
    transparent: true,
    opacity: state.opacity,
    depthWrite: state.opacity >= 0.995,
    side: THREE.DoubleSide,
    clippingPlanes: [],
  });

  material.onBeforeCompile = (shader) => {
    shader.uniforms.uOpening = apertureUniforms.opening;
    shader.uniforms.uApertureCenter = apertureUniforms.center;
    shader.uniforms.uApertureMaxRadii = apertureUniforms.maxRadii;
    shader.uniforms.uMinSuperiorRadius = apertureUniforms.minSuperiorRadius;

    shader.vertexShader = shader.vertexShader.replace(
      "#include <common>",
      `
      #include <common>
      varying vec3 vApertureWorldPosition;
      `,
    );

    shader.vertexShader = shader.vertexShader.replace(
      "#include <begin_vertex>",
      `
      #include <begin_vertex>
      vApertureWorldPosition = (modelMatrix * vec4(transformed, 1.0)).xyz;
      `,
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <common>",
      `
      #include <common>
      uniform float uOpening;
      uniform vec3 uApertureCenter;
      uniform vec3 uApertureMaxRadii;
      uniform float uMinSuperiorRadius;
      varying vec3 vApertureWorldPosition;
      `,
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <clipping_planes_fragment>",
      `
      #include <clipping_planes_fragment>
      if (uOpening > 0.0001) {
        float s = sqrt(clamp(uOpening, 0.0, 1.0));
        float radiusX = max(uApertureMaxRadii.x * s, 0.00015);
        float radiusZ = max(uApertureMaxRadii.z * s, 0.00015);
        float radiusY = mix(uMinSuperiorRadius, uApertureMaxRadii.y, s);
        vec3 local = vApertureWorldPosition - uApertureCenter;
        vec3 normalizedPosition = vec3(
          local.x / radiusX,
          local.y / radiusY,
          local.z / radiusZ
        );
        if (dot(normalizedPosition, normalizedPosition) < 1.0) {
          discard;
        }
      }
      `,
    );
  };

  material.customProgramCacheKey = () => "voxelatlas-va-aperture-1";
  return material;
}

function createClinicalBrainMaterial() {
  return new THREE.MeshPhysicalMaterial({
    color: 0xc9a4a7,
    roughness: 0.82,
    metalness: 0.0,
    clearcoat: 0.0,
    transparent: false,
    opacity: 1.0,
    side: THREE.DoubleSide,
    clippingPlanes: [],
  });
}

function configureApertureFromBounds(box) {
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  apertureUniforms.center.value.set(
    center.x + size.x * APERTURE.centerXFraction,
    box.max.y + size.y * APERTURE.centerAboveFraction,
    center.z + size.z * APERTURE.centerZFraction,
  );

  apertureUniforms.maxRadii.value.set(
    size.x * APERTURE.maxRadiusXFraction,
    size.y * APERTURE.maxRadiusYFraction,
    size.z * APERTURE.maxRadiusZFraction,
  );

  apertureUniforms.minSuperiorRadius.value = size.y * APERTURE.minRadiusYFraction;
}

function updateBoundsFromSkull() {
  const box = new THREE.Box3().setFromObject(state.skullRoot);
  box.getSize(state.size);
  state.min.copy(box.min);
  state.max.copy(box.max);
  configureApertureFromBounds(box);
  return box;
}

function fitCamera(box) {
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const radius = Math.max(sphere.radius, 0.01);
  // Preserve the proven VA framing so the whole skull is readable on first load.
  // The previous migration camera sat too close and cropped the anatomy.
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

function allMeshes() {
  return [...state.skullMeshes, ...state.brainMeshes];
}

function applySection() {
  updateSectionPlane();
  const enabled = state.sectionDepth > 0.001;

  for (const mesh of allMeshes()) {
    const material = mesh.material;
    const currentlyEnabled = Array.isArray(material.clippingPlanes) && material.clippingPlanes.length > 0;

    if (enabled && !currentlyEnabled) {
      material.clippingPlanes = [state.sectionPlane];
      material.needsUpdate = true;
    } else if (!enabled && currentlyEnabled) {
      material.clippingPlanes = [];
      material.needsUpdate = true;
    }
  }

  sectionValue.textContent = `${Math.round(state.sectionDepth * 100)}%`;
}

function applySkullOpacity() {
  for (const mesh of state.skullMeshes) {
    mesh.material.opacity = state.opacity;
    mesh.material.transparent = state.opacity < 0.995;
    mesh.material.depthWrite = state.opacity >= 0.995;
    mesh.material.needsUpdate = true;
  }
  opacityValue.textContent = `${Math.round(state.opacity * 100)}%`;
}

function descriptionForOpening(value) {
  if (value === 0) return "Closed skull";
  if (value < 20) return "Minimal access";
  if (value < 45) return "Small opening";
  if (value < 68) return "Standard opening";
  if (value < 88) return "Large opening";
  return "Wide exploratory opening";
}

function setOpening(value) {
  const normalized = THREE.MathUtils.clamp(Number(value), 0, 100);
  openingSlider.value = String(normalized);
  openingValue.textContent = `${Math.round(normalized)}%`;
  openingDescription.textContent = descriptionForOpening(Math.round(normalized));
  targetOpening = normalized / 100;
}

function updateLayerUI() {
  for (const button of layerButtons) {
    button.classList.toggle("is-active", button.dataset.layer === state.layer);
  }

  if (state.layer === "brain") {
    modelChip.textContent = "A0101 · Brain";
  } else if (state.layer === "combined") {
    modelChip.textContent = "A0101 · Skull + Brain";
  } else {
    modelChip.textContent = "A0101 · Skull";
  }
}

function applyLayerVisibility() {
  if (state.skullRoot) {
    state.skullRoot.visible = state.layer !== "brain";
  }
  if (state.brainRoot) {
    state.brainRoot.visible = state.layer !== "skull";
  }
  updateLayerUI();
}

function prepareBrain(root) {
  root.traverse((child) => {
    if (!child.isMesh) return;
    child.material = createClinicalBrainMaterial();
    child.castShadow = false;
    child.receiveShadow = false;
    state.brainMeshes.push(child);
  });
  state.brainRoot = root;
  anatomyGroup.add(root);
  applySection();
  applyLayerVisibility();
}

function loadBrain() {
  if (state.brainRoot) {
    return Promise.resolve(state.brainRoot);
  }

  return new Promise((resolve, reject) => {
    const loader = new GLTFLoader();
    loader.load(
      BRAIN_URL,
      (gltf) => {
        prepareBrain(gltf.scene);
        resolve(gltf.scene);
      },
      undefined,
      reject,
    );
  });
}

async function setLayer(layer) {
  if ((layer === "brain" || layer === "combined") && !state.brainAvailable) {
    return;
  }

  if ((layer === "brain" || layer === "combined") && !state.brainRoot) {
    setStatus("loading", "Loading brain layer…");
    try {
      await loadBrain();
      setStatus("ready", "Anatomy ready");
    } catch (error) {
      console.error(error);
      state.brainAvailable = false;
      for (const button of layerButtons) {
        if (button.dataset.layer !== "skull") button.disabled = true;
      }
      anatomyNote.textContent = "Brain layer could not be loaded. Verify web/assets/models/brain.glb.";
      setStatus("error", "Brain layer unavailable");
      return;
    }
  }

  state.layer = layer;
  applyLayerVisibility();
}

async function probeBrainAsset() {
  try {
    const response = await fetch(BRAIN_URL, {
      method: "HEAD",
      cache: "no-store",
      credentials: "same-origin",
    });
    state.brainAvailable = response.ok;
  } catch {
    state.brainAvailable = false;
  }

  for (const button of layerButtons) {
    if (button.dataset.layer !== "skull") {
      button.disabled = !state.brainAvailable;
    }
  }

  anatomyNote.textContent = state.brainAvailable
    ? "Co-registered brain layer available."
    : "Brain layer activates when a co-registered brain.glb is available.";
}

function prepareSkull(root) {
  state.skullRoot = root;
  state.skullMeshes = [];

  root.traverse((child) => {
    if (!child.isMesh) return;
    child.material = createClinicalSkullMaterial();
    child.castShadow = false;
    child.receiveShadow = false;
    state.skullMeshes.push(child);
  });

  anatomyGroup.add(root);
  root.updateMatrixWorld(true);
  const box = updateBoundsFromSkull();
  fitCamera(box);
  applySkullOpacity();
  applySection();
  applyLayerVisibility();
}

function loadSkull() {
  setStatus("loading", "Loading skull…");
  const loader = new GLTFLoader();
  loader.load(
    SKULL_URL,
    (gltf) => {
      prepareSkull(gltf.scene);
      setStatus("ready", "Anatomy ready");
      void probeBrainAsset();
    },
    (progress) => {
      if (!progress.total) return;
      const percent = Math.round((progress.loaded / progress.total) * 100);
      setStatus("loading", `Loading skull… ${percent}%`);
    },
    (error) => {
      console.error(error);
      setStatus("error", "Skull failed to load");
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
  setOpening(58);
  state.opacity = DEFAULT_OPACITY;
  opacitySlider.value = String(Math.round(DEFAULT_OPACITY * 100));
  applySkullOpacity();
  applySection();

  anatomyGroup.rotation.set(0, 0, 0);
  camera.position.copy(state.cameraPosition);
  controls.target.copy(state.cameraTarget);
  controls.update();
}

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

openingSlider.addEventListener("input", () => {
  setOpening(openingSlider.value);
});

opacitySlider.addEventListener("input", () => {
  state.opacity = Number(opacitySlider.value) / 100;
  applySkullOpacity();
});

layerButtons.forEach((button) => {
  button.addEventListener("click", () => {
    void setLayer(button.dataset.layer);
  });
});

resetButton.addEventListener("click", resetWorkspace);

autoRotateButton.addEventListener("click", () => {
  state.autoRotate = !state.autoRotate;
  autoRotateButton.classList.toggle("is-active", state.autoRotate);
  autoRotateButton.textContent = state.autoRotate ? "Stop rotate" : "Auto rotate";
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

setOpening(58);
applySkullOpacity();
updateLayerUI();
resize();
loadSkull();

const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05);
  const response = 1 - Math.exp(-18 * dt);
  currentOpening = THREE.MathUtils.lerp(currentOpening, targetOpening, response);
  if (Math.abs(currentOpening - targetOpening) < 0.0001) {
    currentOpening = targetOpening;
  }
  apertureUniforms.opening.value = currentOpening;

  if (state.autoRotate) {
    anatomyGroup.rotation.y += dt * 0.32;
  }

  controls.update();
  renderer.render(scene, camera);
}
animate();
