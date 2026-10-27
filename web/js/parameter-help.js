// Presentation-only contextual parameter help. No patient data or network calls.
const HELP = Object.freeze({
  renderQualityPolicy: ["Rendering quality", "Sets the balance between responsiveness and image quality for direct volume rendering. Higher quality can increase GPU work; this does not alter the source scan."],
  transferPresetSelect: ["Medical preset", "Selects a predefined intensity-to-color and opacity mapping for the displayed volume. It does not modify the acquired voxel values."],
  renderingModeSelect: ["Rendering mode", "Chooses how the volume is visualized: accumulated volume rendering, maximum or minimum intensity, average intensity, a single slice, or a thick slab."],
  slicePlaneSelect: ["Medical plane", "Chooses the anatomical orientation of the slice or thick-slab view: axial, coronal, or sagittal in patient space."],
  slabProjectionSelect: ["Slab method", "Determines how intensities within a thick slab are combined: maximum (MIP), minimum (MinIP), or average."],
  slicePosition: ["Plane position", "Moves the displayed slice through the acquired volume in the selected patient-space plane; follows the synchronized MPR crosshair."],
  slabThicknessSelect: ["Slab thickness", "Sets the physical depth of the thick-slab view in millimetres. A thicker slab combines information from more of the acquired volume."],
  slabCustomThickness: ["Custom thickness", "Sets a custom thick-slab depth in millimetres when Custom is selected."],
  transferWindowCenter: ["Window level", "Sets the center of the displayed intensity window. Changing it shifts which CT or MR intensities appear most prominent; source intensities remain unchanged."],
  transferWindowWidth: ["Window width", "Sets the width of the displayed intensity window. Narrower windows emphasize a smaller intensity range; source intensities remain unchanged."],
  transferRangeLow: ["Intensity minimum", "Sets the lower visible intensity bound in the transfer function. Values below it are suppressed in the displayed volume; the scan is not cropped or edited."],
  transferRangeHigh: ["Intensity maximum", "Sets the upper visible intensity bound in the transfer function. Values above it are suppressed in the displayed volume; the scan is not cropped or edited."],
  transferDensity: ["Absorption", "Controls how strongly the DVR volume accumulates opacity along a viewing ray. Higher absorption tends to make structures more opaque; geometry is unchanged."],
  opacitySlider: ["Overall opacity", "Adjusts the overall transparency of the displayed patient volume. It does not change segmentation labels or surface geometry."],
  transferOpacitySoftness: ["Opacity softness", "Adjusts the transition between more transparent and more opaque intensities in the volume display."],
  transferEdgeDefinition: ["Edge definition", "Adjusts how strongly intensity transitions are emphasized in the displayed volume. It does not sharpen or modify the stored scan."],
  transferShadingStrength: ["Depth shading", "Adjusts the strength of lighting and depth cues in volume rendering. It changes presentation, not source voxels."],
  volumeSurfaceIsovalue: ["Surface isovalue", "Sets the direct volume-surface threshold. CT uses Hounsfield units; MRI uses normalized relative signal. Changing it rebuilds only the derived surface and never modifies the source scan."],
  volumeSurfaceRegionMode: ["Direct CT visibility", "Chooses which displayed direct-CT regions are visible. Hiding a region is reversible and does not delete the underlying generated geometry."],
  segmentationOverlayToggle: ["Show segmentation overlay", "Shows or hides the segmentation label colors on the axial, coronal, and sagittal image views. It does not change labels."],
  segmentationOverlayOpacity: ["Overlay opacity", "Adjusts the transparency of segmentation colors over the source MPR images, without modifying the segmentation."],
  segmentationSurfaceToggle: ["Show 3D segmentation surfaces", "Shows or hides available segmentation-derived 3D surfaces. This does not delete the source label map."],
  segmentationStructureSearch: ["Find a structure", "Filters the structure list by anatomy name or label. Filtering does not change visibility or the source segmentation."],
  segmentationStructureExplode: ["Explode anatomy", "Separates anatomical groups by bounded display-only offsets to improve inspection. Their canonical Patient-LPS coordinates remain unchanged."],
  segmentationStructureColor: ["Structure color", "Sets the display color for the selected structure. The underlying segmentation and geometry are unchanged."],
  segmentationStructureOpacity: ["Structure opacity", "Sets the transparency of the selected 3D structure. It does not change its segmentation mask or geometry."],
  segmentationStructureClipParticipation: ["Follow Directional Cut", "Controls whether the selected structure follows the active multi-plane clipping range. Switching it off leaves that structure uncut in the 3D viewer."],
  mprClippingOverlayToggle: ["Show clipping on MPR", "Shows or hides dashed clipping boundaries and excluded-region shading on reference MPR views. It does not clip or change the source MPR images."],
  segmentationCorrectionKind: ["Review action", "Selects a reversible draft review mark, include intent, or exclude intent for the selected segmentation. The sealed source label map stays unchanged."],
  segmentationCorrectionRadius: ["Review radius", "Sets the physical radius, in millimetres, of the draft review action centered on the MPR crosshair."],
});

