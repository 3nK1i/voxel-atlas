const COMBINED_PRESENTATION_POLICIES = Object.freeze({
  fidelity: Object.freeze({
    volumeOpacityMultiplier: 0.78,
    directCtSurfaceOpacity: 0.84,
    segmentationOpacityMultiplier: 1,
  }),
  presentation: Object.freeze({
    volumeOpacityMultiplier: 0.62,
    directCtSurfaceOpacity: 0.72,
    segmentationOpacityMultiplier: 1,
  }),
});

function clamp01(value, label) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new TypeError(`${label} must be finite`);
  return Math.min(1, Math.max(0, number));
}

export function getCombinedPresentationPolicy(profileId) {
  const normalized = String(profileId || "");
  const policy = COMBINED_PRESENTATION_POLICIES[normalized];
  if (!policy) throw new RangeError(`Unknown combined presentation profile: ${normalized || "<empty>"}`);
  return policy;
}

export function resolveCombinedPresentationBalance({
  mode,
  profile,
  userVolumeOpacity,
  directCtSurfaceVisible = false,
  segmentationSurfaceVisible = false,
} = {}) {
  const normalizedMode = String(mode || "volume");
  const normalizedProfile = String(profile || "fidelity");
  const baseOpacity = clamp01(userVolumeOpacity, "User volume opacity");
  const policy = getCombinedPresentationPolicy(normalizedProfile);
  const active = normalizedMode === "combined"
    && Boolean(directCtSurfaceVisible || segmentationSurfaceVisible);

  if (!active) {
    return Object.freeze({
      active: false,
      profile: normalizedProfile,
      effectiveVolumeOpacity: baseOpacity,
      directCtSurfaceOpacity: 1,
      directCtSurfaceDepthWrite: true,
      segmentationOpacityMultiplier: 1,
    });
  }

  return Object.freeze({
    active: true,
    profile: normalizedProfile,
    effectiveVolumeOpacity: clamp01(
      baseOpacity * policy.volumeOpacityMultiplier,
      "Effective volume opacity",
    ),
    directCtSurfaceOpacity: directCtSurfaceVisible ? policy.directCtSurfaceOpacity : 1,
    directCtSurfaceDepthWrite: !directCtSurfaceVisible,
    segmentationOpacityMultiplier: 1,
  });
}
