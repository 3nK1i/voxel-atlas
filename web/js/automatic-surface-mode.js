// Coordinates only the requested presentation mode. Resource ownership
// and source/study validation stay in the existing surface layers and app.
const VALID_MODES = new Set(["volume", "surface", "combined"]);

export class AutomaticSurfaceModeCoordinator {
  constructor({ requestMode, canActivate, ensureSurface, onPending = () => {}, onFailure = () => {} }) {
    if (![requestMode, canActivate, ensureSurface, onPending, onFailure].every((item) => typeof item === "function")) {
      throw new TypeError("Automatic surface mode callbacks must be functions");
    }
    this.requestMode = requestMode;
    this.canActivate = canActivate;
    this.ensureSurface = ensureSurface;
    this.onPending = onPending;
    this.onFailure = onFailure;
    this.generation = 0;
  }

  invalidate() {
    this.generation += 1;
    this.onPending(null);
  }

  request(modeId) {
    if (!VALID_MODES.has(modeId)) throw new RangeError("Unknown visualization mode");
    const generation = ++this.generation;
    if (modeId === "volume" || this.canActivate(modeId)) {
      this.onPending(null);
      return this.requestMode(modeId);
    }
    this.onPending(modeId);
    let work;
    try {
      work = this.ensureSurface(modeId);
    } catch (error) {
      if (generation === this.generation) {
        this.onPending(null);
        this.onFailure(error);
      }
      return Promise.resolve({ accepted: false, reason: "surface-preparation-failed" });
    }
    if (!work) {
      if (generation === this.generation) this.onPending(null);
      return Promise.resolve({ accepted: false, reason: "surface-unavailable" });
    }
    return Promise.resolve(work).then((ready) => {
      if (generation !== this.generation) return { accepted: false, reason: "superseded" };
      if (ready && this.canActivate(modeId)) return this.requestMode(modeId);
      return { accepted: false, reason: "surface-unavailable" };
    }).catch((error) => {
      if (generation === this.generation) this.onFailure(error);
      return { accepted: false, reason: "surface-preparation-failed" };
    }).finally(() => {
      if (generation === this.generation) this.onPending(null);
    });
  }
}
