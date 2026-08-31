import * as THREE from "three";

import {
  GLTFLoader
} from "three/addons/loaders/GLTFLoader.js";

import {
  OrbitControls
} from "three/addons/controls/OrbitControls.js";


const VERSION =
  "v2b3b-7";

/*
 * Fast-V1 AR bridge.
 *
 * This opens the already validated production AR-enabled
 * experience. Direct section-state transfer into AR belongs
 * to the post-V1 integration.
 */
const AR_URL =
  "https://em.eiatech.ma/ar/";


const viewport =
  document.getElementById(
    "viewport"
  );

const statusText =
  document.getElementById(
    "statusText"
  );


const sectionSlider =
  document.getElementById(
    "sectionSlider"
  );

const sectionValue =
  document.getElementById(
    "sectionValue"
  );

const sectionButtons =
  Array.from(
    document.querySelectorAll(
      "[data-section-axis]"
    )
  );


const opacitySlider =
  document.getElementById(
    "opacitySlider"
  );

const opacityValue =
  document.getElementById(
    "opacityValue"
  );


const presetButtons =
  Array.from(
    document.querySelectorAll(
      "[data-preset]"
    )
  );


const resetButton =
  document.getElementById(
    "resetButton"
  );

const autoRotateButton =
  document.getElementById(
    "autoRotateButton"
  );

const arButton =
  document.getElementById(
    "arButton"
  );


const state = {

  sectionAxis: "y",

  sectionDepth: 0,

  opacity: 0.78,

  preset: "xr",

  autoRotate: false,

  root: null,

  meshes: [],

  size:
    new THREE.Vector3(
      1,
      1,
      1
    ),

  min:
    new THREE.Vector3(),

  max:
    new THREE.Vector3(),

  cameraPosition:
    new THREE.Vector3(),

  cameraTarget:
    new THREE.Vector3(),

  sectionPlane:
    new THREE.Plane(
      new THREE.Vector3(
        0,
        -1,
        0
      ),
      0
    ),

};


const scene =
  new THREE.Scene();


const camera =
  new THREE.PerspectiveCamera(
    29,
    1,
    0.005,
    40
  );


const renderer =
  new THREE.WebGLRenderer({

    antialias: true,

    alpha: true,

    powerPreference:
      "high-performance",

  });


renderer.setPixelRatio(
  Math.min(
    window.devicePixelRatio || 1,
    2
  )
);

renderer.setClearColor(
  0x000000,
  0
);

renderer.localClippingEnabled =
  true;


viewport.appendChild(
  renderer.domElement
);


/* ============================================================
   ORBIT / PAN / TOUCH
   ============================================================ */


const controls =
  new OrbitControls(
    camera,
    renderer.domElement
  );


controls.enableDamping =
  true;

controls.dampingFactor =
  0.07;


controls.enableRotate =
  true;

controls.enablePan =
  true;

controls.enableZoom =
  true;


controls.rotateSpeed =
  0.78;

controls.panSpeed =
  0.55;

controls.zoomSpeed =
  0.95;


controls.screenSpacePanning =
  true;


controls.minPolarAngle =
  0.01;

controls.maxPolarAngle =
  Math.PI - 0.01;


controls.mouseButtons = {

  LEFT:
    THREE.MOUSE.ROTATE,

  MIDDLE:
    THREE.MOUSE.DOLLY,

  RIGHT:
    THREE.MOUSE.PAN,

};


controls.touches = {

  ONE:
    THREE.TOUCH.ROTATE,

  TWO:
    THREE.TOUCH.DOLLY_PAN,

};


renderer.domElement
  .addEventListener(
    "contextmenu",
    (event) => {

      event.preventDefault();

    }
  );


/* ============================================================
   LIGHTING
   ============================================================ */


const hemisphere =
  new THREE.HemisphereLight(
    0xe5f4ff,
    0x071019,
    1.38
  );

scene.add(
  hemisphere
);