const SPECIAL = Object.freeze({
  "surface-volume": ["Direct volume surface source", "Includes or excludes the modality-appropriate direct volume-derived surface in Surface or Combined views. CT uses HU; MRI uses normalized relative signal. Source voxels and reusable generated geometry remain intact."],
  "surface-segmentation": ["Segmentation surface source", "Includes or excludes available segmentation-derived surfaces in Surface or Combined views without editing their masks."],
  "profile": ["Presentation", "The normal viewing intent uses polished surface lighting and materials. It changes only how existing surfaces appear; source anatomy and mesh coordinates remain unchanged."],
  "source": ["Surface sources", "Choose which kinds of 3D surfaces appear in Surface and Combined modes: direct CT and/or segmentation-derived."],
  "workflow": ["Segmentation workflow", "Starts on-demand segmentation for the current study when supported. Volume and MPR visualization remain available while it runs."],
  "structure-row": ["Structure row controls", "The checkbox shows or hides this structure; selecting its name opens its presentation controls; Iso temporarily isolates it. These actions do not alter the stored label map."],
  "axial-enabled": ["Axial clipping", "Moving either bound inward automatically enables the two-sided inferior-to-superior clipping interval. Returning both bounds to the full range disables clipping. The source geometry is unchanged."],
  "coronal-enabled": ["Coronal clipping", "Moving either bound inward automatically enables the two-sided posterior-to-anterior clipping interval. Returning both bounds to the full range disables clipping. The source geometry is unchanged."],
  "sagittal-enabled": ["Sagittal clipping", "Moving either bound inward automatically enables the two-sided right-to-left clipping interval. Returning both bounds to the full range disables clipping. The source geometry is unchanged."],
  "axial-start": ["Inferior clipping boundary", "Moves the inferior bound of axial clipping toward the superior bound. Moving either bound inward activates clipping; the region between both bounds is retained in 3D."],
  "axial-end": ["Superior clipping boundary", "Moves the superior bound of axial clipping toward the inferior bound. Moving either bound inward activates clipping; the region between both bounds is retained in 3D."],
  "coronal-start": ["Posterior clipping boundary", "Moves the posterior bound of coronal clipping toward the anterior bound. Moving either bound inward activates clipping; the region between both bounds is retained in 3D."],
  "coronal-end": ["Anterior clipping boundary", "Moves the anterior bound of coronal clipping toward the posterior bound. Moving either bound inward activates clipping; the region between both bounds is retained in 3D."],
  "sagittal-start": ["Right clipping boundary", "Moves the right bound of sagittal clipping toward the left bound. Moving either bound inward activates clipping; the region between both bounds is retained in 3D."],
  "sagittal-end": ["Left clipping boundary", "Moves the left bound of sagittal clipping toward the right bound. Moving either bound inward activates clipping; the region between both bounds is retained in 3D."],
});

function trigger(key, title, dialogId) {
  const icon = document.createElement("span");
  icon.className = "va-parameter-help";
  icon.dataset.vaHelp = key;
  icon.setAttribute("role", "button");
  icon.setAttribute("tabindex", "0");
  icon.setAttribute("aria-label", `Help: ${title}`);
  icon.setAttribute("aria-haspopup", "dialog");
  icon.setAttribute("aria-controls", dialogId);
  icon.setAttribute("aria-expanded", "false");
  icon.textContent = "?";
  return icon;
}

function addToCaption(caption, key, title, dialogId) {
  if (!caption || caption.querySelector(`.va-parameter-help[data-va-help="${key}"]`)) return;
  // Insert into a textual label, not into its associated input/select. A role=button
  // span is not an additional labelable form control. Clicks cancel label activation.
  const textNode = Array.from(caption.childNodes).find((node) => (
    node.nodeType === Node.TEXT_NODE && node.textContent.trim()
  ));
  const icon = trigger(key, title, dialogId);
  if (textNode) textNode.after(icon);
  else caption.prepend(icon);
}

function installStatic(dialogId) {
  // Reconstruction mode cards do not use contextual help controls.
  for (const [id, [title]] of Object.entries(HELP)) {
    const control = document.getElementById(id);
    if (!control) continue;
    const label = document.querySelector(`label[for="${id}"]`) || control.closest("label");
    if (!label) continue;
    // Keep CT help inline with the caption and editable control.
    const caption = label.querySelector(".va-volume-surface-caption-title") || Array.from(label.children).find((child) => (
      child.tagName === "SPAN"
      && !child.classList.contains("sr-only")
      && !child.querySelector("input,select,textarea")
      && child.textContent.trim()
    )) || label;
    addToCaption(caption, id, title, dialogId);
  }
  const selectors = {
    "surface-volume": '[data-reconstruction-source-row="volume-derived"] > span',
    "surface-segmentation": '[data-reconstruction-source-row="segmentation-derived"] > span',
    profile: "#reconstructionPresentationProfileLabel",
    source: ".reconstruction-surface-sources > .reconstruction-source-label",
    workflow: "#segmentationWorkflowTitle",
    "axial-enabled": '[data-clip-plane="axial"] .clip-plane-label',
    "coronal-enabled": '[data-clip-plane="coronal"] .clip-plane-label',
    "sagittal-enabled": '[data-clip-plane="sagittal"] .clip-plane-label',
    "axial-start": '[data-clip-plane="axial"] .clip-boundary-labels > span:first-child',
    "axial-end": '[data-clip-plane="axial"] .clip-boundary-labels > span:last-child',
    "coronal-start": '[data-clip-plane="coronal"] .clip-boundary-labels > span:first-child',
    "coronal-end": '[data-clip-plane="coronal"] .clip-boundary-labels > span:last-child',
    "sagittal-start": '[data-clip-plane="sagittal"] .clip-boundary-labels > span:first-child',
    "sagittal-end": '[data-clip-plane="sagittal"] .clip-boundary-labels > span:last-child',
  };
  for (const [key, selector] of Object.entries(selectors)) {
    addToCaption(document.querySelector(selector), key, SPECIAL[key][0], dialogId);
  }
}

