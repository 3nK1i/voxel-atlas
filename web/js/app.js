const viewer = document.getElementById("skullViewer");

const statusPill = document.getElementById("statusPill");
const statusText = document.getElementById("statusText");

const modeChip = document.getElementById("modeChip");
const modeStat = document.getElementById("modeStat");
const triangleStat = document.getElementById("triangleStat");
const heightStat = document.getElementById("heightStat");
const presetStat = document.getElementById("presetStat");

const opacityInput = document.getElementById("opacityInput");
const opacityValue = document.getElementById("opacityValue");

const autoRotateButton = document.getElementById("autoRotateButton");
const resetViewButton = document.getElementById("resetViewButton");
const arButton = document.getElementById("arButton");

const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));
const presetButtons = Array.from(document.querySelectorAll("[data-preset]"));

const VERSION = "v2b2-5";

const MODELS = {
  full: {
    src: `./assets/models/skull_full.glb?${VERSION}`,
    label: "Closed skull",
    chip: "Closed skull",
    triangles: "199,999",
    height: "~220 mm",
  },
  open: {
    src: `./assets/models/skull_open.glb?${VERSION}`,
    label: "Open cranial view",
    chip: "Open cranial view",
    triangles: "250,000",
    height: "~209 mm",
  },
};

const PRESETS = {
  clinical: {
    label: "Clinical",
    opacity: 96,
    color: [0.96, 0.98, 1.0],
    metallic: 0.02,
    roughness: 0.62,
  },
  xr: {
    label: "Premium XR",
    opacity: 78,
    color: [0.88, 0.94, 1.0],
    metallic: 0.05,
    roughness: 0.42,
  },
  holo: {
    label: "Holographic",
    opacity: 50,
    color: [0.74, 0.90, 1.0],
    metallic: 0.08,
    roughness: 0.26,
  },
};

const DEFAULT_VIEW = {
  cameraOrbit: "-25deg 72deg 0.48m",
  fieldOfView: "26deg",
};

const state = {
  mode: "open",
  preset: "xr",
  opacity: 78,
  autoRotate: true,
};

function setStatus(kind, text) {
  statusPill.dataset.state = kind;
  statusText.textContent = text;
}

function updateButtonStates() {
  for (const button of modeButtons) {
    button.classList.toggle("is-active", button.dataset.mode === state.mode);
  }

  for (const button of presetButtons) {
    button.classList.toggle("is-active", button.dataset.preset === state.preset);
  }

  autoRotateButton.textContent = state.autoRotate ? "Pause rotation" : "Auto rotate";
}

function updateStats() {
  const mode = MODELS[state.mode];
  const preset = PRESETS[state.preset];

  modeChip.textContent = mode.chip;
  modeStat.textContent = mode.label;
  triangleStat.textContent = mode.triangles;
  heightStat.textContent = mode.height;
  presetStat.textContent = preset.label;
}

function applyMaterial() {
  if (!viewer.model) {
    return;
  }

  const preset = PRESETS[state.preset];
  const alpha = state.opacity / 100;

  for (const material of viewer.model.materials) {
    try {
      if (typeof material.setAlphaMode === "function") {
        material.setAlphaMode(alpha < 0.995 ? "BLEND" : "OPAQUE");
      }

      if (material.pbrMetallicRoughness) {
        const pbr = material.pbrMetallicRoughness;

        if (typeof pbr.setBaseColorFactor === "function") {
          pbr.setBaseColorFactor([
            preset.color[0],
            preset.color[1],
            preset.color[2],
            alpha,
          ]);
        }

        if (typeof pbr.setMetallicFactor === "function") {
          pbr.setMetallicFactor(preset.metallic);
        }

        if (typeof pbr.setRoughnessFactor === "function") {
          pbr.setRoughnessFactor(preset.roughness);
        }
      }
    } catch (error) {
      console.warn("Material styling warning:", error);
    }
  }

  opacityValue.textContent = `${state.opacity}%`;
}

function setMode(mode) {
  if (!MODELS[mode]) {
    return;
  }

  state.mode = mode;
  updateButtonStates();
  updateStats();

  setStatus("loading", "Loading 3D model…");
  viewer.setAttribute("src", MODELS[mode].src);
}

function setPreset(presetName) {
  if (!PRESETS[presetName]) {
    return;
  }

  state.preset = presetName;
  state.opacity = PRESETS[presetName].opacity;
  opacityInput.value = String(state.opacity);

  updateButtonStates();
  updateStats();
  applyMaterial();
}

function resetView() {
  viewer.cameraOrbit = DEFAULT_VIEW.cameraOrbit;
  viewer.fieldOfView = DEFAULT_VIEW.fieldOfView;

  if (typeof viewer.jumpCameraToGoal === "function") {
    viewer.jumpCameraToGoal();
  }
}

function toggleAutoRotate() {
  state.autoRotate = !state.autoRotate;
  viewer.autoRotate = state.autoRotate;
  updateButtonStates();
}

async function launchAR() {
  try {
    if (typeof viewer.activateAR === "function") {
      await viewer.activateAR();
    } else {
      console.warn("AR activation is not available on this browser.");
    }
  } catch (error) {
    console.warn("AR launch failed:", error);
  }
}

for (const button of modeButtons) {
  button.addEventListener("click", () => {
    setMode(button.dataset.mode);
  });
}

for (const button of presetButtons) {
  button.addEventListener("click", () => {
    setPreset(button.dataset.preset);
  });
}

opacityInput.addEventListener("input", () => {
  state.opacity = Number(opacityInput.value);
  opacityValue.textContent = `${state.opacity}%`;
  applyMaterial();
});

autoRotateButton.addEventListener("click", toggleAutoRotate);
resetViewButton.addEventListener("click", resetView);
arButton.addEventListener("click", launchAR);

viewer.addEventListener("progress", (event) => {
  const progress = Math.round((event.detail.totalProgress || 0) * 100);

  if (progress < 100) {
    setStatus("loading", `Loading 3D model… ${progress}%`);
  }
});

viewer.addEventListener("load", () => {
  applyMaterial();
  resetView();
  setStatus("ready", "3D model ready");
});

viewer.addEventListener("error", () => {
  setStatus("error", "Model failed to load");
});

viewer.addEventListener("ar-status", (event) => {
  const status = event.detail.status;

  if (status === "session-started") {
    setStatus("ready", "AR session started");
  } else if (status === "not-presenting") {
    setStatus("ready", "3D model ready");
  } else if (status === "failed") {
    setStatus("error", "AR launch failed");
  }
});

viewer.autoRotate = true;
opacityInput.value = String(state.opacity);

updateButtonStates();
updateStats();
setStatus("loading", "Loading 3D model…");