const key =
  new THREE.DirectionalLight(
    0xffffff,
    1.35
  );

key.position.set(
  3,
  4,
  4
);

scene.add(
  key
);


const fill =
  new THREE.DirectionalLight(
    0x9bd6ff,
    0.48
  );

fill.position.set(
  -4,
  1,
  3
);

scene.add(
  fill
);


const rim =
  new THREE.DirectionalLight(
    0x4ab9ff,
    0.30
  );

rim.position.set(
  -2,
  3,
  -4
);

scene.add(
  rim
);


/* ============================================================
   UI
   ============================================================ */


function setStatus(
  message
) {

  statusText.textContent =
    message;

}


function updateUI() {

  const sectionPercent =
    Math.round(
      state.sectionDepth *
      100
    );


  sectionValue.textContent =
    `${sectionPercent}%`;


  sectionSlider.value =
    String(
      sectionPercent
    );


  opacityValue.textContent =
    `${Math.round(
      state.opacity *
      100
    )}%`;


  sectionButtons.forEach(
    (button) => {

      button.classList.toggle(

        "is-active",

        button.dataset
          .sectionAxis ===
          state.sectionAxis

      );

    }
  );


  presetButtons.forEach(
    (button) => {

      button.classList.toggle(

        "is-active",

        button.dataset.preset ===
          state.preset

      );

    }
  );


  autoRotateButton
    .classList.toggle(
      "is-active",
      state.autoRotate
    );


  autoRotateButton.textContent =
    state.autoRotate
      ? "Stop rotate"
      : "Auto rotate";

}


/* ============================================================
   MATERIAL
   ============================================================ */


function presetConfig(
  preset
) {

  if (
    preset ===
    "clinical"
  ) {

    return {

      color:
        "#eff5fa",

      roughness:
        0.72,

      metalness:
        0.01,

      clearcoat:
        0.02,

      clearcoatRoughness:
        0.42,

      transmission:
        0.0,

      emissive:
        "#000000",

      emissiveIntensity:
        0.0,

    };

  }


  if (
    preset ===
    "holo"
  ) {

    return {

      color:
        "#b9e5ff",

      roughness:
        0.22,

      metalness:
        0.05,

      clearcoat:
        0.72,

      clearcoatRoughness:
        0.12,

      transmission:
        0.30,

      emissive:
        "#06455e",

      emissiveIntensity:
        0.18,

    };

  }


  return {

    color:
      "#edf7ff",

    roughness:
      0.40,

    metalness:
      0.04,

    clearcoat:
      0.46,

    clearcoatRoughness:
      0.16,

    transmission:
      0.08,

    emissive:
      "#031117",

    emissiveIntensity:
      0.05,

  };

}


function createSkullMaterial() {

  const config =
    presetConfig(
      state.preset
    );


  return new THREE.MeshPhysicalMaterial({

    color:
      new THREE.Color(
        config.color
      ),

    roughness:
      config.roughness,

    metalness:
      config.metalness,

    clearcoat:
      config.clearcoat,

    clearcoatRoughness:
      config.clearcoatRoughness,

    transmission:
      config.transmission,

    emissive:
      new THREE.Color(
        config.emissive
      ),

    emissiveIntensity:
      config.emissiveIntensity,

    transparent:
      true,

    opacity:
      state.opacity,

    side:
      THREE.DoubleSide,

    clippingPlanes:
      [],

  });

}


/* ============================================================
   SECTIONING
   ============================================================ */


