const MODE_DEFINITIONS = Object.freeze([
  Object.freeze({ id: "volume", label: "Volume", requiresVolume: true, requiresSurface: false }),
  Object.freeze({ id: "surface", label: "Surface", requiresVolume: false, requiresSurface: true }),
  Object.freeze({ id: "combined", label: "Combined", requiresVolume: true, requiresSurface: true }),
]);

const SURFACE_SOURCE_DEFINITIONS = Object.freeze([
  Object.freeze({ id: "volume-derived", label: "Volume-derived", sourceType: "canonical_volume" }),
  Object.freeze({ id: "segmentation-derived", label: "Segmentation-derived", sourceType: "segmentation_label_map" }),
]);

const MODE_IDS = new Set(MODE_DEFINITIONS.map((entry) => entry.id));
const SURFACE_SOURCE_IDS = new Set(SURFACE_SOURCE_DEFINITIONS.map((entry) => entry.id));

function requireMode(modeId) {
  const normalized = String(modeId || "");
  if (!MODE_IDS.has(normalized)) {
    throw new RangeError(`Unknown reconstruction visualization mode: ${normalized || "<empty>"}`);
  }
  return normalized;
}

function requireSurfaceSource(sourceId) {
  const normalized = String(sourceId || "");
  if (!SURFACE_SOURCE_IDS.has(normalized)) {
    throw new RangeError(`Unknown reconstruction surface source: ${normalized || "<empty>"}`);
  }
  return normalized;
}

export function listReconstructionVisualizationModes() {
  return MODE_DEFINITIONS;
}

export function listReconstructionSurfaceSources() {
  return SURFACE_SOURCE_DEFINITIONS;
}

export class ReconstructionVisualizationModeController {
  constructor({ onChange = () => {} } = {}) {
    if (typeof onChange !== "function") {
      throw new TypeError("Visualization-mode onChange callback must be a function");
    }
    this.onChange = onChange;
    this.mode = "volume";
    this.volumeAvailable = false;
    this.surfaceSources = new Map(
      SURFACE_SOURCE_DEFINITIONS.map(({ id }) => [
        id,
        { available: false, resident: false, selected: false },
      ]),
    );
  }

  _selectedResidentSources() {
    return SURFACE_SOURCE_DEFINITIONS
      .map(({ id }) => id)
      .filter((id) => {
        const state = this.surfaceSources.get(id);
        return state.selected && state.resident;
      });
  }

  _capabilities() {
    const surfaceReady = this._selectedResidentSources().length > 0;
    return Object.freeze({
      canVolume: this.volumeAvailable,
      canSurface: surfaceReady,
      canCombined: this.volumeAvailable && surfaceReady,
    });
  }

  _reconcileMode() {
    const { canVolume, canSurface, canCombined } = this._capabilities();
    if (this.mode === "combined" && !canCombined) {
      this.mode = canVolume ? "volume" : (canSurface ? "surface" : "volume");
    } else if (this.mode === "surface" && !canSurface) {
      this.mode = canVolume ? "volume" : "volume";
    } else if (this.mode === "volume" && !canVolume && canSurface) {
      this.mode = "surface";
    }
  }

  _emit(reason) {
    const snapshot = this.snapshot();
    this.onChange(snapshot, reason);
    return snapshot;
  }

  setVolumeAvailable(available) {
    this.volumeAvailable = Boolean(available);
    this._reconcileMode();
    return this._emit("volume-availability");
  }

  setSurfaceSource(sourceId, update = {}) {
    const id = requireSurfaceSource(sourceId);
    const current = this.surfaceSources.get(id);
    const next = {
      available: Object.hasOwn(update, "available") ? Boolean(update.available) : current.available,
      resident: Object.hasOwn(update, "resident") ? Boolean(update.resident) : current.resident,
      selected: Object.hasOwn(update, "selected") ? Boolean(update.selected) : current.selected,
    };
    if (!next.available) next.resident = false;
    this.surfaceSources.set(id, next);
    this._reconcileMode();
    return this._emit(`surface-source:${id}`);
  }

  selectSurfaceSource(sourceId, selected = true) {
    return this.setSurfaceSource(sourceId, { selected });
  }

  requestMode(modeId) {
    const requested = requireMode(modeId);
    const { canVolume, canSurface, canCombined } = this._capabilities();
    if (requested === "volume" && !canVolume) {
      return Object.freeze({ accepted: false, reason: "volume-unavailable", snapshot: this.snapshot() });
    }
    if (requested === "surface" && !canSurface) {
      return Object.freeze({ accepted: false, reason: "surface-unavailable", snapshot: this.snapshot() });
    }
    if (requested === "combined" && !canCombined) {
      return Object.freeze({
        accepted: false,
        reason: canVolume ? "surface-unavailable" : "volume-unavailable",
        snapshot: this.snapshot(),
      });
    }
    this.mode = requested;
    return Object.freeze({ accepted: true, reason: "accepted", snapshot: this._emit("mode-request") });
  }

  reset() {
    this.mode = "volume";
    this.volumeAvailable = false;
    for (const { id } of SURFACE_SOURCE_DEFINITIONS) {
      this.surfaceSources.set(id, { available: false, resident: false, selected: false });
    }
    return this._emit("reset");
  }

  snapshot() {
    const selectedSurfaceSources = SURFACE_SOURCE_DEFINITIONS
      .map(({ id }) => id)
      .filter((id) => this.surfaceSources.get(id).selected);
    const residentSurfaceSources = SURFACE_SOURCE_DEFINITIONS
      .map(({ id }) => id)
      .filter((id) => this.surfaceSources.get(id).resident);
    const selectedResidentSurfaceSources = this._selectedResidentSources();
    const capabilities = this._capabilities();
    const surfacesVisible = this.mode === "surface" || this.mode === "combined";
    const visibility = {
      volume: this.volumeAvailable && (this.mode === "volume" || this.mode === "combined"),
      surfaceSources: Object.fromEntries(
        SURFACE_SOURCE_DEFINITIONS.map(({ id }) => [
          id,
          surfacesVisible && selectedResidentSurfaceSources.includes(id),
        ]),
      ),
    };
    const sourceState = Object.fromEntries(
      SURFACE_SOURCE_DEFINITIONS.map(({ id }) => [id, Object.freeze({ ...this.surfaceSources.get(id) })]),
    );
    return Object.freeze({
      mode: this.mode,
      volumeAvailable: this.volumeAvailable,
      selectedSurfaceSources: Object.freeze(selectedSurfaceSources),
      residentSurfaceSources: Object.freeze(residentSurfaceSources),
      selectedResidentSurfaceSources: Object.freeze(selectedResidentSurfaceSources),
      surfaceSources: Object.freeze(sourceState),
      ...capabilities,
      visibility: Object.freeze({
        volume: visibility.volume,
        surfaceSources: Object.freeze(visibility.surfaceSources),
      }),
    });
  }
}
