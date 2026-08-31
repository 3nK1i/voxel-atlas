import * as THREE from "three";

import {
  GLTFLoader
} from "three/addons/loaders/GLTFLoader.js";

import {
  OrbitControls
} from "three/addons/controls/OrbitControls.js";


/* ============================================================
   DOM
   ============================================================ */


const viewport =
  document.getElementById("viewport");

const status =
  document.getElementById("status");

const statusText =
  document.getElementById("statusText");

const slider =
  document.getElementById("openingSlider");

const openingValue =
  document.getElementById("openingValue");

const openingDescription =
  document.getElementById("openingDescription");

const presetButtons =
  Array.from(
    document.querySelectorAll(
      "[data-opening]"
    )
  );


/* ============================================================
   RENDERER
   ============================================================ */


const renderer =
  new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: "high-performance",
  });


renderer.setPixelRatio(
  Math.min(
    window.devicePixelRatio || 1,
    2
  )
);


renderer.outputColorSpace =
  THREE.SRGBColorSpace;


renderer.toneMapping =
  THREE.ACESFilmicToneMapping;


renderer.toneMappingExposure =
  1.08;


viewport.appendChild(
  renderer.domElement
);


/* ============================================================
   SCENE / CAMERA
   ============================================================ */


const scene =
  new THREE.Scene();


const camera =
  new THREE.PerspectiveCamera(
    27,
    1,
    0.01,
    10
  );


const controls =
  new OrbitControls(
    camera,
    renderer.domElement
  );


controls.enableDamping = true;
controls.dampingFactor = 0.075;

controls.enablePan = false;

controls.rotateSpeed = 0.70;
controls.zoomSpeed = 0.85;

controls.minPolarAngle = 0.01;
controls.maxPolarAngle =
  Math.PI - 0.01;


/* ============================================================
   LIGHTING
   ============================================================ */


const hemi =
  new THREE.HemisphereLight(
    0xc8e8ff,
    0x07101c,
    2.0
  );


scene.add(hemi);


const key =
  new THREE.DirectionalLight(
    0xe8f5ff,
    4.0
  );


key.position.set(
  0.7,
  1.1,
  0.9
);


scene.add(key);


const fill =
  new THREE.DirectionalLight(
    0x78bff5,
    2.0
  );


fill.position.set(
  -0.8,
  0.3,
  0.5
);


scene.add(fill);


const rim =
  new THREE.DirectionalLight(
    0x9ddcff,
    2.5
  );


rim.position.set(
  0.2,
  0.5,
  -1.1
);


scene.add(rim);


/* ============================================================
   APERTURE STATE
   ============================================================ */


const apertureUniforms = {

  opening: {
    value: 0.58
  },

  center: {
    value: new THREE.Vector3()
  },

  maxRadii: {
    value: new THREE.Vector3()
  },

  minSuperiorRadius: {
    value: 0.01
  },

};


let targetOpening = 0.58;
let currentOpening = 0.58;


/*
 * Geometry ratios are derived from our previously selected
 * A0101 medium oval cutaway:
 *
 * selected medium:
 *   horizontal radius ≈ 52 mm
 *   depth radius      ≈ 62 mm
 *   superior radius   ≈ 72 mm
 *   cutter center     ≈ 24 mm above superior skull
 *
 * 58% is intentionally calibrated to approximate that
 * existing medium opening.
 */

const APERTURE = {

  centerXFraction: -0.019,

  centerZFraction: -0.040,

  centerAboveFraction: 0.109,

  maxRadiusXFraction: 0.455,

  maxRadiusYFraction: 0.380,

  maxRadiusZFraction: 0.430,

  minRadiusYFraction: 0.120,

};


/* ============================================================
   MATERIAL
   ============================================================ */


