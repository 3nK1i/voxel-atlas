const SURFACE_PRESENTATION_PROFILES = Object.freeze({
  fidelity: Object.freeze({
    id: "fidelity",
    lighting: Object.freeze({
      hemisphere: Object.freeze({ sky: "#d8efff", ground: "#182332", intensity: 1.18 }),
      key: Object.freeze({ color: "#fff6ea", intensity: 1.35, position: Object.freeze([2.8, 3.6, 4.8]) }),
      fill: Object.freeze({ color: "#c9ddff", intensity: 0.48, position: Object.freeze([-3.4, 1.4, 2.6]) }),
      rim: Object.freeze({ color: "#e4efff", intensity: 0.62, position: Object.freeze([-1.2, 3.0, -4.2]) }),
    }),
    volumeSurface: Object.freeze({
      color: "#e8e1d2",
      roughness: 0.62,
      metalness: 0.0,
    }),
    segmentationSurface: Object.freeze({
      roughness: 0.60,
      selectedRoughness: 0.52,
      metalness: 0.0,
    }),
  }),
  presentation: Object.freeze({
    id: "presentation",
    lighting: Object.freeze({
      hemisphere: Object.freeze({ sky: "#e7f5ff", ground: "#2a3a50", intensity: 1.32 }),
      key: Object.freeze({ color: "#fff4e6", intensity: 1.45, position: Object.freeze([2.5, 3.8, 4.5]) }),
      fill: Object.freeze({ color: "#d8e9ff", intensity: 0.68, position: Object.freeze([-3.2, 1.8, 2.8]) }),
      rim: Object.freeze({ color: "#edf7ff", intensity: 0.78, position: Object.freeze([-1.4, 3.2, -4.0]) }),
    }),
    volumeSurface: Object.freeze({
      color: "#eee7d9",
      roughness: 0.50,
      metalness: 0.0,
    }),
    segmentationSurface: Object.freeze({
      roughness: 0.52,
      selectedRoughness: 0.44,
      metalness: 0.0,
    }),
  }),
});

export function getSurfacePresentationProfile(profileId) {
  const normalized = String(profileId || "");
  const profile = SURFACE_PRESENTATION_PROFILES[normalized];
  if (!profile) throw new RangeError(`Unknown surface presentation profile: ${normalized || "<empty>"}`);
  return profile;
}

function setLight(light, definition) {
  light.color.set(definition.color);
  light.intensity = definition.intensity;
  light.position.set(...definition.position);
}

export function createSurfaceLightingRig({ three, scene, requestRender = () => {} }) {
  if (!three?.HemisphereLight || !three?.DirectionalLight || !scene?.add) {
    throw new TypeError("Three.js surface lighting dependencies are required");
  }
  const initial = getSurfacePresentationProfile("fidelity").lighting;
  const hemisphere = new three.HemisphereLight(
    initial.hemisphere.sky,
    initial.hemisphere.ground,
    initial.hemisphere.intensity,
  );
  hemisphere.name = "VoxelAtlas surface hemisphere";
  const key = new three.DirectionalLight(initial.key.color, initial.key.intensity);
  key.name = "VoxelAtlas surface key";
  const fill = new three.DirectionalLight(initial.fill.color, initial.fill.intensity);
  fill.name = "VoxelAtlas surface fill";
  const rim = new three.DirectionalLight(initial.rim.color, initial.rim.intensity);
  rim.name = "VoxelAtlas surface rim";
  scene.add(hemisphere, key, fill, rim);

  const rig = {
    profile: "fidelity",
    hemisphere,
    key,
    fill,
    rim,
    setProfile(profileId) {
      const profile = getSurfacePresentationProfile(profileId);
      const lighting = profile.lighting;
      hemisphere.color.set(lighting.hemisphere.sky);
      hemisphere.groundColor.set(lighting.hemisphere.ground);
      hemisphere.intensity = lighting.hemisphere.intensity;
      setLight(key, lighting.key);
      setLight(fill, lighting.fill);
      setLight(rim, lighting.rim);
      rig.profile = profile.id;
      requestRender();
      return profile;
    },
  };
  rig.setProfile("fidelity");
  return rig;
}

export function applyVolumeSurfaceMaterialProfile(material, profileId) {
  if (!material?.color?.set) throw new TypeError("Volume surface material is required");
  const profile = getSurfacePresentationProfile(profileId);
  const policy = profile.volumeSurface;
  material.color.set(policy.color);
  material.roughness = policy.roughness;
  material.metalness = policy.metalness;
  material.needsUpdate = true;
  return profile;
}

export function createVolumeSurfaceMaterial(three, profileId = "fidelity") {
  if (!three?.MeshStandardMaterial) throw new TypeError("Three.js MeshStandardMaterial is required");
  const profile = getSurfacePresentationProfile(profileId);
  const policy = profile.volumeSurface;
  return new three.MeshStandardMaterial({
    color: policy.color,
    opacity: 1,
    transparent: false,
    side: three.DoubleSide,
    depthTest: true,
    depthWrite: true,
    roughness: policy.roughness,
    metalness: policy.metalness,
    flatShading: false,
  });
}

export function applySegmentationSurfaceMaterialProfile(
  material,
  structure,
  profileId,
  selected = false,
) {
  if (!material?.color?.set) throw new TypeError("Segmentation surface material is required");
  const profile = getSurfacePresentationProfile(profileId);
  const policy = profile.segmentationSurface;
  const opacity = Number(structure?.opacity ?? 1);
  material.color.set(structure?.colorHex || "#ffffff");
  material.opacity = opacity;
  material.transparent = opacity < 1;
  material.depthWrite = opacity >= 0.98;
  material.roughness = selected ? policy.selectedRoughness : policy.roughness;
  material.metalness = policy.metalness;
  material.needsUpdate = true;
  return profile;
}

export function createSegmentationSurfaceMaterial(
  three,
  structure,
  profileId = "fidelity",
  selected = false,
) {
  if (!three?.MeshStandardMaterial) throw new TypeError("Three.js MeshStandardMaterial is required");
  const opacity = Number(structure?.opacity ?? 1);
  const profile = getSurfacePresentationProfile(profileId);
  const policy = profile.segmentationSurface;
  return new three.MeshStandardMaterial({
    color: structure?.colorHex || "#ffffff",
    opacity,
    transparent: opacity < 1,
    side: three.FrontSide ?? three.DoubleSide,
    depthTest: true,
    depthWrite: opacity >= 0.98,
    roughness: selected ? policy.selectedRoughness : policy.roughness,
    metalness: policy.metalness,
    flatShading: false,
  });
}
