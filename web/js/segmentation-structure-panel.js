import {
  createStructureInteractionDefaults,
  createStructureInteractionState,
  resetStructureInteractionState,
} from "./segmentation-structure-interaction.js?v=phase6f-a-r1";

const HEX_COLOR = /^#[0-9a-f]{6}$/i;

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, Number(value)));
}

function requireCatalog(descriptor) {
  const catalog = descriptor?.structure_catalog;
  if (
    catalog?.schema_version !== 1
    || !Array.isArray(catalog.groups)
    || !Array.isArray(catalog.structures)
    || catalog.structure_count !== catalog.structures.length
  ) {
    throw new Error("Segmentation structure catalog is invalid");
  }
  return catalog;
}

export function createStructurePresentation(descriptor) {
  const catalog = requireCatalog(descriptor);
  const structures = new Map();
  for (const raw of catalog.structures) {
    const labelId = Number(raw?.label_id);
    const colorHex = String(raw?.color_hex || "").toLowerCase();
    if (
      !Number.isInteger(labelId)
      || labelId <= 0
      || structures.has(labelId)
      || typeof raw.name !== "string"
      || typeof raw.display_name !== "string"
      || typeof raw.group_id !== "string"
      || typeof raw.group_name !== "string"
      || !HEX_COLOR.test(colorHex)
    ) {
      throw new Error("Segmentation structure definition is invalid");
    }
    const interactionDefaults = createStructureInteractionDefaults();
    structures.set(labelId, {
      labelId,
      name: raw.name,
      displayName: raw.display_name,
      groupId: raw.group_id,
      groupName: raw.group_name,
      defaultColorHex: colorHex,
      colorHex,
      visible: raw.default_visible !== false,
      surfaceVisible: false,
      opacity: clamp(raw.default_opacity ?? 1, 0, 1),
      clippingEnabled: interactionDefaults.clippingEnabled,
      explodedOffsetLpsMm: interactionDefaults.explodedOffsetLpsMm,
    });
  }
  if (structures.size !== catalog.structure_count) {
    throw new Error("Segmentation structure catalog count is invalid");
  }
  return {
    labelMapId: descriptor.label_map_id,
    groups: catalog.groups.map((group) => ({
      groupId: String(group.group_id),
      displayName: String(group.display_name),
    })),
    structures,
    selectedLabelId: null,
    filter: "",
    interaction: createStructureInteractionState(),
  };
}

export function activateSurfaceForStructure(presentation, labelId) {
  const normalized = Number(labelId);
  const structure = presentation?.structures?.get(normalized);
  if (!structure) {
    throw new Error("Segmentation structure selection is invalid");
  }
  if (structure.visible) structure.surfaceVisible = true;
  presentation.selectedLabelId = normalized;
}

export function resetStructurePresentation(presentation) {
  for (const structure of presentation.structures.values()) {
    structure.visible = true;
    structure.surfaceVisible = false;
    structure.colorHex = structure.defaultColorHex;
    structure.opacity = 1;
  }
  presentation.selectedLabelId = null;
  resetStructureInteractionState(presentation);
}

export function isolateStructure(presentation, labelId) {
  const normalized = Number(labelId);
  if (!presentation.structures.has(normalized)) {
    throw new Error("Segmentation structure selection is invalid");
  }
  for (const structure of presentation.structures.values()) {
    const isolated = structure.labelId === normalized;
    structure.visible = isolated;
    structure.surfaceVisible = isolated;
  }
  presentation.selectedLabelId = normalized;
}

function setAllVisible(presentation, visible) {
  for (const structure of presentation.structures.values()) {
    structure.visible = visible;
    structure.surfaceVisible = visible;
  }
}

function matchingStructures(presentation, groupId) {
  const needle = presentation.filter.trim().toLowerCase();
  return Array.from(presentation.structures.values()).filter((structure) => {
    if (structure.groupId !== groupId) return false;
    if (!needle) return true;
    return [
      structure.displayName,
      structure.name,
      structure.groupName,
      `label ${structure.labelId}`,
    ].some((value) => value.toLowerCase().includes(needle));
  });
}

function button(text, className, action, labelId = null) {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  element.dataset.structureAction = action;
  if (labelId !== null) element.dataset.labelId = String(labelId);
  element.textContent = text;
  return element;
}

