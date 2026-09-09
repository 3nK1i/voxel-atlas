const ACTION_LABELS = Object.freeze({
  review: "Review mark",
  include: "Include in structure",
  exclude: "Exclude from structure",
});

export function validateCorrectionDraftAction(action) {
  const center = Array.isArray(action?.center_lps_mm)
    ? action.center_lps_mm.map(Number)
    : [];
  const normalized = {
    kind: String(action?.kind || ""),
    label_id: Number(action?.label_id),
    center_lps_mm: center,
    radius_mm: Number(action?.radius_mm),
    plane: String(action?.plane || ""),
  };
  if (
    !Object.hasOwn(ACTION_LABELS, normalized.kind)
    || !Number.isInteger(normalized.label_id)
    || normalized.label_id <= 0
    || center.length !== 3
    || !center.every(Number.isFinite)
    || !Number.isFinite(normalized.radius_mm)
    || normalized.radius_mm < 0.5
    || normalized.radius_mm > 25
    || !["axial", "coronal", "sagittal"].includes(normalized.plane)
  ) {
    throw new Error("Correction draft action is invalid");
  }
  return normalized;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Accept": "application/json", "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Correction request failed (${response.status})`);
  return payload;
}

export class SegmentationCorrectionPanel {
  constructor(root, { getCrosshair, getPlane } = {}) {
    if (!(root instanceof HTMLElement)) throw new Error("Correction panel root is required");
    this.root = root;
    this.getCrosshair = getCrosshair;
    this.getPlane = getPlane;
    this.status = root.querySelector("#segmentationCorrectionStatus");
    this.start = root.querySelector("#segmentationCorrectionStart");
    this.kind = root.querySelector("#segmentationCorrectionKind");
    this.radius = root.querySelector("#segmentationCorrectionRadius");
    this.radiusValue = root.querySelector("#segmentationCorrectionRadiusValue");
    this.apply = root.querySelector("#segmentationCorrectionApply");
    this.undo = root.querySelector("#segmentationCorrectionUndo");
    this.redo = root.querySelector("#segmentationCorrectionRedo");
    this.discard = root.querySelector("#segmentationCorrectionDiscard");
    this.warnings = root.querySelector("#segmentationQualityWarnings");
    this.context = null;
    this.session = null;
    this.busy = false;
    this.qualityGeneration = 0;
    this.sessionGeneration = 0;
    this.start.addEventListener("click", () => void this.startSession());
    this.apply.addEventListener("click", () => void this.applyAtCrosshair());
    this.undo.addEventListener("click", () => void this.moveHistory("undo"));
    this.redo.addEventListener("click", () => void this.moveHistory("redo"));
    this.discard.addEventListener("click", () => void this.discardSession());
    this.radius.addEventListener("input", () => {
      this.radiusValue.textContent = `${Number(this.radius.value).toFixed(1)} mm`;
    });
    this.clear();
  }

  clear() {
    this.qualityGeneration += 1;
    this.sessionGeneration += 1;
    this.context = null;
    this.session = null;
    this.root.dataset.state = "unavailable";
    this.status.textContent = "Select a segmented structure to begin review.";
    this.warnings.replaceChildren();
    this.render();
  }

  setContext({ labelMapId, studyId, labelId, displayName }) {
    const next = { labelMapId, studyId, labelId: Number(labelId), displayName };
    const selectionChanged = !this.context
      || this.context.labelMapId !== next.labelMapId
      || this.context.studyId !== next.studyId
      || this.context.labelId !== next.labelId;
    const sourceChanged = !this.context
      || this.context.labelMapId !== next.labelMapId
      || this.context.studyId !== next.studyId;
    if (sourceChanged) this.session = null;
    this.context = next;
    this.root.dataset.state = "ready";
    this.status.textContent = this.session
      ? `${this.session.applied_action_count} draft actions applied`
      : `${displayName} · correction draft not started`;
    this.render();
    if (selectionChanged) void this.loadQuality();
    if (sourceChanged) void this.resumeLatestDraft();
  }

  async resumeLatestDraft() {
    if (!this.context) return;
    const generation = ++this.sessionGeneration;
    const params = new URLSearchParams({ label_map_id: this.context.labelMapId });
    try {
      const payload = await requestJson(
        `/api/segmentation/correction-sessions?${params}`,
        { method: "GET", headers: { "Accept": "application/json" } },
      );
      if (generation !== this.sessionGeneration || this.session) return;
      this.session = (payload.correction_sessions || []).find(
        (candidate) => candidate.state === "draft",
      ) || null;
      if (this.session) {
        this.status.textContent = `${this.session.applied_action_count} draft actions resumed`;
      }
      this.render();
    } catch (error) {
      if (generation !== this.sessionGeneration) return;
      this.root.dataset.state = "error";
      this.status.textContent = error instanceof Error ? error.message : "Correction draft unavailable";
      this.render();
    }
  }

  async loadQuality() {
    if (!this.context) return;
    const generation = ++this.qualityGeneration;
    const params = new URLSearchParams({ label_map_id: this.context.labelMapId });
    try {
      const payload = await requestJson(
        `/api/studies/latest/segmentation-quality/${this.context.labelId}?${params}`,
        { method: "GET", headers: { "Accept": "application/json" } },
      );
      if (generation !== this.qualityGeneration) return;
      this.renderWarnings(payload.quality?.warnings || []);
    } catch (error) {
      if (generation !== this.qualityGeneration) return;
      this.renderWarnings([{ severity: "warning", message: error.message }]);
    }
  }

  renderWarnings(warnings) {
    this.warnings.replaceChildren();
    for (const warning of warnings) {
      const item = document.createElement("li");
      item.dataset.severity = warning.severity === "warning" ? "warning" : "info";
      item.textContent = String(warning.message || "Review warning unavailable");
      this.warnings.appendChild(item);
    }
  }

  async startSession() {
    if (!this.context || this.busy) return;
    await this.run(async () => {
      const payload = await requestJson("/api/segmentation/correction-sessions", {
        method: "POST",
        body: JSON.stringify({ label_map_id: this.context.labelMapId }),
      });
      this.session = payload.correction_session;
    });
  }

  async applyAtCrosshair() {
    if (!this.context || !this.session || this.busy) return;
    const center = this.getCrosshair?.();
    const plane = this.getPlane?.() || "axial";
    if (!Array.isArray(center) || center.length !== 3) return;
    await this.run(async () => {
      const payload = await requestJson(
        `/api/segmentation/correction-sessions/${this.session.session_id}/actions`,
        {
          method: "POST",
          body: JSON.stringify(validateCorrectionDraftAction({
            kind: this.kind.value,
            label_id: this.context.labelId,
            center_lps_mm: center.map(Number),
            radius_mm: Number(this.radius.value),
            plane,
          })),
        },
      );
      this.session = payload.correction_session;
    });
  }

  async moveHistory(direction) {
    if (!this.session || this.busy) return;
    await this.run(async () => {
      const payload = await requestJson(
        `/api/segmentation/correction-sessions/${this.session.session_id}/${direction}`,
        { method: "POST", body: "{}" },
      );
      this.session = payload.correction_session;
    });
  }

  async discardSession() {
    if (!this.session || this.busy) return;
    await this.run(async () => {
      await requestJson(
        `/api/segmentation/correction-sessions/${this.session.session_id}/discard`,
        { method: "POST", body: "{}" },
      );
      this.session = null;
    });
  }

  async run(operation) {
    this.busy = true;
    this.root.dataset.state = "loading";
    this.render();
    try {
      await operation();
      this.root.dataset.state = "ready";
      this.status.textContent = this.session
        ? `${this.session.applied_action_count} draft actions applied · ${ACTION_LABELS[this.kind.value]}`
        : `${this.context.displayName} · correction draft discarded`;
    } catch (error) {
      this.root.dataset.state = "error";
      this.status.textContent = error instanceof Error ? error.message : "Correction action failed";
    } finally {
      this.busy = false;
      this.render();
    }
  }

  render() {
    const available = Boolean(this.context);
    const active = Boolean(this.session?.state === "draft");
    this.start.disabled = !available || active || this.busy;
    this.kind.disabled = !active || this.busy;
    this.radius.disabled = !active || this.busy;
    this.apply.disabled = !active || this.busy;
    this.undo.disabled = !active || !this.session?.can_undo || this.busy;
    this.redo.disabled = !active || !this.session?.can_redo || this.busy;
    this.discard.disabled = !active || this.busy;
    this.start.hidden = active;
  }
}