function updateSectionPlane() {

  const t =
    THREE.MathUtils.clamp(
      state.sectionDepth,
      0,
      1
    );


  if (
    state.sectionAxis ===
    "x"
  ) {

    const x =
      THREE.MathUtils.lerp(

        state.max.x +
          state.size.x *
          0.02,

        state.min.x,

        t

      );


    state.sectionPlane
      .setFromNormalAndCoplanarPoint(

        new THREE.Vector3(
          -1,
          0,
          0
        ),

        new THREE.Vector3(
          x,
          0,
          0
        )

      );


    return;

  }


  if (
    state.sectionAxis ===
    "z"
  ) {

    const z =
      THREE.MathUtils.lerp(

        state.max.z +
          state.size.z *
          0.02,

        state.min.z,

        t

      );


    state.sectionPlane
      .setFromNormalAndCoplanarPoint(

        new THREE.Vector3(
          0,
          0,
          -1
        ),

        new THREE.Vector3(
          0,
          0,
          z
        )

      );


    return;

  }


  const y =
    THREE.MathUtils.lerp(

      state.max.y +
        state.size.y *
        0.02,

      state.min.y,

      t

    );


  state.sectionPlane
    .setFromNormalAndCoplanarPoint(

      new THREE.Vector3(
        0,
        -1,
        0
      ),

      new THREE.Vector3(
        0,
        y,
        0
      )

    );

}


function applySection() {

  updateSectionPlane();


  const enabled =
    state.sectionDepth >
    0.001;


  state.meshes.forEach(
    (mesh) => {

      const material =
        mesh.material;


      const currentlyEnabled =
        Array.isArray(
          material.clippingPlanes
        ) &&
        material.clippingPlanes.length >
          0;


      if (
        enabled &&
        !currentlyEnabled
      ) {

        material.clippingPlanes =
          [
            state.sectionPlane
          ];

        material.needsUpdate =
          true;

      }


      if (
        !enabled &&
        currentlyEnabled
      ) {

        material.clippingPlanes =
          [];

        material.needsUpdate =
          true;

      }

    }
  );


  updateUI();

}


/* ============================================================
   APPEARANCE
   ============================================================ */


function applyPreset() {

  const config =
    presetConfig(
      state.preset
    );


  state.meshes.forEach(
    (mesh) => {

      const material =
        mesh.material;


      material.color.set(
        config.color
      );


      material.roughness =
        config.roughness;


      material.metalness =
        config.metalness;


      material.clearcoat =
        config.clearcoat;


      material.clearcoatRoughness =
        config.clearcoatRoughness;


      material.transmission =
        config.transmission;


      material.emissive.set(
        config.emissive
      );


      material.emissiveIntensity =
        config.emissiveIntensity;


      material.needsUpdate =
        true;

    }
  );


  updateUI();

}


function applyOpacity() {

  state.meshes.forEach(
    (mesh) => {

      mesh.material.opacity =
        state.opacity;


      mesh.material.transparent =
        true;


      mesh.material.depthWrite =
        state.opacity >
        0.96;


      mesh.material.needsUpdate =
        true;

    }
  );


  updateUI();

}


/* ============================================================
   CAMERA
   ============================================================ */


function fitCamera() {

  const radius =
    state.size.length() *
    0.91;


  const position =
    new THREE.Vector3(

      radius * 0.84,

      radius * 0.43,

      radius * 1.50

    );


  const target =
    new THREE.Vector3(

      0,

      state.size.y *
        0.015,

      0

    );


  camera.position.copy(
    position
  );


  controls.target.copy(
    target
  );


  state.cameraPosition.copy(
    position
  );


  state.cameraTarget.copy(
    target
  );


  controls.minDistance =
    radius *
    0.55;


  controls.maxDistance =
    radius *
    4.5;


  camera.near =
    0.005;


  camera.far =
    40;


  camera.updateProjectionMatrix();


  controls.update();

}


function resetWorkspace() {

  /*
   * Reset camera + active section only.
   * Appearance and opacity remain user-selected.
   */

  state.sectionDepth =
    0;


  sectionSlider.value =
    "0";


  applySection();


  camera.position.copy(
    state.cameraPosition
  );


  controls.target.copy(
    state.cameraTarget
  );


  controls.update();

}


/* ============================================================
   MODEL
   ============================================================ */