export class SegmentationStructurePanel {
  constructor(root, onPresentationChange = () => {}) {
    if (!(root instanceof HTMLElement)) {
      throw new Error("Segmentation structure panel root is unavailable");
    }
    this.root = root;
    this.onPresentationChange = onPresentationChange;
    this.search = root.querySelector("#segmentationStructureSearch");
    this.groups = root.querySelector("#segmentationStructureGroups");
    this.summary = root.querySelector("#segmentationStructureSummary");
    this.selectedName = root.querySelector("#segmentationStructureSelectedName");
    this.selectedMetadata = root.querySelector("#segmentationStructureSelectedMetadata");
    this.color = root.querySelector("#segmentationStructureColor");
    this.opacity = root.querySelector("#segmentationStructureOpacity");
    this.opacityValue = root.querySelector("#segmentationStructureOpacityValue");
    this.presentation = null;
    this.expandedGroups = new Set();
    this.surfaceStates = new Map();

    this.search.addEventListener("input", () => {
      if (!this.presentation) return;
      this.presentation.filter = this.search.value;
      this.renderGroups();
    });
    root.addEventListener("click", (event) => this.handleClick(event));
    root.addEventListener("change", (event) => this.handleChange(event));
    root.addEventListener("toggle", (event) => {
      const details = event.target.closest?.(".structure-group");
      if (!details || !this.presentation || this.presentation.filter) return;
      if (details.open) this.expandedGroups.add(details.dataset.groupId);
      else this.expandedGroups.delete(details.dataset.groupId);
    }, true);
    this.opacity.addEventListener("input", () => {
      const structure = this.selectedStructure();
      if (!structure) return;
      structure.opacity = clamp(Number(this.opacity.value) / 100, 0, 1);
      this.opacityValue.textContent = `${Math.round(structure.opacity * 100)}%`;
      this.notify();
    });
  }

  load(descriptor) {
    this.presentation = createStructurePresentation(descriptor);
    this.surfaceStates.clear();
    this.expandedGroups = new Set(
      this.presentation.groups.length > 0
        ? [this.presentation.groups[0].groupId]
        : [],
    );
    this.root.dataset.state = "ready";
    this.search.disabled = false;
    for (const control of this.root.querySelectorAll("button, input")) {
      control.disabled = false;
    }
    this.render();
    return this.presentation;
  }

  clear() {
    this.presentation = null;
    this.expandedGroups.clear();
    this.surfaceStates.clear();
    this.root.dataset.state = "unavailable";
    this.search.value = "";
    this.groups.replaceChildren();
    this.summary.textContent = "Available after a canonical label map is loaded.";
    this.selectedName.textContent = "No structure selected";
    this.selectedMetadata.textContent = "Select a visible structure to edit its presentation.";
    for (const control of this.root.querySelectorAll("button, input")) {
      control.disabled = true;
    }
  }

  selectedStructure() {
    return this.presentation?.structures.get(this.presentation.selectedLabelId) || null;
  }

  setSurfaceStatusSnapshot(status) {
    this.surfaceStates.clear();
    if (Array.isArray(status?.labels)) {
      for (const entry of status.labels) {
        if (!Number.isInteger(entry?.labelId)) continue;
        this.surfaceStates.set(entry.labelId, {
          state: String(entry.state || "idle"),
          desired: Boolean(entry.desired),
          resident: Boolean(entry.resident),
        });
      }
    }
    if (this.presentation) this.renderGroups();
  }

  _surfaceStateIndicator(structure) {
    const snapshot = this.surfaceStates.get(structure.labelId);
    const state = snapshot?.state || "idle";
    const indicator = document.createElement("span");
    indicator.className = "structure-surface-state";
    indicator.dataset.surfaceState = state;
    indicator.setAttribute("aria-hidden", "true");
    const labels = {
      idle: "",
      queued: "…",
      building: "",
      ready: "✓",
      failed: "!",
    };
    indicator.textContent = labels[state] ?? "";
    const title = {
      idle: "3D surface not requested",
      queued: "3D surface queued",
      building: "Building refined 3D surface",
      ready: "Refined 3D surface ready",
      failed: "3D surface failed",
    };
    indicator.title = title[state] || title.idle;
    return indicator;
  }

  notify() {
    this.renderSummary();
    this.onPresentationChange(this.presentation);
  }

