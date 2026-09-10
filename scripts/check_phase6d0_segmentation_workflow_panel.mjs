#!/usr/bin/env node
import assert from "node:assert/strict";

class FakeElement {
  constructor(id = "") {
    this.id = id;
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.style = {};
    this.attributes = new Map();
    this.listeners = new Map();
  }
  addEventListener(name, handler) { this.listeners.set(name, handler); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  click() { this.listeners.get("click")?.(); }
}

class FakeRoot extends FakeElement {
  constructor() {
    super("segmentationWorkflowPanel");
    this.nodes = new Map([
      ["#segmentationWorkflowStatus", new FakeElement("segmentationWorkflowStatus")],
      ["#segmentationWorkflowBadge", new FakeElement("segmentationWorkflowBadge")],
      ["#segmentationWorkflowProvider", new FakeElement("segmentationWorkflowProvider")],
      ["#segmentationWorkflowProgress", new FakeElement("segmentationWorkflowProgress")],
      ["#segmentationWorkflowProgressFill", new FakeElement("segmentationWorkflowProgressFill")],
      ["#segmentationWorkflowProgressText", new FakeElement("segmentationWorkflowProgressText")],
      ["#segmentationWorkflowPrimary", new FakeElement("segmentationWorkflowPrimary")],
      ["#segmentationWorkflowCancel", new FakeElement("segmentationWorkflowCancel")],
    ]);
  }
  querySelector(selector) { return this.nodes.get(selector) || null; }
}

globalThis.HTMLElement = FakeElement;
const { SegmentationWorkflowPanel } = await import("../web/js/segmentation-workflow-panel.js");

let primaryClicks = 0;
let cancelClicks = 0;
const root = new FakeRoot();
const panel = new SegmentationWorkflowPanel(root, {
  onPrimary: () => { primaryClicks += 1; },
  onCancel: () => { cancelClicks += 1; },
});

const idle = {
  study_id: "a".repeat(32), modality: "CT", provider_id: "totalsegmentator",
  state: "idle", message: "Segmentation has not been started",
  can_start: true, can_cancel: false, can_use: false, progress: null,
};
panel.render(idle);
assert.equal(root.dataset.state, "idle");
assert.equal(panel.primary.textContent, "Start Segmentation");
assert.equal(panel.primary.disabled, false);
assert.equal(panel.progress.hidden, true);
panel.primary.click();
assert.equal(primaryClicks, 1);

const running = {
  ...idle,
  state: "running",
  message: "Running full-resolution CT segmentation",
  can_start: false,
  can_cancel: true,
  progress: { stage: "inference", percent: 25, message: "Running full-resolution CT segmentation" },
};
panel.render(running);
assert.equal(root.dataset.state, "running");
assert.equal(panel.primary.hidden, true);
assert.equal(panel.cancel.hidden, false);
assert.equal(panel.progress.hidden, false);
assert.equal(panel.progress.attributes.get("aria-valuenow"), "25");
assert.equal(panel.progressFill.style.width, "25%");
panel.cancel.click();
assert.equal(cancelClicks, 1);

const available = {
  ...idle,
  state: "available",
  message: "Existing segmentation is ready to use",
  can_start: false,
  can_use: true,
  label_map_id: `map-${"b".repeat(32)}`,
  present_label_count: 49,
  progress: { stage: "complete", percent: 100, message: "Segmentation ready" },
};
panel.render(available);
assert.equal(panel.primary.textContent, "Use Segmentation");
assert.equal(panel.primary.disabled, false);
panel.setActivated(available.label_map_id);
assert.equal(root.dataset.state, "active");
assert.equal(panel.badge.textContent, "Active");
assert.match(panel.status.textContent, /49 structures available/);
assert.equal(panel.primary.hidden, true);

const failed = {
  ...idle,
  state: "failed",
  message: "Segmentation failed. Retry when ready",
  can_start: true,
};
panel.render(failed);
assert.equal(panel.primary.textContent, "Retry");
assert.equal(panel.primary.disabled, false);

const unsupported = {
  ...idle,
  modality: "MR",
  state: "unsupported",
  message: "MR segmentation provider is not available in Phase 6D0",
  can_start: false,
};
panel.render(unsupported);
assert.equal(panel.primary.disabled, true);
assert.match(panel.provider.textContent, /Phase 7/);

console.log("PHASE6D0_EXPLICIT_START_ACTION=PASS");
console.log("PHASE6D0_REAL_PROGRESS_DISPLAY=PASS");
console.log("PHASE6D0_CANCEL_RETRY_STATES=PASS");
console.log("PHASE6D0_EXISTING_RESULT_REUSE=PASS");
console.log("PHASE6D0_MRI_PROVIDER_GATING=PASS");
console.log("PHASE6D0_WORKFLOW_PANEL_OK=YES");
