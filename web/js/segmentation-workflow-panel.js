const ACTIVE_STATES = new Set(["queued", "starting", "running", "cancelling", "finalizing"]);

function finitePercent(progress) {
  const value = Number(progress?.percent);
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
}

export class SegmentationWorkflowPanel {
  constructor(root, { onPrimary, onCancel } = {}) {
    if (!(root instanceof HTMLElement)) throw new Error("Segmentation workflow panel root is required");
    this.root = root;
    this.status = root.querySelector("#segmentationWorkflowStatus");
    this.badge = root.querySelector("#segmentationWorkflowBadge");
    this.provider = root.querySelector("#segmentationWorkflowProvider");
    this.progress = root.querySelector("#segmentationWorkflowProgress");
    this.progressFill = root.querySelector("#segmentationWorkflowProgressFill");
    this.progressText = root.querySelector("#segmentationWorkflowProgressText");
    this.primary = root.querySelector("#segmentationWorkflowPrimary");
    this.cancel = root.querySelector("#segmentationWorkflowCancel");
    this.snapshot = null;
    this.activatedLabelMapId = null;
    this.busy = false;
    this.primary.addEventListener("click", () => onPrimary?.());
    this.cancel.addEventListener("click", () => onCancel?.());
    this.reset();
  }

  reset(message = "Patient volume loads before segmentation becomes available.") {
    this.snapshot = null;
    this.activatedLabelMapId = null;
    this.busy = false;
    this.root.dataset.state = "waiting";
    this.status.textContent = message;
    this.badge.textContent = "Waiting";
    this.provider.textContent = "Segmentation is intentionally off the initial loading path.";
    this.progress.hidden = true;
    this.primary.textContent = "Start Segmentation";
    this.primary.disabled = true;
    this.primary.hidden = false;
    this.cancel.hidden = true;
  }

  setBusy(message) {
    this.busy = true;
    this.root.dataset.state = "loading";
    this.status.textContent = message;
    this.primary.disabled = true;
    this.cancel.disabled = true;
  }

  setActivated(labelMapId) {
    this.activatedLabelMapId = String(labelMapId || "") || null;
    if (this.snapshot) this.render(this.snapshot);
  }

  render(workflow) {
    if (!workflow || typeof workflow !== "object") {
      this.reset("Segmentation status is unavailable.");
      return;
    }
    this.snapshot = workflow;
    this.busy = false;
    const state = String(workflow.state || "unavailable");
    const active = ACTIVE_STATES.has(state);
    const readOnlyMri = workflow.modality === "MR" && workflow.model_id === "total_mr";
    const mriPresentationReady = readOnlyMri && workflow.mri_label_map_ready === true;
    const ready = state === "available" && (!readOnlyMri || mriPresentationReady);
    const activated = ready
      && this.activatedLabelMapId
      && this.activatedLabelMapId === String(workflow.label_map_id || "");
    const providerName = workflow.provider_id === "totalsegmentator"
      ? (workflow.modality === "MR" && workflow.model_id === "total_mr"
        ? "TotalSegmentator · MRI (total_mr)"
        : "TotalSegmentator · CT")
      : String(workflow.provider_id || "Segmentation provider");

    this.root.dataset.state = activated ? "active" : state;
    this.status.textContent = activated
      ? `${Number(workflow.present_label_count) || 0} structures available · segmentation active`
      : String(workflow.message || "Segmentation status unavailable");
    this.provider.textContent = providerName;

    const percent = finitePercent(workflow.progress);
    this.progress.hidden = !active || percent === null;
    if (!this.progress.hidden) {
      this.progress.setAttribute("aria-valuenow", String(Math.round(percent)));
      this.progressFill.style.width = `${percent}%`;
      this.progressText.textContent = `${Math.round(percent)}% · ${String(workflow.progress?.message || "Processing")}`;
    }

    this.cancel.hidden = !Boolean(workflow.can_cancel);
    this.cancel.disabled = !Boolean(workflow.can_cancel);
    this.primary.hidden = active || activated;
    this.primary.disabled = true;

    if (ready && !activated) {
      this.primary.textContent = "Use Segmentation";
      this.primary.disabled = !Boolean(workflow.can_use);
    } else if (state === "idle") {
      this.primary.textContent = "Start Segmentation";
      this.primary.disabled = !Boolean(workflow.can_start);
    } else if (state === "output_ready") {
      this.primary.textContent = "Prepare Segmentation";
      this.primary.disabled = !Boolean(workflow.can_start);
    } else if (state === "failed" || state === "cancelled") {
      this.primary.textContent = "Retry";
      this.primary.disabled = !Boolean(workflow.can_start);
    } else if (state === "waiting" || state === "unsupported" || state === "unavailable") {
      this.primary.textContent = "Start Segmentation";
      this.primary.disabled = true;
    }

    if (readOnlyMri && !mriPresentationReady) {
      // MRI execution remains disabled; D3 may only reuse an already persisted qualified map.
      this.primary.textContent = "Start Segmentation";
      this.primary.disabled = true;
    }

    const badge = {
      available: activated ? "Active" : "Ready",
      waiting: "Waiting",
      idle: "Not started",
      queued: "Queued",
      starting: "Starting",
      running: "Processing",
      cancelling: "Cancelling",
      finalizing: "Finalizing",
      output_ready: "Prepare",
      failed: "Failed",
      cancelled: "Cancelled",
      unsupported: "Unavailable",
      unavailable: "Unavailable",
    }[state] || "Unavailable";
    this.badge.textContent = activated ? "Active" : badge;
  }
}