function createApertureMaterial() {

  const material =
    new THREE.MeshPhysicalMaterial({

      color: new THREE.Color(
        0xdcecff
      ),

      metalness: 0.06,

      roughness: 0.34,

      clearcoat: 0.12,

      clearcoatRoughness: 0.42,

      side: THREE.DoubleSide,

    });


  material.onBeforeCompile =
    (shader) => {

      shader.uniforms.uOpening =
        apertureUniforms.opening;

      shader.uniforms.uApertureCenter =
        apertureUniforms.center;

      shader.uniforms.uApertureMaxRadii =
        apertureUniforms.maxRadii;

      shader.uniforms.uMinSuperiorRadius =
        apertureUniforms.minSuperiorRadius;


      shader.vertexShader =
        shader.vertexShader.replace(

          "#include <common>",

          `
          #include <common>

          varying vec3 vApertureWorldPosition;
          `

        );


      /*
       * Do not depend on Three.js' conditional
       * <worldpos_vertex> chunk.
       *
       * modelMatrix is always available for a normal mesh.
       * "transformed" contains the current local vertex.
       */
      shader.vertexShader =
        shader.vertexShader.replace(

          "#include <begin_vertex>",

          `
          #include <begin_vertex>

          vApertureWorldPosition =
            (
              modelMatrix *
              vec4(transformed, 1.0)
            ).xyz;
          `

        );


      shader.fragmentShader =
        shader.fragmentShader.replace(

          "#include <common>",

          `
          #include <common>

          uniform float uOpening;

          uniform vec3 uApertureCenter;

          uniform vec3 uApertureMaxRadii;

          uniform float uMinSuperiorRadius;

          varying vec3 vApertureWorldPosition;
          `

        );


      shader.fragmentShader =
        shader.fragmentShader.replace(

          "#include <clipping_planes_fragment>",

          `
          #include <clipping_planes_fragment>

          /*
           * Continuous ellipsoidal subtraction.
           *
           * sqrt(opening) gives us a useful ergonomic
           * response:
           *
           * 58% approximately corresponds to our
           * previously validated medium oval.
           */

          if (uOpening > 0.0001) {

            float s =
              sqrt(
                clamp(
                  uOpening,
                  0.0,
                  1.0
                )
              );


            float radiusX =
              max(
                uApertureMaxRadii.x * s,
                0.00015
              );


            float radiusZ =
              max(
                uApertureMaxRadii.z * s,
                0.00015
              );


            float radiusY =
              mix(
                uMinSuperiorRadius,
                uApertureMaxRadii.y,
                s
              );


            vec3 local =
              vApertureWorldPosition -
              uApertureCenter;


            vec3 normalizedPosition =
              vec3(

                local.x / radiusX,

                local.y / radiusY,

                local.z / radiusZ

              );


            float ellipsoid =
              dot(
                normalizedPosition,
                normalizedPosition
              );


            if (ellipsoid < 1.0) {
              discard;
            }

          }
          `

        );

    };


  material.customProgramCacheKey =
    () => "v2b3a-dynamic-aperture-2";


  return material;
}


/* ============================================================
   MODEL
   ============================================================ */


let skull = null;


function configureApertureFromBounds(
  box
) {

  const size =
    new THREE.Vector3();


  const center =
    new THREE.Vector3();


  box.getSize(size);
  box.getCenter(center);


  apertureUniforms.center.value.set(

    center.x +
      size.x *
      APERTURE.centerXFraction,

    box.max.y +
      size.y *
      APERTURE.centerAboveFraction,

    center.z +
      size.z *
      APERTURE.centerZFraction,

  );


  apertureUniforms.maxRadii.value.set(

    size.x *
      APERTURE.maxRadiusXFraction,

    size.y *
      APERTURE.maxRadiusYFraction,

    size.z *
      APERTURE.maxRadiusZFraction,

  );


  apertureUniforms.minSuperiorRadius.value =

    size.y *
    APERTURE.minRadiusYFraction;


  console.log(
    "===== V2B3A APERTURE ====="
  );

  console.log(
    "Bounds size:",
    size
  );

  console.log(
    "Cutter center:",
    apertureUniforms.center.value
  );

  console.log(
    "Max radii:",
    apertureUniforms.maxRadii.value
  );

}


function frameModel(
  object,
  box
) {

  const sphere =
    new THREE.Sphere();


  box.getBoundingSphere(
    sphere
  );


  controls.target.copy(
    sphere.center
  );


  const radius =
    sphere.radius;


  camera.position.set(

    sphere.center.x +
      radius * 1.30,

    sphere.center.y +
      radius * 0.42,

    sphere.center.z +
      radius * 2.55

  );


  camera.near =
    Math.max(
      radius / 100,
      0.001
    );


  camera.far =
    radius * 30;


  camera.updateProjectionMatrix();


  controls.minDistance =
    radius * 1.15;


  controls.maxDistance =
    radius * 8;


  controls.update();

}


