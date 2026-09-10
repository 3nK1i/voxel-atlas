const PROFILE_DEFINITIONS = Object.freeze([
  Object.freeze({
    id: "fidelity",
    label: "Fidelity",
    intent: "restrained",
    description: "Restrained rendering intent for clear geometry-first inspection.",
  }),
  Object.freeze({
    id: "presentation",
    label: "Presentation",
    intent: "polished",
    description: "Polished rendering intent for stronger anatomical readability.",
  }),
]);

const PROFILE_IDS = new Set(PROFILE_DEFINITIONS.map((entry) => entry.id));

function requireProfile(profileId) {
  const normalized = String(profileId || "");
  if (!PROFILE_IDS.has(normalized)) {
    throw new RangeError(`Unknown reconstruction presentation profile: ${normalized || "<empty>"}`);
  }
  return normalized;
}

export function listReconstructionPresentationProfiles() {
  return PROFILE_DEFINITIONS;
}

export class ReconstructionPresentationProfileController {
  constructor({ onChange = () => {} } = {}) {
    if (typeof onChange !== "function") {
      throw new TypeError("Presentation-profile onChange callback must be a function");
    }
    this.onChange = onChange;
    this.profile = "fidelity";
  }

  _definition() {
    return PROFILE_DEFINITIONS.find((entry) => entry.id === this.profile);
  }

  _emit(reason) {
    const snapshot = this.snapshot();
    this.onChange(snapshot, reason);
    return snapshot;
  }

  requestProfile(profileId) {
    const requested = requireProfile(profileId);
    if (requested === this.profile) {
      return Object.freeze({ accepted: true, reason: "unchanged", snapshot: this.snapshot() });
    }
    this.profile = requested;
    return Object.freeze({ accepted: true, reason: "accepted", snapshot: this._emit("profile-request") });
  }

  reset() {
    this.profile = "fidelity";
    return this._emit("reset");
  }

  snapshot() {
    const definition = this._definition();
    return Object.freeze({
      profile: this.profile,
      label: definition.label,
      intent: definition.intent,
      description: definition.description,
    });
  }
}
