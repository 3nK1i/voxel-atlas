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
      viewRelative: true,
      hemisphere: Object.freeze({ sky: "#eef8ff", ground: "#64748a", intensity: 1.40 }),
      key: Object.freeze({ color: "#fff4e6", intensity: 1.26, position: Object.freeze([1.9, 2.4, 3.1]) }),
      fill: Object.freeze({ color: "#dcecff", intensity: 0.88, position: Object.freeze([-2.5, 1.0, 2.2]) }),
      rim: Object.freeze({ color: "#f3f8ff", intensity: 0.74, position: Object.freeze([0.8, 2.0, -2.8]) }),
    }),
    volumeSurface: Object.freeze({
      color: "#f0e8da",
      roughness: 0.56,
      metalness: 0.0,
      emissive: "#4a4134",
      emissiveIntensity: 0.16,
    }),
    segmentationSurface: Object.freeze({
      roughness: 0.54,
      selectedRoughness: 0.46,
      metalness: 0.0,
      emissiveIntensity: 0.08,
      selectedEmissiveIntensity: 0.12,
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

function setDirectionalTarget(light, focus) {
  if (!light?.target?.position?.set) return;
  light.target.position.set(focus.x, focus.y, focus.z);
  light.target.updateMatrixWorld?.(true);
}

function placeViewRelativeLight(three, light, camera, focus, offset) {
  const position = new three.Vector3(...offset);
  position.applyQuaternion(camera.quaternion);
  position.x += focus.x;
  position.y += focus.y;
  position.z += focus.z;
  light.position.set(position.x, position.y, position.z);
  setDirectionalTarget(light, focus);
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
      if (!lighting.viewRelative) {
        const origin = { x: 0, y: 0, z: 0 };
        setDirectionalTarget(key, origin);
        setDirectionalTarget(fill, origin);
        setDirectionalTarget(rim, origin);
      }
      rig.profile = profile.id;
      requestRender();
      return profile;
    },
    syncToView(camera, focus) {
      const profile = getSurfacePresentationProfile(rig.profile);
      const lighting = profile.lighting;
      if (!lighting.viewRelative) return false;
      if (!three?.Vector3 || !camera?.quaternion) return false;
      const target = {
        x: Number(focus?.x ?? 0),
        y: Number(focus?.y ?? 0),
        z: Number(focus?.z ?? 0),
      };
      placeViewRelativeLight(three, key, camera, target, lighting.key.position);
      placeViewRelativeLight(three, fill, camera, target, lighting.fill.position);
      placeViewRelativeLight(three, rim, camera, target, lighting.rim.position);
      return true;
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
  material.emissive?.set?.(policy.emissive || "#000000");
  material.emissiveIntensity = Number(policy.emissiveIntensity ?? 0);
  material.needsUpdate = true;
  return profile;
}

export function createVolumeSurfaceMaterial(three, profileId = "fidelity") {
  if (!three?.MeshStandardMaterial) throw new TypeError("Three.js MeshStandardMaterial is required");
  const profile = getSurfacePresentationProfile(profileId);
  const policy = profile.volumeSurface;
  return new three.MeshStandardMaterial({
    color: policy.color,
    emissive: policy.emissive || "#000000",
    emissiveIntensity: Number(policy.emissiveIntensity ?? 0),
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



export function resolveDirectCtSurfaceCompositionPolicy(rawOpacity, semanticOverlayActive = false) {
  const opacity = Number(rawOpacity ?? 1);
  if (!Number.isFinite(opacity) || opacity < 0 || opacity > 1) {
    throw new RangeError("Direct CT surface opacity must be within [0, 1]");
  }
  const semanticOverlay = Boolean(semanticOverlayActive);
  const translucent = opacity < 0.999;
  return Object.freeze({
    opacity,
    // In Surface mode, a co-present semantic segmentation layer must remain
    // visible over the resident Direct CT mesh. Keep alpha exact, but move
    // Direct CT out of the depth-writing opaque lane while semantic overlay
    // coexistence is active. No geometry is offset or rebuilt.
    transparent: translucent || semanticOverlay,
    depthWrite: !(translucent || semanticOverlay),
  });
}

export function resolveSegmentationSurfaceOpacityPolicy(rawOpacity) {
  const opacity = Number(rawOpacity ?? 1);
  if (!Number.isFinite(opacity) || opacity < 0 || opacity > 1) {
    throw new RangeError("Segmentation surface opacity must be within [0, 1]");
  }
  const fullyOpaque = opacity >= 1;
  return Object.freeze({
    opacity,
    // Segmentation surfaces stay in the transparent render lane even at
    // alpha=1 so semantic overlays render after Direct CT presentation
    // surfaces. Alpha remains exact; only queue placement is stabilized.
    transparent: true,
    depthWrite: fullyOpaque,
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
  const opacityPolicy = resolveSegmentationSurfaceOpacityPolicy(structure?.opacity ?? 1);
  const semanticColor = structure?.colorHex || "#ffffff";
  const emissiveIntensity = selected
    ? Number(policy.selectedEmissiveIntensity ?? policy.emissiveIntensity ?? 0)
    : Number(policy.emissiveIntensity ?? 0);
  material.color.set(structure?.colorHex || "#ffffff");
  material.emissive?.set?.(semanticColor);
  material.emissiveIntensity = emissiveIntensity;
  material.opacity = opacityPolicy.opacity;
  material.transparent = opacityPolicy.transparent;
  material.depthWrite = opacityPolicy.depthWrite;
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
  const opacityPolicy = resolveSegmentationSurfaceOpacityPolicy(structure?.opacity ?? 1);
  const semanticColor = structure?.colorHex || "#ffffff";
  const profile = getSurfacePresentationProfile(profileId);
  const policy = profile.segmentationSurface;
  const emissiveIntensity = selected
    ? Number(policy.selectedEmissiveIntensity ?? policy.emissiveIntensity ?? 0)
    : Number(policy.emissiveIntensity ?? 0);
  return new three.MeshStandardMaterial({
    color: semanticColor,
    emissive: emissiveIntensity > 0 ? semanticColor : "#000000",
    emissiveIntensity,
    opacity: opacityPolicy.opacity,
    transparent: opacityPolicy.transparent,
    side: three.FrontSide ?? three.DoubleSide,
    depthTest: true,
    depthWrite: opacityPolicy.depthWrite,
    roughness: selected ? policy.selectedRoughness : policy.roughness,
    metalness: policy.metalness,
    flatShading: false,
  });
}