function prepareModel(
  root
) {

  const initialBox =
    new THREE.Box3()
      .setFromObject(
        root
      );


  const center =
    initialBox.getCenter(
      new THREE.Vector3()
    );


  root.position.sub(
    center
  );


  const box =
    new THREE.Box3()
      .setFromObject(
        root
      );


  box.getSize(
    state.size
  );


  state.min.copy(
    box.min
  );


  state.max.copy(
    box.max
  );


  state.meshes =
    [];


  root.traverse(
    (child) => {

      if (
        !child.isMesh
      ) {
        return;
      }


      child.material =
        createSkullMaterial();


      child.castShadow =
        false;


      child.receiveShadow =
        false;


      state.meshes.push(
        child
      );

    }
  );


  fitCamera();

  applyPreset();

  applyOpacity();

  applySection();

}


function loadModel() {

  setStatus(
    "Loading model…"
  );


  const loader =
    new GLTFLoader();


  loader.load(

    `./assets/skull_full.glb?v=${VERSION}`,

    (gltf) => {

      state.root =
        gltf.scene;


      scene.add(
        state.root
      );


      prepareModel(
        state.root
      );


      setStatus(
        "Model ready"
      );

    },


    undefined,


    (error) => {

      console.error(
        error
      );


      setStatus(
        "Model load failed"
      );

    }

  );

}


/* ============================================================
   EVENTS
   ============================================================ */


sectionButtons.forEach(
  (button) => {

    button.addEventListener(
      "click",
      () => {

        const nextAxis =
          button.dataset
            .sectionAxis;


        if (
          nextAxis ===
          state.sectionAxis
        ) {

          return;

        }


        /*
         * Predictable UX:
         * switching direction always returns to the
         * complete model rather than unexpectedly
         * clipping from the previous percentage.
         */

        state.sectionAxis =
          nextAxis;


        state.sectionDepth =
          0;


        sectionSlider.value =
          "0";


        applySection();

      }
    );

  }
);


sectionSlider.addEventListener(
  "input",
  () => {

    state.sectionDepth =
      Number(
        sectionSlider.value
      ) /
      100;


    applySection();

  }
);


opacitySlider.addEventListener(
  "input",
  () => {

    state.opacity =
      Number(
        opacitySlider.value
      ) /
      100;


    applyOpacity();

  }
);


presetButtons.forEach(
  (button) => {

    button.addEventListener(
      "click",
      () => {

        state.preset =
          button.dataset
            .preset;


        applyPreset();

      }
    );

  }
);


resetButton.addEventListener(
  "click",
  () => {

    resetWorkspace();

  }
);


autoRotateButton.addEventListener(
  "click",
  () => {

    state.autoRotate =
      !state.autoRotate;


    updateUI();

  }
);


arButton.addEventListener(
  "click",
  () => {

    window.open(
      AR_URL,
      "_blank",
      "noopener,noreferrer"
    );

  }
);


/* ============================================================
   RESPONSIVE CANVAS
   ============================================================ */


function resize() {

  const width =
    Math.max(
      1,
      viewport.clientWidth
    );


  const height =
    Math.max(
      1,
      viewport.clientHeight
    );


  camera.aspect =
    width /
    height;


  camera.updateProjectionMatrix();


  renderer.setSize(
    width,
    height,
    false
  );

}


window.addEventListener(
  "resize",
  resize,
  {
    passive: true
  }
);


if (
  window.ResizeObserver
) {

  const resizeObserver =
    new ResizeObserver(
      () => {

        resize();

      }
    );


  resizeObserver.observe(
    viewport
  );

}


/* ============================================================
   RENDER
   ============================================================ */


function animate() {

  requestAnimationFrame(
    animate
  );


  if (
    state.autoRotate
  ) {

    controls.rotateLeft(
      0.0034
    );

  }


  controls.update();


  renderer.render(
    scene,
    camera
  );

}


updateUI();

resize();

loadModel();

animate();