function setStatus(
  state,
  message
) {

  status.dataset.state =
    state;

  statusText.textContent =
    message;

}


const loader =
  new GLTFLoader();


setStatus(
  "loading",
  "Loading skull…"
);


loader.load(

  "./assets/skull_full.glb?v=v2b3a-1",

  (gltf) => {

    skull =
      gltf.scene;


    const apertureMaterial =
      createApertureMaterial();


    skull.traverse(
      (object) => {

        if (!object.isMesh) {
          return;
        }


        object.material =
          apertureMaterial;


        object.castShadow = false;
        object.receiveShadow = false;

      }
    );


    scene.add(
      skull
    );


    skull.updateMatrixWorld(
      true
    );


    const box =
      new THREE.Box3().setFromObject(
        skull
      );


    configureApertureFromBounds(
      box
    );


    frameModel(
      skull,
      box
    );


    setStatus(
      "ready",
      "Dynamic aperture ready"
    );

  },


  (progress) => {

    if (!progress.total) {
      return;
    }


    const percent =
      Math.round(
        progress.loaded /
        progress.total *
        100
      );


    setStatus(
      "loading",
      `Loading skull… ${percent}%`
    );

  },


  (error) => {

    console.error(
      error
    );


    setStatus(
      "error",
      "Skull failed to load"
    );

  }

);


/* ============================================================
   APERTURE UI
   ============================================================ */


function descriptionForOpening(
  value
) {

  if (value === 0) {
    return "Closed skull";
  }

  if (value < 20) {
    return "Minimal access";
  }

  if (value < 45) {
    return "Small opening";
  }

  if (value < 68) {
    return "Standard opening";
  }

  if (value < 88) {
    return "Large opening";
  }

  return "Wide exploratory opening";

}


function updatePresetButtons(
  value
) {

  for (
    const button
    of presetButtons
  ) {

    const preset =
      Number(
        button.dataset.opening
      );


    button.classList.toggle(
      "is-active",
      preset === value
    );

  }

}


function setOpening(
  value
) {

  const normalized =
    THREE.MathUtils.clamp(
      Number(value),
      0,
      100
    );


  slider.value =
    String(normalized);


  openingValue.textContent =
    `${Math.round(normalized)}%`;


  openingDescription.textContent =
    descriptionForOpening(
      Math.round(normalized)
    );


  targetOpening =
    normalized / 100;


  updatePresetButtons(
    Math.round(normalized)
  );

}


slider.addEventListener(
  "input",
  () => {

    setOpening(
      slider.value
    );

  }
);


for (
  const button
  of presetButtons
) {

  button.addEventListener(
    "click",
    () => {

      setOpening(
        Number(
          button.dataset.opening
        )
      );

    }
  );

}


setOpening(58);


/* ============================================================
   RESIZE
   ============================================================ */


function resize() {

  const width =
    Math.max(
      viewport.clientWidth,
      1
    );


  const height =
    Math.max(
      viewport.clientHeight,
      1
    );


  renderer.setSize(
    width,
    height,
    false
  );


  camera.aspect =
    width / height;


  camera.updateProjectionMatrix();

}


const resizeObserver =
  new ResizeObserver(
    resize
  );


resizeObserver.observe(
  viewport
);


resize();


/* ============================================================
   RENDER LOOP
   ============================================================ */


const clock =
  new THREE.Clock();


function animate() {

  requestAnimationFrame(
    animate
  );


  const dt =
    Math.min(
      clock.getDelta(),
      0.05
    );


  /*
   * Slight damping makes the opening feel physical
   * rather than snapping directly to slider values.
   */

  const response =
    1 -
    Math.exp(
      -18 * dt
    );


  currentOpening =
    THREE.MathUtils.lerp(
      currentOpening,
      targetOpening,
      response
    );


  if (
    Math.abs(
      currentOpening -
      targetOpening
    ) < 0.0001
  ) {

    currentOpening =
      targetOpening;

  }


  apertureUniforms.opening.value =
    currentOpening;


  controls.update();


  renderer.render(
    scene,
    camera
  );

}


animate();