  handleClick(event) {
    const control = event.target.closest("[data-structure-action]");
    if (!control || !this.root.contains(control) || !this.presentation) return;
    const action = control.dataset.structureAction;
    const labelId = Number(control.dataset.labelId);
    if (action === "show-all") setAllVisible(this.presentation, true);
    if (action === "hide-all") setAllVisible(this.presentation, false);
    if (action === "reset") resetStructurePresentation(this.presentation);
    if (action === "isolate") isolateStructure(this.presentation, labelId);
    if (action === "select" && this.presentation.structures.has(labelId)) {
      activateSurfaceForStructure(this.presentation, labelId);
      this.render();
      this.notify();
      return;
    }
    this.render();
    this.notify();
  }

  handleChange(event) {
    if (!this.presentation) return;
    const visibility = event.target.closest("[data-structure-visible]");
    if (visibility) {
      const structure = this.presentation.structures.get(Number(visibility.dataset.labelId));
      if (!structure) return;
      structure.visible = visibility.checked;
      structure.surfaceVisible = visibility.checked;
      this.presentation.selectedLabelId = structure.labelId;
      this.render();
      this.notify();
      return;
    }
    if (event.target === this.color) {
      const structure = this.selectedStructure();
      if (!structure || !HEX_COLOR.test(this.color.value)) return;
      structure.colorHex = this.color.value.toLowerCase();
      this.renderGroups();
      this.notify();
    }
  }

  render() {
    this.renderGroups();
    this.renderInspector();
    this.renderSummary();
  }

  renderSummary() {
    if (!this.presentation) return;
    const visible = Array.from(this.presentation.structures.values())
      .filter((structure) => structure.visible).length;
    this.summary.textContent = `${visible} of ${this.presentation.structures.size} structures shown`;
  }

  renderGroups() {
    this.groups.replaceChildren();
    if (!this.presentation) return;
    let matchCount = 0;
    for (const group of this.presentation.groups) {
      const structures = matchingStructures(this.presentation, group.groupId);
      if (structures.length === 0) continue;
      matchCount += structures.length;
      const details = document.createElement("details");
      details.className = "structure-group";
      details.dataset.groupId = group.groupId;
      details.open = Boolean(this.presentation.filter)
        || this.expandedGroups.has(group.groupId);
      const summary = document.createElement("summary");
      const title = document.createElement("span");
      title.textContent = group.displayName;
      const count = document.createElement("strong");
      count.textContent = String(structures.length);
      summary.append(title, count);
      const list = document.createElement("div");
      list.className = "structure-list";
      for (const structure of structures) {
        const row = document.createElement("div");
        row.className = "structure-row";
        row.dataset.selected = String(
          structure.labelId === this.presentation.selectedLabelId,
        );
        const visibility = document.createElement("input");
        visibility.type = "checkbox";
        visibility.checked = structure.visible;
        visibility.dataset.structureVisible = "true";
        visibility.dataset.labelId = String(structure.labelId);
        visibility.setAttribute("aria-label", `Show ${structure.displayName}`);
        const swatch = document.createElement("span");
        swatch.className = "structure-swatch";
        swatch.style.backgroundColor = structure.colorHex;
        const select = button(
          structure.displayName,
          "structure-select",
          "select",
          structure.labelId,
        );
        select.title = `Select ${structure.displayName}`;
        const surfaceState = this._surfaceStateIndicator(structure);
        const isolate = button("Iso", "structure-isolate", "isolate", structure.labelId);
        isolate.title = `Isolate ${structure.displayName}`;
        isolate.setAttribute("aria-label", `Isolate ${structure.displayName}`);
        row.append(visibility, swatch, select, surfaceState, isolate);
        list.appendChild(row);
      }
      details.append(summary, list);
      this.groups.appendChild(details);
    }
    if (matchCount === 0) {
      const empty = document.createElement("p");
      empty.className = "structure-empty";
      empty.textContent = "No structures match this search.";
      this.groups.appendChild(empty);
    }
  }

  renderInspector() {
    const structure = this.selectedStructure();
    const disabled = !structure;
    this.color.disabled = disabled;
    this.opacity.disabled = disabled;
    if (!structure) {
      this.selectedName.textContent = "No structure selected";
      this.selectedMetadata.textContent = "Select a visible structure to edit its presentation.";
      this.opacityValue.textContent = "—";
      return;
    }
    this.selectedName.textContent = structure.displayName;
    this.selectedMetadata.textContent = `${structure.groupName} · Label ${structure.labelId}`;
    this.color.value = structure.colorHex;
    this.opacity.value = String(Math.round(structure.opacity * 100));
    this.opacityValue.textContent = `${Math.round(structure.opacity * 100)}%`;
  }
}
