// Uses existing source-bound segmentation surfaces; does not start jobs or mutate the layer.
export class ExistingSegmentationSurfaceGate {
  constructor({ readIdentity, hasResident, hasDesiredStructures, startSurface }) {
    if (![readIdentity, hasResident, hasDesiredStructures, startSurface]
      .every((value) => typeof value === "function")) {
      throw new TypeError("Existing segmentation surface callbacks are required");
    }
    this.readIdentity = readIdentity;
    this.hasResident = hasResident;
    this.hasDesiredStructures = hasDesiredStructures;
    this.startSurface = startSurface;
    this.pending = null;
  }

  _finish(ready) {
    const pending = this.pending;
    this.pending = null;
    if (pending) pending.resolve(Boolean(ready));
  }

  invalidate() {
    this._finish(false);
  }

  request() {
    const identity = this.readIdentity();
    if (!identity || !this.hasDesiredStructures()) return Promise.resolve(false);
    if (this.hasResident()) return Promise.resolve(true);
    if (this.pending?.identity === identity) return this.pending.promise;
    this.invalidate();
    let resolve;
    const promise = new Promise((done) => { resolve = done; });
    const pending = { identity, promise, resolve };
    this.pending = pending;
    try {
      Promise.resolve(this.startSurface()).catch(() => {
        if (this.pending === pending) this._finish(false);
      });
    } catch {
      if (this.pending === pending) this._finish(false);
    }
    return promise;
  }

  notify(status) {
    if (!this.pending) return;
    if (this.readIdentity() !== this.pending.identity || !this.hasDesiredStructures()) {
      this._finish(false);
    } else if (this.hasResident()) {
      this._finish(true);
    } else if (
      ["unavailable", "disabled", "error"].includes(status?.state)
      || status?.requestedCount === 0
    ) {
      this._finish(false);
    }
  }
}