export function installParameterHelp() {
  if (!document.querySelector(".right-panel") || document.getElementById("vaParameterHelpDialog")) return;
  const dialog = document.createElement("div");
  dialog.id = "vaParameterHelpDialog";
  dialog.className = "va-parameter-help-popover";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "false");
  dialog.setAttribute("aria-labelledby", "vaParameterHelpTitle");
  dialog.setAttribute("aria-describedby", "vaParameterHelpDescription");
  dialog.hidden = true;
  const title = document.createElement("strong");
  title.id = "vaParameterHelpTitle";
  const description = document.createElement("p");
  description.id = "vaParameterHelpDescription";
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "va-parameter-help-close";
  closeButton.setAttribute("aria-label", "Close parameter help");
  closeButton.textContent = "×";
  const header = document.createElement("div");
  header.className = "va-parameter-help-header";
  header.append(title, closeButton);
  dialog.append(header, description);
  document.body.append(dialog);
  let opener = null;

  function close({ returnFocus = false } = {}) {
    if (opener) opener.setAttribute("aria-expanded", "false");
    dialog.hidden = true;
    if (returnFocus && opener?.isConnected) opener.focus();
    opener = null;
  }
  function open(icon) {
    const entry = HELP[icon.dataset.vaHelp] || SPECIAL[icon.dataset.vaHelp];
    if (!entry) return;
    if (!dialog.hidden && opener === icon) { close({ returnFocus: true }); return; }
    close();
    opener = icon;
    title.textContent = entry[0];
    description.textContent = entry[1];
    icon.setAttribute("aria-expanded", "true");
    dialog.hidden = false;
    // Fixed positioning avoids clipping inside the scrollable control sidebar.
    const rect = icon.getBoundingClientRect();
    const width = Math.min(300, window.innerWidth - 24);
    dialog.style.width = `${width}px`;
    dialog.style.left = `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`;
    const desiredTop = rect.bottom + 7;
    const height = dialog.getBoundingClientRect().height;
    dialog.style.top = `${desiredTop + height <= window.innerHeight - 12 ? desiredTop : Math.max(12, rect.top - height - 7)}px`;
    closeButton.focus();
  }
  closeButton.addEventListener("click", () => close({ returnFocus: true }));
  document.addEventListener("click", (event) => {
    const icon = event.target.closest?.(".va-parameter-help");
    if (icon) {
      event.preventDefault();
      event.stopPropagation();
      open(icon);
    } else if (!dialog.hidden && !dialog.contains(event.target)) close();
  }, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !dialog.hidden) {
      event.preventDefault();
      close({ returnFocus: true });
    } else if ((event.key === "Enter" || event.key === " ") && event.target.matches?.(".va-parameter-help")) {
      event.preventDefault();
      open(event.target);
    }
  }, true);
  // Keep help open during scroll; keyboard focus can scroll the sidebar.
  window.addEventListener("resize", () => { if (!dialog.hidden) close(); });

  installStatic(dialog.id);
  const groups = document.getElementById("segmentationStructureGroups");
  if (groups) {
    // Rows are recreated during filtering; use delegated listeners for new rows.
    const enhanceRows = () => {
      for (const row of groups.querySelectorAll(".structure-row:not([data-va-help-ready])")) {
        row.dataset.vaHelpReady = "true";
        row.append(trigger("structure-row", SPECIAL["structure-row"][0], dialog.id));
      }
    };
    const observer = new MutationObserver((changes) => {
      if (changes.some((change) => change.addedNodes.length)) enhanceRows();
    });
    observer.observe(groups, { childList: true, subtree: true });
    enhanceRows();
  }
  // Modality changes rewrite the window-level label; restore its help control afterward.
  const windowLevel = document.getElementById("transferWindowCenterLabel");
  if (windowLevel) {
    new MutationObserver(() => {
      if (!windowLevel.querySelector('.va-parameter-help')) {
        addToCaption(windowLevel, "transferWindowCenter", HELP.transferWindowCenter[0], dialog.id);
      }
    }).observe(windowLevel, { childList: true });
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", installParameterHelp, { once: true });
else installParameterHelp();
