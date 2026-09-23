import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import {
  qualifyCanonicalVolumeForDevice,
  qualifyVolumeRenderingCapabilities,
  validateVolumeRenderingDescriptor,
} from "./volume-rendering-capabilities.js";
import { PatientVolumeTextureManager } from "./volume-texture-manager.js?v=phase4c1-r1";
import {
  PatientVolumeRayMarcher,
  constrainMedicalIntensityInterval,
  listMedicalRenderingModes,
  listMedicalTransferPresets,
} from "./patient-volume-ray-marcher.js?v=phase4h6";
import {
  AdaptiveVolumeRenderingQuality,
} from "./volume-rendering-quality.js?v=phase4h1";
import {
  PatientVolumeSurfaceLayer,
} from "./volume-surface-viewer.js?v=phase6d2b-r1-phase6e-b-r1-phase6e-d-r1-phase6e-e-r1-phase6f-c-r3-phase6f-d-r1-post6f-b1b2b-r1";
import {
  ReconstructionVisualizationModeController,
} from "./reconstruction-visualization-mode.js?v=phase6d2a-r1";
import { AutomaticSurfaceModeCoordinator } from "./automatic-surface-mode.js?v=phase6i-b1-r1";
import { ExistingSegmentationSurfaceGate } from "./existing-segmentation-mode.js?v=phase6i-b2-r1";
import {
  ReconstructionPresentationProfileController,
} from "./reconstruction-presentation-profile.js?v=phase6e-a-r1-phase6e-c-r1";
import {
  createSurfaceLightingRig,
} from "./reconstruction-surface-presentation.js?v=phase6e-b-r1-phase6e-d-r1-phase6f-c-r3";
import {
  enableSurfaceLocalClipping,
} from "./reconstruction-surface-clipping.js?v=phase6f-d-r1-phase6f-e-r1";
import {
  resolveCombinedPresentationBalance,
} from "./reconstruction-combined-presentation.js?v=phase6e-e-r1";
import { SampleStudyCatalogClient } from "./sample-study-catalog.js?v=phase4g-r1";
import {
  classifySampleStudyActivation,
} from "./sample-study-activation.js?v=phase5f2-switch-r1";
import { projectMprClipping, renderMprClippingOverlay } from "./mpr-clipping-overlay.js?v=phase4h6";
import { installRenderingQualification } from "./rendering-qualification.js?v=phase4h6";
import {
  clearSegmentationOverlay,
  decodeSegmentationLabels,
  drawSegmentationLabels,
  drawSegmentationRgba,
} from "./segmentation-overlay.js?v=phase5e-r1-phase6f-b-r1";
import {
  SegmentationStructurePanel,
} from "./segmentation-structure-panel.js?v=phase5e-r1-phase6c-r2-phase6d0-explicit-r1-phase6f-a-r1-phase6f-b-r1-phase6f-d-r1-phase6f-e-r1";
import {
  resolve3dAppearanceContext,
} from "./segmentation-anatomical-appearance.js?v=ctb2-r1-ctb3a-r1";
import {
  resolveStructureInteraction,
} from "./segmentation-structure-interaction.js?v=phase6f-a-r1-phase6f-b-r1";
import {
  PatientSegmentationSurfaceLayer,
} from "./segmentation-surface-viewer.js?v=phase6a-r1-phase6b-r1-phase6c-r2-phase6d2b-r1-phase6e-b-r1-phase6e-d-r1-phase6f-b-r1-phase6b-fallback-r1-phase6f-c-r3-phase6f-d-r1-phase6f-e-r1-post6f-b2a-r1-ctb2-r1";
import {
  SegmentationCorrectionPanel,
} from "./segmentation-correction-panel.js?v=phase5f2-r1";
import {
  SegmentationWorkflowPanel,
} from "./segmentation-workflow-panel.js?v=phase6d0-r1-phase6j-b1-r1";

const THEME_KEY = "voxelatlas-theme";
const DEFAULT_OPACITY = 1.0;
const DEFAULT_RECONSTRUCTION_SURFACE_SOURCE_SELECTION = Object.freeze({
  "volume-derived": true,
  "segmentation-derived": true,
});
const INITIAL_VIEW_DISTANCE_SCALE = 1.18;
const CLIPPING_MINIMUM_GAP_PERCENT = 0.1;

const viewport = document.getElementById("viewport");
const viewerStage = document.getElementById("viewerStage");
const modelStatus = document.getElementById("modelStatus");
const statusText = document.getElementById("statusText");
const modelChip = document.getElementById("modelChip");
const directionalCutPanel = document.getElementById("directionalCutPanel");
const clippingResetButton = document.getElementById("clippingResetButton");
const mprClippingOverlayToggle = document.getElementById("mprClippingOverlayToggle");
const segmentationWorkflowPanelRoot = document.getElementById("segmentationWorkflowPanel");
const reconstructionVisualizationPanel = document.getElementById("reconstructionVisualizationPanel");
const reconstructionVisualizationStatus = document.getElementById("reconstructionVisualizationStatus");
const surfaceModeStatusText = document.getElementById("surfaceModeStatusText");
const combinedModeStatusText = document.getElementById("combinedModeStatusText");
const reconstructionModeButtons = Array.from(document.querySelectorAll("[data-reconstruction-mode]"));
const reconstructionSurfaceSourceInputs = Array.from(document.querySelectorAll("[data-reconstruction-surface-source]"));
const reconstructionPresentationProfileStatus = document.getElementById("reconstructionPresentationProfileStatus");
const reconstructionPresentationProfileButtons = Array.from(document.querySelectorAll("[data-reconstruction-presentation-profile]"));
const volumeSurfacePanel = document.getElementById("volumeSurfacePanel");
const volumeSurfaceStatus = document.getElementById("volumeSurfaceStatus");
const volumeSurfaceIsovalue = document.getElementById("volumeSurfaceIsovalue");
const volumeSurfaceBuild = document.getElementById("volumeSurfaceBuild");
const volumeSurfaceClear = document.getElementById("volumeSurfaceClear");
const volumeSurfaceRegionMode = document.getElementById("volumeSurfaceRegionMode");
const volumeSurfaceRegionStatus = document.getElementById("volumeSurfaceRegionStatus");
const segmentationOverlayPanel = document.getElementById("segmentationOverlayPanel");
const segmentationOverlayStatus = document.getElementById("segmentationOverlayStatus");
const segmentationOverlayToggle = document.getElementById("segmentationOverlayToggle");
const segmentationOverlayOpacity = document.getElementById("segmentationOverlayOpacity");
const segmentationOverlayOpacityValue = document.getElementById("segmentationOverlayOpacityValue");
const segmentationSurfacePanel = document.getElementById("segmentationSurfacePanel");
const segmentationSurfaceToggle = document.getElementById("segmentationSurfaceToggle");
const segmentationSurfaceStatus = document.getElementById("segmentationSurfaceStatus");
const segmentation3dAppearance = document.getElementById("segmentation3dAppearance");
const segmentation3dAppearanceNote = document.getElementById("segmentation3dAppearanceNote");
const segmentationStructurePanelRoot = document.getElementById("segmentationStructurePanel");
const segmentationCorrectionPanelRoot = document.getElementById("segmentationCorrectionPanel");
const CLIPPING_PLANES = Object.freeze({
  axial: Object.freeze({ axis: "z", axisIndex: 2, coordinate: "Z", startLabel: "Inferior", endLabel: "Superior", reversed: false }),
  coronal: Object.freeze({ axis: "y", axisIndex: 1, coordinate: "Y", startLabel: "Posterior", endLabel: "Anterior", reversed: true }),
  sagittal: Object.freeze({ axis: "x", axisIndex: 0, coordinate: "X", startLabel: "Right", endLabel: "Left", reversed: false }),
});
const clippingRegistry = new Map(Object.keys(CLIPPING_PLANES).map((plane) => [
  plane,
  {
    status: document.querySelector(`[data-clip-enabled="${plane}"]`),
    start: document.querySelector(`[data-clip-start="${plane}"]`),
    end: document.querySelector(`[data-clip-end="${plane}"]`),
    startPosition: document.querySelector(`[data-clip-start-position="${plane}"]`),
    endPosition: document.querySelector(`[data-clip-end-position="${plane}"]`),
    startPercent: document.querySelector(`[data-clip-start-percent="${plane}"]`),
    endPercent: document.querySelector(`[data-clip-end-percent="${plane}"]`),
    range: document.querySelector(`[data-clip-range="${plane}"]`),
  },
]));
const volumeRenderingPanel = document.getElementById("volumeRenderingPanel");
const transferModality = document.getElementById("transferModality");
const transferPresetSelect = document.getElementById("transferPresetSelect");
const renderingModeSelect = document.getElementById("renderingModeSelect");
const renderingModeNote = document.getElementById("renderingModeNote");
const sliceRenderingControls = document.getElementById("sliceRenderingControls");
const slicePlaneSelect = document.getElementById("slicePlaneSelect");
const slicePosition = document.getElementById("slicePosition");
const slicePositionValue = document.getElementById("slicePositionValue");
const slabProjectionSelect = document.getElementById("slabProjectionSelect");
const slabThicknessSelect = document.getElementById("slabThicknessSelect");
const slabCustomThicknessControl = document.getElementById("slabCustomThicknessControl");
const slabCustomThickness = document.getElementById("slabCustomThickness");
const slabCustomThicknessValue = document.getElementById("slabCustomThicknessValue");
const transferWindowCenter = document.getElementById("transferWindowCenter");
const transferWindowCenterLabel = document.getElementById("transferWindowCenterLabel");
const transferWindowCenterValue = document.getElementById("transferWindowCenterValue");
const transferWindowWidth = document.getElementById("transferWindowWidth");
const transferWindowWidthValue = document.getElementById("transferWindowWidthValue");
const transferRangeLow = document.getElementById("transferRangeLow");
const transferRangeLowValue = document.getElementById("transferRangeLowValue");
const transferRangeHigh = document.getElementById("transferRangeHigh");
const transferRangeHighValue = document.getElementById("transferRangeHighValue");
const transferIntensityRange = document.getElementById("transferIntensityRange");
const transferDensity = document.getElementById("transferDensity");
const transferDensityValue = document.getElementById("transferDensityValue");
const transferOpacitySoftness = document.getElementById("transferOpacitySoftness");
const transferOpacitySoftnessValue = document.getElementById("transferOpacitySoftnessValue");
const transferEdgeDefinition = document.getElementById("transferEdgeDefinition");
const transferEdgeDefinitionValue = document.getElementById("transferEdgeDefinitionValue");
const transferShadingStrength = document.getElementById("transferShadingStrength");
const transferShadingStrengthValue = document.getElementById("transferShadingStrengthValue");
const dvrOnlyControls = [
  transferDensity,
  transferOpacitySoftness,
  transferEdgeDefinition,
  transferShadingStrength,
];
const intensityIntervalControls = [transferRangeLow, transferRangeHigh];
const transferResetButton = document.getElementById("transferResetButton");
const transferFunctionNote = document.getElementById("transferFunctionNote");
const renderQualityPolicy = document.getElementById("renderQualityPolicy");
const renderQualityStatus = document.getElementById("renderQualityStatus");
const opacitySlider = document.getElementById("opacitySlider");
const opacityValue = document.getElementById("opacityValue");
const resetButton = document.getElementById("resetButton");
const autoRotateButton = document.getElementById("autoRotateButton");
const logoutButton = document.getElementById("logoutButton");
const accountName = document.getElementById("accountName");
const themeToggle = document.getElementById("themeToggle");
const rotateToolButton = document.getElementById("rotateToolButton");
const panToolButton = document.getElementById("panToolButton");
const fitViewButton = document.getElementById("fitViewButton");
const zoomInButton = document.getElementById("zoomInButton");
const zoomOutButton = document.getElementById("zoomOutButton");
const fullscreenButton = document.getElementById("fullscreenButton");
const primaryInteractionHint = document.getElementById("primaryInteractionHint");
const themeColorMeta = document.querySelector('meta[name="theme-color"]');
const uploadDicomButton = document.getElementById("uploadDicomButton");
const uploadDicomLabel = document.getElementById("uploadDicomLabel");
const dicomFileInput = document.getElementById("dicomFileInput");
const uploadStatus = document.getElementById("uploadStatus");
const sampleCatalogButton = document.getElementById("sampleCatalogButton");
const sampleCatalogDialog = document.getElementById("sampleCatalogDialog");
const sampleCatalogClose = document.getElementById("sampleCatalogClose");
const sampleCatalogGrid = document.getElementById("sampleCatalogGrid");
const sampleCatalogEmpty = document.getElementById("sampleCatalogEmpty");
const sampleCatalogProgress = document.getElementById("sampleCatalogProgress");
const sampleCatalogProgressTitle = document.getElementById("sampleCatalogProgressTitle");
const sampleCatalogProgressText = document.getElementById("sampleCatalogProgressText");
const sampleReplaceConfirm = document.getElementById("sampleReplaceConfirm");
const sampleReplaceText = document.getElementById("sampleReplaceText");
const sampleReplaceCancel = document.getElementById("sampleReplaceCancel");
const sampleReplaceAccept = document.getElementById("sampleReplaceAccept");
const studyCard = document.querySelector(".study-card");
const studyLabel = document.getElementById("studyLabel");
const studyOriginBadge = document.getElementById("studyOriginBadge");
const studyId = document.getElementById("studyId");
const studyModality = document.getElementById("studyModality");
const studyDate = document.getElementById("studyDate");
const studyModalityValue = document.getElementById("studyModalityValue");
const studyInstanceCount = document.getElementById("studyInstanceCount");
const studySeriesCount = document.getElementById("studySeriesCount");
const seriesDescription = document.getElementById("seriesDescription");
const seriesManufacturer = document.getElementById("seriesManufacturer");
const seriesPixelSpacing = document.getElementById("seriesPixelSpacing");
const seriesMatrix = document.getElementById("seriesMatrix");
const seriesSliceThickness = document.getElementById("seriesSliceThickness");
const seriesButton = document.getElementById("seriesButton");
const seriesButtonLabel = document.getElementById("seriesButtonLabel");
const seriesDialog = document.getElementById("seriesDialog");
const seriesDialogClose = document.getElementById("seriesDialogClose");
const seriesDialogList = document.getElementById("seriesDialogList");
const workflowData = document.getElementById("workflowData");
const workflowReconstruction = document.getElementById("workflowReconstruction");
const workflowVisualization = document.getElementById("workflowVisualization");
const volumeStatusRow = document.getElementById("volumeStatusRow");
const volumeStatusText = document.getElementById("volumeStatusText");
const mprPanels = Array.from(document.querySelectorAll(".mpr-panel"));
const mprVolumeMessages = Array.from(document.querySelectorAll("[data-mpr-message]"));
const mprViews = Array.from(document.querySelectorAll("[data-mpr-view]"));
const mprRegistry = new Map([
  ["axial", {
    panel: document.getElementById("mprAxial"),
    view: document.querySelector('[data-mpr-view="axial"]'),
    surface: document.querySelector('[data-mpr-surface="axial"]'),
    canvas: document.getElementById("mprAxialCanvas"),
    overlayCanvas: document.getElementById("mprAxialSegmentationCanvas"),
    index: document.getElementById("mprAxialIndex"),
    position: document.getElementById("mprAxialPosition"),
    wl: document.getElementById("mprAxialWl"),
    message: document.querySelector('[data-mpr-message="axial"]'),
  }],
  ["coronal", {
    panel: document.getElementById("mprCoronal"),
    view: document.querySelector('[data-mpr-view="coronal"]'),
    surface: document.querySelector('[data-mpr-surface="coronal"]'),
    canvas: document.getElementById("mprCoronalCanvas"),
    overlayCanvas: document.getElementById("mprCoronalSegmentationCanvas"),
    index: document.getElementById("mprCoronalIndex"),
    position: document.getElementById("mprCoronalPosition"),
    wl: document.getElementById("mprCoronalWl"),
    message: document.querySelector('[data-mpr-message="coronal"]'),
  }],
  ["sagittal", {
    panel: document.getElementById("mprSagittal"),
    view: document.querySelector('[data-mpr-view="sagittal"]'),
    surface: document.querySelector('[data-mpr-surface="sagittal"]'),
    canvas: document.getElementById("mprSagittalCanvas"),
    overlayCanvas: document.getElementById("mprSagittalSegmentationCanvas"),
    index: document.getElementById("mprSagittalIndex"),
    position: document.getElementById("mprSagittalPosition"),
    wl: document.getElementById("mprSagittalWl"),
    message: document.querySelector('[data-mpr-message="sagittal"]'),
  }],
]);
const orientationGizmo = document.getElementById("orientationGizmo");
const gizmoEdges = Array.from(document.querySelectorAll("[data-gizmo-edge]"));
const gizmoAxisS = document.getElementById("gizmoAxisS");
const gizmoAxisA = document.getElementById("gizmoAxisA");
const gizmoAxisR = document.getElementById("gizmoAxisR");
const gizmoAxisL = document.getElementById("gizmoAxisL");
const gizmoLabelS = document.getElementById("gizmoLabelS");
const gizmoLabelA = document.getElementById("gizmoLabelA");
const gizmoLabelR = document.getElementById("gizmoLabelR");
const gizmoLabelL = document.getElementById("gizmoLabelL");

const volumeLayer = { available: false, root: null };

const state = {
  clipping: {
    axial: { enabled: false, startPercent: 0, endPercent: 100 },
    coronal: { enabled: false, startPercent: 0, endPercent: 100 },
    sagittal: { enabled: false, startPercent: 0, endPercent: 100 },
  },
  opacity: DEFAULT_OPACITY,
  autoRotate: false,
  viewerInteractionMode: "rotate",
  study: null,
  mpr: {
    descriptor: null,
    crosshairLpsMm: [0, 0, 0],
    activePlane: "axial",
    window: 400,
    level: 40,
  },
  segmentationOverlay: {
    descriptor: null,
    enabled: true,
    opacity: 0.45,
    presentation: null,
  },
  segmentationSurface: {
    descriptor: null,
    enabled: true,
  },
  volumeSurface: {
    descriptor: null,
  },
  reconstructionVisualization: {
    surfaceSourceSelection: { ...DEFAULT_RECONSTRUCTION_SURFACE_SOURCE_SELECTION },
  },
  size: new THREE.Vector3(1, 1, 1),
  cameraPosition: new THREE.Vector3(),
  cameraTarget: new THREE.Vector3(),
};

let volumeBuildPromise = null;
let volumeRenderingTask = null;
let mprDescriptorPromise = null;
let mprRenderGeneration = 0;
let mprRenderTimer = null;
let mprAbortController = null;
let segmentationOverlayDescriptorPromise = null;
let segmentationSurfaceDescriptorPromise = null;
let segmentationSurfaceLayer = null;
let volumeSurfaceDescriptorPromise = null;
let volumeSurfaceLayer = null;
let reconstructionVisualizationController = null;
let automaticSurfaceMode = null;
let segmentationSurfaceGate = null;
let autoSurfacePendingMode = null;
let autoSurfaceBuildPromise = null;
let autoSurfaceBuildStudyId = null;
let reconstructionPresentationProfileController = null;
let viewerRenderRequested = true;
let lastRenderedTimestamp = null;
let segmentationCorrectionPanel = null;
let segmentationWorkflowPanel = null;
let segmentationWorkflowSnapshot = null;
let segmentationWorkflowPollTimer = null;
let segmentationWorkflowGeneration = 0;
let activeSegmentationLabelMapId = null;
let segmentation3dAppearanceMode = "scientific";
let segmentation3dAppearanceLabelMapId = null;

function syncSegmentation3dAppearance() {
  const { ready, overrides } = resolve3dAppearanceContext(
    segmentation3dAppearanceMode,
    state.segmentationSurface.descriptor,
    state.segmentationOverlay.presentation,
  );
  segmentation3dAppearance.disabled = !ready;
  segmentation3dAppearance.value = segmentation3dAppearanceMode;
  // When a new label map is loading, the surface layer clears its old overrides.
  // Reapply only after the current surface and overlay descriptors agree.
  if (!ready) {
    segmentation3dAppearanceNote.textContent = "Available after a segmentation surface is ready. 3D colors only; MPR colors are unchanged.";
    return;
  }
  segmentationSurfaceLayer.set3dColorOverrides(overrides);
  segmentation3dAppearanceNote.textContent = segmentation3dAppearanceMode === "anatomical"
    ? `${overrides.size} structures use 3D anatomical colors; others retain their label colors. MPR colors are unchanged.`
    : "Original structure colors in 3D and MPR. Existing custom colors are preserved.";
}


function syncSegmentationCorrectionContext(presentation) {
  const descriptor = state.segmentationOverlay.descriptor;
  const structure = presentation?.structures?.get(presentation.selectedLabelId);
  if (!descriptor || !state.study?.study_id || !structure) {
    segmentationCorrectionPanel?.clear();
    return;
  }
  segmentationCorrectionPanel?.setContext({
    labelMapId: descriptor.label_map_id,
    studyId: state.study.study_id,
    labelId: structure.labelId,
    displayName: structure.displayName,
  });
}

function syncSegmentationOverlayPresentationStatus(presentation) {
  const descriptor = state.segmentationOverlay.descriptor;
  if (!descriptor || !(presentation?.structures instanceof Map)) return;
  const provider = descriptor.provider_id === "totalsegmentator"
    ? "TotalSegmentator"
    : String(descriptor.provider_id || "Segmentation");
  const visibleCount = Array.from(presentation.structures.values()).filter((structure) => (
    resolveStructureInteraction(presentation, structure.labelId).effectiveVisible
  )).length;
  const suffix = visibleCount === 1 ? "visible label" : "visible labels";
  segmentationOverlayStatus.textContent = `${provider} · ${visibleCount} ${suffix}`;
}

segmentationWorkflowPanel = new SegmentationWorkflowPanel(
  segmentationWorkflowPanelRoot,
  {
    onPrimary: () => void requestSegmentationStart(),
    onCancel: () => void requestSegmentationCancel(),
  },
);

const segmentationStructurePanel = new SegmentationStructurePanel(
  segmentationStructurePanelRoot,
  (presentation) => {
    state.segmentationOverlay.presentation = presentation;
    syncSegmentationOverlayPresentationStatus(presentation);
    redrawSegmentationOverlays();
    syncSegmentationSurface();
    syncSegmentation3dAppearance();
    syncSegmentationCorrectionContext(presentation);
  },
);
segmentationStructurePanel.clear();
segmentationCorrectionPanel = new SegmentationCorrectionPanel(
  segmentationCorrectionPanelRoot,
  {
    getCrosshair: () => [...state.mpr.crosshairLpsMm],
    getPlane: () => state.mpr.activePlane,
  },
);

function requestViewerRender() {
  viewerRenderRequested = true;
}

const scene = new THREE.Scene();
const anatomyGroup = new THREE.Group();
scene.add(anatomyGroup);
const surfaceLightingRig = createSurfaceLightingRig({
  three: THREE,
  scene,
  requestRender: requestViewerRender,
});

const camera = new THREE.PerspectiveCamera(29, 1, 0.005, 40);
const renderer = new THREE.WebGLRenderer({
  antialias: true,
  alpha: true,
  powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.86;
enableSurfaceLocalClipping(renderer);
viewport.appendChild(renderer.domElement);
const volumeRenderingCapabilities = qualifyVolumeRenderingCapabilities(renderer);
state.volumeRendering = {
  capabilities: volumeRenderingCapabilities,
  descriptor: null,
  textureResource: null,
  transferPresetId: null,
  transferBasePresetId: null,
  transferCustomized: false,
  renderingMode: "dvr",
  transferWindowCenter: null,
  transferWindowWidth: null,
  transferRangeLow: null,
  transferRangeHigh: null,
  transferDensityMultiplier: 1,
  opacitySoftness: null,
  edgeDefinition: null,
  shadingStrength: null,
  slicePlane: "axial",
  slabThicknessMm: 10,
  slabThicknessPreset: "10",
  slabProjection: "mip",
};
const volumeTextureManager = new PatientVolumeTextureManager({
  three: THREE,
  initializeTexture: (texture) => renderer.initTexture(texture),
});
const volumeRayMarcher = new PatientVolumeRayMarcher({ three: THREE });
function syncDirectCtRegionControls() {
  const state = volumeSurfaceLayer?.current?.regionVisibility;
  const enabled = Boolean(state?.available);
  volumeSurfaceRegionMode.disabled = !enabled;
  volumeSurfaceRegionMode.value = enabled ? state.mode : "all";
  if (!volumeSurfaceLayer?.current) {
    volumeSurfaceRegionStatus.textContent = "Build a Direct CT surface to inspect regions.";
  } else if (enabled) {
    volumeSurfaceRegionStatus.textContent = "Regions are unlabeled; inspect before hiding. Full geometry restores every triangle.";
  } else {
    volumeSurfaceRegionStatus.textContent = "Region separation is unavailable for this surface; full geometry remains visible.";
  }
}

volumeSurfaceLayer = new PatientVolumeSurfaceLayer({
  three: THREE,
  parent: anatomyGroup,
  requestRender: requestViewerRender,
  readVolumePresentation: () => volumeRayMarcher.current?.presentation || null,
  onStatusChange: (surfaceStatus) => {
    volumeSurfacePanel.dataset.state = surfaceStatus.state;
    volumeSurfaceStatus.textContent = surfaceStatus.message;
    const busy = surfaceStatus.state === "loading";
    const available = Boolean(state.volumeSurface.descriptor?.available);
    volumeSurfaceBuild.disabled = busy || !available;
    volumeSurfaceIsovalue.disabled = busy || !available;
    volumeSurfaceClear.disabled = busy || !volumeSurfaceLayer?.current;
    syncDirectCtRegionControls();
    syncReconstructionVisualizationResources();
  },
});
segmentationSurfaceLayer = new PatientSegmentationSurfaceLayer({
  three: THREE,
  parent: anatomyGroup,
  requestRender: requestViewerRender,
  readVolumePresentation: () => volumeRayMarcher.current?.presentation || null,
  onStatusChange: (surfaceStatus) => {
    segmentationSurfacePanel.dataset.state = surfaceStatus.state;
    segmentationSurfaceStatus.textContent = surfaceStatus.message;
    segmentationSurfaceStatus.setAttribute("aria-live", surfaceStatus.state === "loading" ? "polite" : "off");
    segmentationStructurePanel.setSurfaceStatusSnapshot(surfaceStatus);
    syncReconstructionVisualizationResources();
    segmentationSurfaceGate?.notify(surfaceStatus);
  },
});
reconstructionVisualizationController = new ReconstructionVisualizationModeController({
  onChange: (snapshot) => applyReconstructionVisualizationSnapshot(snapshot),
});
applyReconstructionVisualizationSnapshot(reconstructionVisualizationController.snapshot());
automaticSurfaceMode = new AutomaticSurfaceModeCoordinator({
  requestMode: (modeId) => reconstructionVisualizationController.requestMode(modeId),
  canActivate: (modeId) => {
    const snapshot = reconstructionVisualizationController.snapshot();
    return modeId === "surface" ? snapshot.canSurface : snapshot.canCombined;
  },
  ensureSurface: () => ensureAutomaticSelectedSurface(),
  onPending: (modeId) => {
    autoSurfacePendingMode = modeId;
    applyReconstructionVisualizationSnapshot(reconstructionVisualizationController.snapshot());
  },
  onFailure: () => {
    // Surface layers retain their actionable errors; no implicit segmentation retry.
  },
});
segmentationSurfaceGate = new ExistingSegmentationSurfaceGate({
  readIdentity: () => canPrepareAutomaticSegmentationSurface()
    ? `${state.study.study_id}/${state.segmentationSurface.descriptor.label_map_id}` : null,
  hasResident: () => hasSelectedResidentSegmentationSurface(),
  hasDesiredStructures: () => Boolean(segmentationSurfaceLayer?.desiredLabels?.size),
  startSurface: () => syncSegmentationSurface(),
});
reconstructionPresentationProfileController = new ReconstructionPresentationProfileController({
  onChange: (snapshot) => applyReconstructionPresentationProfileSnapshot(snapshot),
});
// Presentation is the normal UI intent. The internal Fidelity profile and
// scientific reference settings remain available for qualification workflows.
reconstructionPresentationProfileController.requestProfile("presentation");
const sampleStudyCatalogClient = new SampleStudyCatalogClient();
let sampleReplacementResolver = null;
let sampleCatalogLoading = false;

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.enableRotate = true;
controls.enablePan = true;
controls.enableZoom = true;
controls.rotateSpeed = 0.68;
controls.panSpeed = 0.72;
controls.zoomSpeed = 0.88;
controls.screenSpacePanning = true;
controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
controls.touches.ONE = THREE.TOUCH.ROTATE;
controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;

function updateRenderingQualityStatus(quality) {
  if (!renderQualityStatus) return;
  if (quality.mode === "inactive") {
    renderQualityStatus.dataset.mode = "inactive";
    renderQualityStatus.textContent = "Rendering quality: waiting for patient volume";
    return;
  }
  renderQualityStatus.dataset.mode = quality.mode;
  const mode = quality.mode === "interactive" ? "Interactive" : "Settled";
  const policy = quality.policy
    ? `${quality.policy.charAt(0).toUpperCase()}${quality.policy.slice(1)}`
    : "Balanced";
  renderQualityStatus.textContent = (
    `Rendering quality: ${policy} / ${mode} · ${quality.samplingRate} samples · `
    + `${quality.pixelRatio.toFixed(2)}x pixel ratio`
  );
}

const volumeRenderingQuality = new AdaptiveVolumeRenderingQuality({
  renderer,
  rayMarcher: volumeRayMarcher,
  devicePixelRatio: window.devicePixelRatio || 1,
  requestRender: requestViewerRender,
  onStateChange: updateRenderingQualityStatus,
  policy: renderQualityPolicy?.value || "balanced",
});

controls.addEventListener("start", () => {
  volumeRenderingQuality.beginInteraction("orbit");
});
controls.addEventListener("end", () => {
  volumeRenderingQuality.endInteraction("orbit");
});
controls.addEventListener("change", requestViewerRender);

const qualification = installRenderingQualification({
  window, renderer,
  readSnapshot: () => {
    const current = volumeRayMarcher.current;
    const quality = volumeRenderingQuality.snapshot();
    return {
      modality: current?.descriptor.source_modality,
      dimensions: current?.descriptor.texture_dimensions,
      ready: volumeLayer.available && Boolean(current),
      mode: current?.renderingModeState.current.id,
      qualityPolicy: quality.policy, samplingRate: quality.samplingRate,
      pixelRatio: renderer.getPixelRatio(),
      canvasWidth: renderer.domElement.width, canvasHeight: renderer.domElement.height,
      geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures,
      programs: renderer.info.programs?.length,
      shaderErrors: renderer.info.programs?.filter((program) => program.diagnostics?.runnable === false).length,
      overlayNodes: document.querySelectorAll('.mpr-clipping-overlay, .mpr-clipping-overlay > *, .mpr-clipping-status').length,
      contextLost: renderer.getContext().isContextLost(),
    };
  },
});

function setStatus(kind, message) {
  modelStatus.dataset.state = kind;
  statusText.textContent = message;
}

function setTransferControlsEnabled(enabled) {
  const available = Boolean(enabled);
  volumeRenderingPanel.dataset.state = available ? "ready" : "unavailable";
  for (const control of [
    transferPresetSelect,
    renderingModeSelect,
    transferWindowCenter,
    transferWindowWidth,
    transferRangeLow,
    transferRangeHigh,
    transferDensity,
    transferOpacitySoftness,
    transferEdgeDefinition,
    transferShadingStrength,
    renderQualityPolicy,
    transferResetButton,
  ]) {
    control.disabled = !available;
  }
  const mode = volumeRayMarcher.current?.renderingModeState.current;
  setDvrOnlyControlsEnabled(available && mode?.usesDvrControls === true);
  setIntensityIntervalControlsEnabled(available && mode?.id !== "slice");
  setSliceRenderingControlsEnabled(available && mode?.usesPlaneControls === true, mode);
}

function setDvrOnlyControlsEnabled(enabled) {
  const available = Boolean(enabled);
  for (const control of dvrOnlyControls) {
    control.disabled = !available;
  }
}

function setIntensityIntervalControlsEnabled(enabled) {
  for (const control of intensityIntervalControls) {
    control.disabled = !enabled;
  }
}

function setSliceRenderingControlsEnabled(enabled, mode = null) {
  const available = Boolean(enabled && state.mpr.descriptor);
  slicePlaneSelect.disabled = !available;
  slicePosition.disabled = !available;
  const slabAvailable = available && mode?.usesSlabControls === true;
  slabProjectionSelect.disabled = !slabAvailable;
  slabThicknessSelect.disabled = !slabAvailable;
  slabCustomThickness.disabled = !slabAvailable || slabThicknessSelect.value !== "custom";
  sliceRenderingControls.dataset.state = available ? "ready" : "unavailable";
}

function clearTransferControls() {
  state.volumeRendering.transferPresetId = null;
  state.volumeRendering.transferBasePresetId = null;
  state.volumeRendering.transferCustomized = false;
  state.volumeRendering.renderingMode = "dvr";
  state.volumeRendering.transferWindowCenter = null;
  state.volumeRendering.transferWindowWidth = null;
  state.volumeRendering.transferRangeLow = null;
  state.volumeRendering.transferRangeHigh = null;
  state.volumeRendering.transferDensityMultiplier = 1;
  state.volumeRendering.opacitySoftness = null;
  state.volumeRendering.edgeDefinition = null;
  state.volumeRendering.shadingStrength = null;
  state.volumeRendering.slicePlane = "axial";
  state.volumeRendering.slabThicknessMm = 10;
  state.volumeRendering.slabThicknessPreset = "10";
  state.volumeRendering.slabProjection = "mip";
  transferPresetSelect.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Load a patient volume";
  transferPresetSelect.appendChild(placeholder);
  renderingModeSelect.value = "dvr";
  volumeRenderingPanel.dataset.renderingMode = "dvr";
  renderingModeNote.textContent = (
    "DVR compositing accumulates color and opacity through the patient volume."
  );
  slicePlaneSelect.value = "axial";
  slicePositionValue.textContent = "Z: --";
  slabProjectionSelect.value = "mip";
  slabThicknessSelect.value = "10";
  slabCustomThickness.value = "10";
  slabCustomThicknessValue.textContent = "10.0 mm";
  slabCustomThicknessControl.hidden = true;
  transferModality.textContent = "--";
  transferWindowCenterLabel.textContent = "Window level";
  transferWindowCenterValue.textContent = "--";
  transferWindowWidthValue.textContent = "--";
  transferRangeLowValue.textContent = "--";
  transferRangeHighValue.textContent = "--";
  transferIntensityRange.style.setProperty("--intensity-start-percent", "0%");
  transferIntensityRange.style.setProperty("--intensity-end-percent", "100%");
  transferDensity.value = "100";
  transferDensityValue.textContent = "100%";
  transferOpacitySoftness.value = "30";
  transferOpacitySoftnessValue.textContent = "30%";
  transferEdgeDefinition.value = "25";
  transferEdgeDefinitionValue.textContent = "25%";
  transferShadingStrength.value = "35";
  transferShadingStrengthValue.textContent = "35%";
  transferFunctionNote.textContent = (
    "Medical transfer controls activate with a qualified patient volume."
  );
  setTransferControlsEnabled(false);
}

function transferIntensityStep(transfer) {
  if (transfer.units === "HU") return 1;
  const span = transfer.sourceRange[1] - transfer.sourceRange[0];
  return Math.max(span / 1000, 0.001);
}

function formatTransferIntensity(value, transfer) {
  if (transfer.units === "HU") return `${Math.round(value)} HU`;
  const span = transfer.sourceRange[1] - transfer.sourceRange[0];
  const digits = span >= 100 ? 0 : span >= 10 ? 1 : 2;
  return `${Number(value).toFixed(digits)} rel`;
}

function syncIntensityRangeTrack(transfer) {
  const [sourceLow, sourceHigh] = transfer.sourceRange;
  const span = sourceHigh - sourceLow;
  const minimumPercent = span > 0
    ? clamp(((transfer.rangeLow - sourceLow) / span) * 100, 0, 100)
    : 0;
  const maximumPercent = span > 0
    ? clamp(((transfer.rangeHigh - sourceLow) / span) * 100, 0, 100)
    : 100;
  transferIntensityRange.style.setProperty(
    "--intensity-start-percent",
    `${minimumPercent}%`,
  );
  transferIntensityRange.style.setProperty(
    "--intensity-end-percent",
    `${maximumPercent}%`,
  );
}

function syncTransferControls(transfer) {
  const step = transferIntensityStep(transfer);
  const [sourceLow, sourceHigh] = transfer.sourceRange;
  const minimumInterval = Math.max(step, 0.000001);
  state.volumeRendering.transferPresetId = transfer.id;
  state.volumeRendering.transferBasePresetId = transfer.id;
  state.volumeRendering.transferCustomized = false;
  state.volumeRendering.transferWindowCenter = transfer.windowCenter;
  state.volumeRendering.transferWindowWidth = transfer.windowWidth;
  state.volumeRendering.transferRangeLow = transfer.rangeLow;
  state.volumeRendering.transferRangeHigh = transfer.rangeHigh;
  state.volumeRendering.transferDensityMultiplier = transfer.densityMultiplier;
  state.volumeRendering.opacitySoftness = transfer.opacitySoftness;
  state.volumeRendering.edgeDefinition = transfer.edgeDefinition;
  state.volumeRendering.shadingStrength = transfer.shadingStrength;

  transferPresetSelect.value = transfer.id;
  transferWindowCenter.min = String(sourceLow);
  transferWindowCenter.max = String(sourceHigh);
  transferWindowCenter.step = String(step);
  transferWindowCenter.value = String(transfer.windowCenter);
  transferWindowWidth.min = String(minimumInterval);
  transferWindowWidth.max = String((sourceHigh - sourceLow) * 2);
  transferWindowWidth.step = String(step);
  transferWindowWidth.value = String(transfer.windowWidth);
  transferRangeLow.min = String(sourceLow);
  transferRangeLow.max = String(sourceHigh);
  transferRangeLow.step = String(step);
  transferRangeLow.value = String(transfer.rangeLow);
  transferRangeHigh.min = String(sourceLow);
  transferRangeHigh.max = String(sourceHigh);
  transferRangeHigh.step = String(step);
  transferRangeHigh.value = String(transfer.rangeHigh);
  syncIntensityRangeTrack(transfer);
  transferDensity.value = String(Math.round(transfer.densityMultiplier * 100));
  transferOpacitySoftness.value = String(Math.round(transfer.opacitySoftness * 100));
  transferEdgeDefinition.value = String(Math.round(transfer.edgeDefinition * 100));
  transferShadingStrength.value = String(Math.round(transfer.shadingStrength * 100));

  const displayUnits = transfer.units === "HU" ? "HU" : "relative";
  transferModality.textContent = `${transfer.modality} · ${displayUnits}`;
  transferWindowCenterLabel.textContent = transfer.units === "HU"
    ? "Window level"
    : "Window center";
  transferWindowCenterValue.textContent = formatTransferIntensity(
    transfer.windowCenter,
    transfer,
  );
  transferWindowWidthValue.textContent = formatTransferIntensity(
    transfer.windowWidth,
    transfer,
  );
  transferRangeLowValue.textContent = formatTransferIntensity(transfer.rangeLow, transfer);
  transferRangeHighValue.textContent = formatTransferIntensity(transfer.rangeHigh, transfer);
  transferDensityValue.textContent = `${Math.round(transfer.densityMultiplier * 100)}%`;
  transferOpacitySoftnessValue.textContent = `${Math.round(transfer.opacitySoftness * 100)}%`;
  transferEdgeDefinitionValue.textContent = `${Math.round(transfer.edgeDefinition * 100)}%`;
  transferShadingStrengthValue.textContent = `${Math.round(transfer.shadingStrength * 100)}%`;
  transferFunctionNote.textContent = transfer.description;
}

function configureTransferControls(volumeResource) {
  const presets = listMedicalTransferPresets(volumeResource.descriptor);
  transferPresetSelect.replaceChildren();
  for (const preset of presets) {
    const option = document.createElement("option");
    option.value = preset.id;
    option.textContent = preset.label;
    transferPresetSelect.appendChild(option);
  }
  const option = document.createElement("option");
  option.value = "custom";
  option.textContent = "Custom";
  option.disabled = true;
  transferPresetSelect.appendChild(option);
  renderingModeSelect.replaceChildren();
  for (const mode of listMedicalRenderingModes()) {
    const modeOption = document.createElement("option");
    modeOption.value = mode.id;
    modeOption.textContent = mode.label;
    renderingModeSelect.appendChild(modeOption);
  }
  syncTransferControls(volumeResource.transferState.current);
  setMedicalRenderingMode(volumeResource.renderingModeState.current.id);
  setTransferControlsEnabled(true);
}

function setMedicalRenderingMode(modeId = renderingModeSelect.value) {
  if (!volumeRayMarcher.current) return null;
  const mode = volumeRayMarcher.setRenderingMode(modeId);
  state.volumeRendering.renderingMode = mode.id;
  volumeRenderingPanel.dataset.renderingMode = mode.id;
  renderingModeSelect.value = mode.id;
  if (mode.id === "slice") {
    renderingModeNote.textContent = (
      `${mode.description} Position follows the synchronized MPR crosshair.`
    );
  } else if (mode.id === "thick-slab") {
    renderingModeNote.textContent = (
      `${mode.description} Thickness is measured in Patient LPS millimetres.`
    );
  } else {
    renderingModeNote.textContent = mode.usesDvrControls
      ? mode.description
      : `${mode.description} Projection modes aggregate real patient voxels in the selected intensity interval before window/level.`;
  }
  setDvrOnlyControlsEnabled(mode.usesDvrControls);
  setIntensityIntervalControlsEnabled(mode.id !== "slice");
  setSliceRenderingControlsEnabled(mode.usesPlaneControls, mode);
  if (mode.usesPlaneControls) syncSliceRenderingControlsFromMpr();
  modelChip.textContent = `Patient scan - ${mode.label}`;
  requestViewerRender();
  return mode;
}

function selectedSlabThicknessMm() {
  return slabThicknessSelect.value === "custom"
    ? Number(slabCustomThickness.value)
    : Number(slabThicknessSelect.value);
}

function syncSliceRenderingControlsFromMpr() {
  const descriptor = state.mpr.descriptor;
  const resource = volumeRayMarcher.current;
  const plane = state.volumeRendering.slicePlane;
  const planeDescriptor = descriptor?.planes?.[plane];
  if (!descriptor || !resource || !planeDescriptor) {
    slicePositionValue.textContent = "--";
    setSliceRenderingControlsEnabled(false);
    return null;
  }

  const axisIndex = MPR_AXIS_INDEX[planeDescriptor.normal_axis];
  const [minimum, maximum] = planeDescriptor.position_range_mm.map(Number);
  const sampleSpacingMm = Math.max(Number(planeDescriptor.slice_spacing_mm), 0.01);
  const positionLpsMm = clamp(
    Number(state.mpr.crosshairLpsMm[axisIndex]),
    minimum,
    maximum,
  );
  state.mpr.crosshairLpsMm[axisIndex] = positionLpsMm;
  slicePlaneSelect.value = plane;
  slicePosition.min = String(minimum);
  slicePosition.max = String(maximum);
  slicePosition.step = String(sampleSpacingMm);
  slicePosition.value = String(positionLpsMm);
  slicePositionValue.textContent = `${planeDescriptor.coordinate}: ${positionLpsMm.toFixed(2)} mm`;

  const maximumThicknessMm = Math.max(sampleSpacingMm, maximum - minimum);
  const slabThicknessMm = clamp(
    Number(state.volumeRendering.slabThicknessMm),
    Math.min(0.1, maximumThicknessMm),
    maximumThicknessMm,
  );
  state.volumeRendering.slabThicknessMm = slabThicknessMm;
  slabCustomThickness.min = String(Math.min(0.1, maximumThicknessMm));
  slabCustomThickness.max = String(maximumThicknessMm);
  slabCustomThickness.step = String(Math.min(sampleSpacingMm, 0.1));
  slabCustomThickness.value = String(slabThicknessMm);
  slabCustomThicknessValue.textContent = `${slabThicknessMm.toFixed(1)} mm`;
  const presetThickness = Number(state.volumeRendering.slabThicknessPreset);
  const presetIsAvailable = state.volumeRendering.slabThicknessPreset !== "custom"
    && Number.isFinite(presetThickness)
    && Math.abs(presetThickness - slabThicknessMm) < 0.0001;
  slabThicknessSelect.value = presetIsAvailable
    ? state.volumeRendering.slabThicknessPreset
    : "custom";
  if (!presetIsAvailable) state.volumeRendering.slabThicknessPreset = "custom";
  slabCustomThicknessControl.hidden = slabThicknessSelect.value !== "custom";
  slabProjectionSelect.value = state.volumeRendering.slabProjection;

  const settings = volumeRayMarcher.setSliceRendering({
    plane,
    positionLpsMm,
    slabThicknessMm,
    slabProjection: state.volumeRendering.slabProjection,
    sampleSpacingMm,
    patientBoundsLpsMm: descriptor.patient_bounds_lps_mm,
  });
  const mode = resource.renderingModeState.current;
  setSliceRenderingControlsEnabled(mode.usesPlaneControls, mode);
  requestViewerRender();
  return settings;
}

function applyTransferPreset(presetId = transferPresetSelect.value) {
  if (!volumeRayMarcher.current || !presetId || presetId === "custom") return null;
  const transfer = volumeRayMarcher.setTransferPreset(presetId);
  syncTransferControls(transfer);
  requestViewerRender();
  return transfer;
}

function markTransferCustomized() {
  state.volumeRendering.transferCustomized = true;
  transferPresetSelect.value = "custom";
}

function applyTransferAdjustments(changedControl = null) {
  if (!volumeRayMarcher.current || !state.volumeRendering.transferBasePresetId) return null;
  const current = volumeRayMarcher.current.transferState.current;
  const [sourceLow, sourceHigh] = current.sourceRange;
  const changedBoundary = changedControl === transferRangeLow ? "minimum" : "maximum";
  const interval = constrainMedicalIntensityInterval(
    [sourceLow, sourceHigh],
    Number(transferRangeLow.value),
    Number(transferRangeHigh.value),
    changedBoundary,
  );
  const rangeLow = interval.minimum;
  const rangeHigh = interval.maximum;

  const transfer = volumeRayMarcher.setTransferPreset(
    state.volumeRendering.transferBasePresetId,
    {
      windowCenter: Number(transferWindowCenter.value),
      windowWidth: Number(transferWindowWidth.value),
      rangeLow,
      rangeHigh,
      densityMultiplier: Number(transferDensity.value) / 100,
      opacitySoftness: Number(transferOpacitySoftness.value) / 100,
      edgeDefinition: Number(transferEdgeDefinition.value) / 100,
      shadingStrength: Number(transferShadingStrength.value) / 100,
    },
  );
  syncTransferControls(transfer);
  markTransferCustomized();
  requestViewerRender();
  return transfer;
}

function reconstructionSurfaceSourceLabel(sourceId) {
  return sourceId === "volume-derived" ? "Direct CT" : "Segmentation";
}

function applyCombinedPresentationBalance(visualizationSnapshot = null, profileSnapshot = null) {
  const visualization = visualizationSnapshot || reconstructionVisualizationController?.snapshot();
  const presentation = profileSnapshot || reconstructionPresentationProfileController?.snapshot();
  const plan = resolveCombinedPresentationBalance({
    mode: visualization?.mode || "volume",
    profile: presentation?.profile || "fidelity",
    userVolumeOpacity: state.opacity,
    directCtSurfaceVisible: Boolean(visualization?.visibility?.surfaceSources?.["volume-derived"]),
    segmentationSurfaceVisible: Boolean(visualization?.visibility?.surfaceSources?.["segmentation-derived"]),
  });
  volumeRayMarcher.setOpacity(plan.effectiveVolumeOpacity);
  volumeSurfaceLayer?.setPresentationOpacity(plan.directCtSurfaceOpacity);
  if (reconstructionVisualizationPanel) {
    reconstructionVisualizationPanel.dataset.combinedBalance = plan.active ? "active" : "inactive";
  }
  return plan;
}

function applyReconstructionPresentationProfileSnapshot(snapshot) {
  if (!snapshot) return;
  surfaceLightingRig.setProfile(snapshot.profile);
  volumeSurfaceLayer?.setPresentationProfile(snapshot.profile);
  segmentationSurfaceLayer?.setPresentationProfile(snapshot.profile);
  if (reconstructionVisualizationPanel) {
    reconstructionVisualizationPanel.dataset.presentationProfile = snapshot.profile;
  }
  for (const button of reconstructionPresentationProfileButtons) {
    const profileId = button.dataset.reconstructionPresentationProfile;
    const active = snapshot.profile === profileId;
    button.dataset.active = String(active);
    button.setAttribute("aria-pressed", String(active));
  }
  if (reconstructionPresentationProfileStatus) {
    reconstructionPresentationProfileStatus.textContent = `${snapshot.label} · ${snapshot.description}`;
  }
  applyCombinedPresentationBalance(null, snapshot);
}

function requestReconstructionPresentationProfile(profileId) {
  if (!reconstructionPresentationProfileController) return null;
  return reconstructionPresentationProfileController.requestProfile(profileId);
}

function canPrepareAutomaticDirectCtSurface(snapshot) {
  const descriptor = state.volumeSurface.descriptor;
  return Boolean(
    snapshot.volumeAvailable
    && state.study?.study_id
    && descriptor?.available
    && descriptor.study_id === state.study.study_id
    && state.reconstructionVisualization.surfaceSourceSelection["volume-derived"]
  );
}

function hasSelectedResidentSegmentationSurface() {
  const layer = segmentationSurfaceLayer;
  if (!layer?.descriptor?.label_map_id || !layer.desiredLabels?.size) return false;
  if (layer.descriptor.label_map_id !== state.segmentationSurface.descriptor?.label_map_id) return false;
  return Array.from(layer.desiredLabels).some((labelId) => layer.items.has(labelId));
}

function canPrepareAutomaticSegmentationSurface() {
  return Boolean(
    volumeLayer.available
    && volumeRayMarcher.current
    && state.segmentationSurface.descriptor?.ready
    && state.segmentationSurface.descriptor?.source_study_id === state.study?.study_id
    && state.segmentationSurface.descriptor?.label_map_id === activeSegmentationLabelMapId
    && state.segmentationOverlay.presentation?.structures instanceof Map
    && state.segmentationSurface.enabled
    && state.reconstructionVisualization.surfaceSourceSelection["segmentation-derived"]
    && segmentationSurfaceLayer.desiredLabels.size > 0
  );
}

function applyReconstructionVisualizationSnapshot(snapshot) {
  if (!snapshot) return;
  if (volumeLayer.root) {
    volumeLayer.root.visible = Boolean(snapshot.visibility.volume) && state.opacity > 0.001;
  }
  const surfaceSemanticOverlayActive = Boolean(
    snapshot.mode === "surface"
    && snapshot.visibility.surfaceSources["volume-derived"]
    && snapshot.visibility.surfaceSources["segmentation-derived"]
  );
  volumeSurfaceLayer?.setSemanticOverlayActive(surfaceSemanticOverlayActive);
  volumeSurfaceLayer?.setPresentationVisible(snapshot.visibility.surfaceSources["volume-derived"]);
  segmentationSurfaceLayer?.setPresentationVisible(snapshot.visibility.surfaceSources["segmentation-derived"]);

  if (reconstructionVisualizationPanel) {
    reconstructionVisualizationPanel.dataset.mode = snapshot.mode;
    reconstructionVisualizationPanel.dataset.state = snapshot.volumeAvailable || snapshot.canSurface
      ? "ready"
      : "unavailable";
  }
  const canPrepareDirectCt = canPrepareAutomaticDirectCtSurface(snapshot);
  const canPrepareSegmentation = canPrepareAutomaticSegmentationSurface();
  const preparatory = canPrepareDirectCt || canPrepareSegmentation;
  const pendingSource = canPrepareDirectCt ? "Direct CT" : "selected segmentation";
  for (const button of reconstructionModeButtons) {
    const modeId = button.dataset.reconstructionMode;
    const available = modeId === "volume"
      ? snapshot.canVolume
      : (modeId === "surface"
        ? snapshot.canSurface || preparatory
        : snapshot.canCombined || (snapshot.canVolume && preparatory));
    button.disabled = !available;
    button.dataset.active = String(snapshot.mode === modeId && available);
    button.dataset.capability = available ? "ready" : "unavailable";
    button.dataset.pending = String(autoSurfacePendingMode === modeId);
    button.setAttribute("aria-pressed", String(snapshot.mode === modeId && available));
  }
  const selectedResidentLabels = snapshot.selectedResidentSurfaceSources.map(reconstructionSurfaceSourceLabel);
  const sourceSummary = selectedResidentLabels.join(" + ");
  if (surfaceModeStatusText) {
    surfaceModeStatusText.textContent = autoSurfacePendingMode === "surface"
      ? `Preparing ${pendingSource} surface…`
      : (snapshot.canSurface ? `${sourceSummary || "Surface"} ready`
        : (preparatory ? (canPrepareDirectCt ? "Select to prepare Direct CT" : "Select to prepare selected segmentation") : "Select a surface source"));
  }
  if (combinedModeStatusText) {
    combinedModeStatusText.textContent = autoSurfacePendingMode === "combined"
      ? `Preparing ${pendingSource} surface…`
      : (snapshot.canCombined ? "Volume + selected surface ready"
        : (snapshot.canVolume && preparatory ? `Select to prepare volume + ${pendingSource}` : "Requires volume + surface"));
  }
  for (const input of reconstructionSurfaceSourceInputs) {
    const sourceId = input.dataset.reconstructionSurfaceSource;
    const sourceState = snapshot.surfaceSources[sourceId];
    const semanticEnabled = sourceId !== "segmentation-derived" || state.segmentationSurface.enabled;
    const directCtPreparatory = sourceId === "volume-derived" && Boolean(
      snapshot.volumeAvailable && state.volumeSurface.descriptor?.available
      && state.volumeSurface.descriptor.study_id === state.study?.study_id
    );
    const segmentationPreparatory = sourceId === "segmentation-derived" && Boolean(
      state.segmentationSurface.descriptor?.ready
      && state.segmentationSurface.descriptor?.source_study_id === state.study?.study_id
      && state.segmentationSurface.descriptor?.label_map_id === activeSegmentationLabelMapId
    );
    const selectable = Boolean(semanticEnabled && (sourceState?.resident || directCtPreparatory || segmentationPreparatory));
    input.disabled = !selectable;
    input.checked = Boolean(selectable && state.reconstructionVisualization.surfaceSourceSelection[sourceId]);
    const row = input.closest("[data-reconstruction-source-row]");
    if (row) {
      row.dataset.state = !selectable ? "unavailable" : (input.checked ? "selected" : "ready");
    }
  }
  if (reconstructionVisualizationStatus) {
    if (!snapshot.volumeAvailable && !snapshot.canSurface) {
      reconstructionVisualizationStatus.textContent = "Available after a patient volume or resident surface is ready.";
    } else if (snapshot.mode === "combined") {
      reconstructionVisualizationStatus.textContent = `Combined view · balanced patient volume + ${sourceSummary} · semantic surface colors preserved.`;
    } else if (snapshot.mode === "surface") {
      reconstructionVisualizationStatus.textContent = `Surface view · ${sourceSummary} · resident geometry reused without rebuilding.`;
    } else {
      reconstructionVisualizationStatus.textContent = snapshot.canSurface
        ? "Volume view · resident surface sources are ready for Surface or Combined."
        : (preparatory
          ? `Volume view · choose Surface or Combined to prepare the selected ${pendingSource} surface.`
          : "Volume view · select an available surface source to enable Surface and Combined.");
    }
  }
  applyCombinedPresentationBalance(snapshot, null);
  requestViewerRender();
}

function syncReconstructionVisualizationResources() {
  if (!reconstructionVisualizationController) return null;
  const volumeAvailable = Boolean(volumeLayer.available && volumeLayer.root);
  const volumeDerivedResident = Boolean(volumeSurfaceLayer?.current);
  const segmentationDerivedResident = hasSelectedResidentSegmentationSurface();
  const sourceSelection = state.reconstructionVisualization.surfaceSourceSelection;

  reconstructionVisualizationController.setVolumeAvailable(volumeAvailable);
  reconstructionVisualizationController.setSurfaceSource("volume-derived", {
    available: Boolean(state.volumeSurface.descriptor?.available),
    resident: volumeDerivedResident,
    selected: volumeDerivedResident && Boolean(sourceSelection["volume-derived"]),
  });
  reconstructionVisualizationController.setSurfaceSource("segmentation-derived", {
    available: Boolean(state.segmentationSurface.descriptor?.ready),
    resident: segmentationDerivedResident,
    selected: segmentationDerivedResident
      && state.segmentationSurface.enabled
      && Boolean(sourceSelection["segmentation-derived"]),
  });
  return reconstructionVisualizationController.snapshot();
}

function requestReconstructionVisualizationMode(modeId) {
  if (!reconstructionVisualizationController) return null;
  const snapshot = reconstructionVisualizationController.snapshot();
  if (modeId === "volume" || (modeId === "surface" ? snapshot.canSurface : snapshot.canCombined)) {
    automaticSurfaceMode?.invalidate();
    segmentationSurfaceGate?.invalidate();
    const result = reconstructionVisualizationController.requestMode(modeId);
    // A resident segmentation surface can be shown immediately; prepare the
    // separately selected Direct CT source in the background without replacing it.
    if (result.accepted && modeId !== "volume" && !volumeSurfaceLayer.current
        && canPrepareAutomaticDirectCtSurface(snapshot)) {
      void ensureAutomaticDirectCtSurface();
    }
    if (result.accepted && modeId !== "volume" && canPrepareAutomaticSegmentationSurface()) {
      void syncSegmentationSurface();
    }
    return result;
  }
  return automaticSurfaceMode.request(modeId);
}

function ensureAutomaticSelectedSurface() {
  const snapshot = reconstructionVisualizationController.snapshot();
  if (canPrepareAutomaticDirectCtSurface(snapshot)) {
    const build = ensureAutomaticDirectCtSurface();
    if (!build) return null;
    return Promise.resolve(build).then((ready) => {
      if (ready || reconstructionVisualizationController.snapshot().canSurface) return true;
      return canPrepareAutomaticSegmentationSurface()
        ? ensureAutomaticSegmentationSurface() : false;
    });
  }
  if (canPrepareAutomaticSegmentationSurface()) return ensureAutomaticSegmentationSurface();
  return null;
}

function ensureAutomaticSegmentationSurface() {
  if (!canPrepareAutomaticSegmentationSurface()) return null;
  return segmentationSurfaceGate?.request() || null;
}

function ensureAutomaticDirectCtSurface() {
  const snapshot = reconstructionVisualizationController.snapshot();
  if (!canPrepareAutomaticDirectCtSurface(snapshot)) return null;
  const studyId = state.study.study_id;
  const requestedLevel = Number(volumeSurfaceIsovalue.value);
  if (volumeSurfaceLayer.current?.isovalue === requestedLevel) return Promise.resolve(true);
  if (autoSurfaceBuildPromise && autoSurfaceBuildStudyId === studyId) return autoSurfaceBuildPromise;
  autoSurfaceBuildStudyId = studyId;
  const buildPromise = requestVolumeSurfaceBuild().then((built) => (
    Boolean(built && state.study?.study_id === studyId && volumeSurfaceLayer.current === built)
  ));
  autoSurfaceBuildPromise = buildPromise;
  void buildPromise.finally(() => {
    if (autoSurfaceBuildPromise === buildPromise) {
      autoSurfaceBuildPromise = null;
      autoSurfaceBuildStudyId = null;
    }
  });
  return buildPromise;
}

function requestReconstructionSurfaceSourceSelection(sourceId, selected) {
  if (!reconstructionVisualizationController) return null;
  const selection = state.reconstructionVisualization.surfaceSourceSelection;
  if (!Object.hasOwn(selection, sourceId)) return null;
  selection[sourceId] = Boolean(selected);
  const snapshot = reconstructionVisualizationController.snapshot();
  const sourceState = snapshot.surfaceSources[sourceId];
  const semanticEnabled = sourceId !== "segmentation-derived" || state.segmentationSurface.enabled;
  const effectiveSelection = Boolean(selected && sourceState?.resident && semanticEnabled);
  if (sourceId === "segmentation-derived" && !selected) segmentationSurfaceGate?.invalidate();
  const result = reconstructionVisualizationController.selectSurfaceSource(sourceId, effectiveSelection);
  if (sourceId === "segmentation-derived" && selected && canPrepareAutomaticSegmentationSurface()) {
    void syncSegmentationSurface();
  }
  return result;
}

function setVolumeAvailability(available) {
  volumeLayer.available = Boolean(available);
  modelChip.textContent = "Patient scan - Full Volume";
  const mode = volumeRayMarcher.current?.renderingModeState.current;
  if (mode) modelChip.textContent = `Patient scan - ${mode.label}`;
  setClippingControlsEnabled(
    volumeLayer.available
    && Boolean(volumeRayMarcher.current)
    && Boolean(state.mpr.descriptor),
  );
  setTransferControlsEnabled(volumeLayer.available && Boolean(volumeRayMarcher.current));
  syncReconstructionVisualizationResources();
}

function applyVolumeVisibility() {
  if (volumeLayer.root) {
    const snapshot = reconstructionVisualizationController?.snapshot();
    const modeAllowsVolume = snapshot ? snapshot.visibility.volume : true;
    volumeLayer.root.visible = volumeLayer.available && state.opacity > 0.001 && modeAllowsVolume;
    requestViewerRender();
  }
}

function updateVolumeBounds() {
  const root = volumeLayer.root;
  if (!root) return null;
  const box = new THREE.Box3().setFromObject(root);
  box.getSize(state.size);
  return box;
}

function fitCamera(box) {
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const radius = Math.max(sphere.radius, 0.01);
  const offset = new THREE.Vector3(
    radius * 1.30,
    radius * 0.42,
    radius * 2.55,
  );
  offset.multiplyScalar(INITIAL_VIEW_DISTANCE_SCALE);
  const position = sphere.center.clone().add(offset);
  const target = sphere.center.clone();
  target.y += state.size.y * 0.015;

  camera.position.copy(position);
  controls.target.copy(target);
  state.cameraPosition.copy(position);
  state.cameraTarget.copy(target);

  controls.minDistance = radius * 1.15;
  controls.maxDistance = radius * 8;
  camera.near = Math.max(radius / 150, 0.001);
  camera.far = radius * 30;
  camera.updateProjectionMatrix();
  controls.update();
}

function fitSavedView() {
  camera.position.copy(state.cameraPosition);
  controls.target.copy(state.cameraTarget);
  controls.update();
}

function zoomBy(factor) {
  const offset = camera.position.clone().sub(controls.target);
  const currentDistance = Math.max(offset.length(), 0.0001);
  const nextDistance = THREE.MathUtils.clamp(
    currentDistance * factor,
    controls.minDistance || currentDistance * 0.25,
    controls.maxDistance || currentDistance * 4,
  );
  offset.setLength(nextDistance);
  camera.position.copy(controls.target).add(offset);
  controls.update();
}

const GIZMO_CENTER = 48;
const GIZMO_CUBE_SCALE = 15.5;
const GIZMO_AXIS_SCALE = 27;
const GIZMO_LABEL_SCALE = 34;
const GIZMO_CORNERS = [
  new THREE.Vector3(-1, -1, -1),
  new THREE.Vector3(1, -1, -1),
  new THREE.Vector3(1, 1, -1),
  new THREE.Vector3(-1, 1, -1),
  new THREE.Vector3(-1, -1, 1),
  new THREE.Vector3(1, -1, 1),
  new THREE.Vector3(1, 1, 1),
  new THREE.Vector3(-1, 1, 1),
];
const GIZMO_EDGE_PAIRS = [
  [0, 1], [1, 2], [2, 3], [3, 0],
  [4, 5], [5, 6], [6, 7], [7, 4],
  [0, 4], [1, 5], [2, 6], [3, 7],
];
const gizmoInverseCameraQuaternion = new THREE.Quaternion();

function anatomyDirectionInView(localDirection) {
  gizmoInverseCameraQuaternion.copy(camera.quaternion).invert();
  return localDirection
    .clone()
    .applyQuaternion(anatomyGroup.quaternion)
    .applyQuaternion(gizmoInverseCameraQuaternion);
}

function gizmoPoint(localPoint, scale) {
  const view = anatomyDirectionInView(localPoint);
  return {
    x: GIZMO_CENTER + view.x * scale,
    y: GIZMO_CENTER - view.y * scale,
    z: view.z,
  };
}

function setGizmoLine(line, start, end) {
  if (!line) return;
  line.setAttribute("x1", start.x.toFixed(2));
  line.setAttribute("y1", start.y.toFixed(2));
  line.setAttribute("x2", end.x.toFixed(2));
  line.setAttribute("y2", end.y.toFixed(2));
}

function setGizmoLabel(label, point) {
  if (!label) return;
  label.setAttribute("x", point.x.toFixed(2));
  label.setAttribute("y", point.y.toFixed(2));
}

function updateOrientationGizmo() {
  if (!orientationGizmo) return;

  const projectedCorners = GIZMO_CORNERS.map((corner) => gizmoPoint(corner, GIZMO_CUBE_SCALE));
  GIZMO_EDGE_PAIRS.forEach(([from, to], index) => {
    setGizmoLine(gizmoEdges[index], projectedCorners[from], projectedCorners[to]);
  });

  const center = { x: GIZMO_CENTER, y: GIZMO_CENTER };
  const directions = [
    [gizmoAxisS, gizmoLabelS, new THREE.Vector3(0, 1, 0)],
    [gizmoAxisA, gizmoLabelA, new THREE.Vector3(0, 0, 1)],
    [gizmoAxisR, gizmoLabelR, new THREE.Vector3(1, 0, 0)],
    [gizmoAxisL, gizmoLabelL, new THREE.Vector3(-1, 0, 0)],
  ];

  for (const [line, label, direction] of directions) {
    setGizmoLine(line, center, gizmoPoint(direction, GIZMO_AXIS_SCALE));
    setGizmoLabel(label, gizmoPoint(direction, GIZMO_LABEL_SCALE));
  }
}

function clippingPlaneRange(plane) {
  const range = state.mpr.descriptor?.planes?.[plane]?.position_range_mm;
  if (!Array.isArray(range) || range.length !== 2) return null;
  const minimum = Number(range[0]);
  const maximum = Number(range[1]);
  return Number.isFinite(minimum) && Number.isFinite(maximum) && maximum > minimum
    ? [minimum, maximum]
    : null;
}

function clippingRangeIsActive(startPercent, endPercent) {
  // The full 0..100% acquisition range never clips. Both endpoints independently
  // activate the same retained interval when moved inward; no hidden toggle state.
  return Number(startPercent) > 0 || Number(endPercent) < 100;
}

function setClippingControlsEnabled(enabled) {
  const available = Boolean(enabled);
  directionalCutPanel.dataset.clippingState = available ? "ready" : "unavailable";
  clippingResetButton.disabled = !available;
  for (const controlsForPlane of clippingRegistry.values()) {
    // A full-range plane must remain adjustable, otherwise it cannot activate.
    controlsForPlane.start.disabled = !available;
    controlsForPlane.end.disabled = !available;
  }
}

function clippingBoundaryLpsMm(definition, range, percent) {
  const normalized = clamp(Number(percent) / 100, 0, 1);
  const span = range[1] - range[0];
  return definition.reversed
    ? range[1] - normalized * span
    : range[0] + normalized * span;
}

function clippingRequest() {
  return Object.fromEntries(Object.entries(CLIPPING_PLANES).map(([plane, definition]) => [
    plane,
    (() => {
      const range = clippingPlaneRange(plane);
      if (!range) return { enabled: false };
      const startLpsMm = clippingBoundaryLpsMm(definition, range, state.clipping[plane].startPercent);
      const endLpsMm = clippingBoundaryLpsMm(definition, range, state.clipping[plane].endPercent);
      return {
        enabled: clippingRangeIsActive(state.clipping[plane].startPercent, state.clipping[plane].endPercent),
        minimumLpsMm: Math.min(startLpsMm, endLpsMm),
        maximumLpsMm: Math.max(startLpsMm, endLpsMm),
      };
    })(),
  ]));
}

function applyPatientClipping() {
  updateMprClippingOverlays();
  if (!state.mpr.descriptor) return null;
  const request = clippingRequest();
  volumeSurfaceLayer?.setClippingPlanes(request);
  segmentationSurfaceLayer?.setClippingPlanes(request);
  if (!volumeRayMarcher.current) {
    requestViewerRender();
    return request;
  }
  const clipping = volumeRayMarcher.setClippingPlanes(request);
  requestViewerRender();
  return clipping;
}

function syncClippingControlsFromMpr() {
  for (const [plane, definition] of Object.entries(CLIPPING_PLANES)) {
    const controlsForPlane = clippingRegistry.get(plane);
    const range = clippingPlaneRange(plane);
    if (!controlsForPlane) continue;
    const clipping = state.clipping[plane];
    clipping.startPercent = clamp(Number(clipping.startPercent), 0, 100 - CLIPPING_MINIMUM_GAP_PERCENT);
    clipping.endPercent = clamp(
      Number(clipping.endPercent),
      clipping.startPercent + CLIPPING_MINIMUM_GAP_PERCENT,
      100,
    );
    clipping.enabled = clippingRangeIsActive(clipping.startPercent, clipping.endPercent);
    controlsForPlane.status.textContent = clipping.enabled ? "Active" : "Full range";
    controlsForPlane.status.dataset.active = String(clipping.enabled);
    controlsForPlane.range.closest(".clip-plane-control").dataset.clippingActive = String(clipping.enabled);
    if (!range) {
      controlsForPlane.startPosition.textContent = `${definition.coordinate}: --`;
      controlsForPlane.endPosition.textContent = `${definition.coordinate}: --`;
      continue;
    }
    const startLpsMm = clippingBoundaryLpsMm(definition, range, clipping.startPercent);
    const endLpsMm = clippingBoundaryLpsMm(definition, range, clipping.endPercent);
    controlsForPlane.start.value = String(clipping.startPercent);
    controlsForPlane.end.value = String(clipping.endPercent);
    controlsForPlane.startPercent.textContent = `${Number(clipping.startPercent.toFixed(1))}%`;
    controlsForPlane.endPercent.textContent = `${Number(clipping.endPercent.toFixed(1))}%`;
    controlsForPlane.startPosition.textContent = `${definition.coordinate}: ${startLpsMm.toFixed(2)} mm`;
    controlsForPlane.endPosition.textContent = `${definition.coordinate}: ${endLpsMm.toFixed(2)} mm`;
    controlsForPlane.start.setAttribute("aria-valuetext", `${definition.startLabel}: ${startLpsMm.toFixed(2)} mm (${clipping.startPercent}%)`);
    controlsForPlane.end.setAttribute("aria-valuetext", `${definition.endLabel}: ${endLpsMm.toFixed(2)} mm (${clipping.endPercent}%)`);
    controlsForPlane.range.style.setProperty("--clip-start-percent", `${clipping.startPercent}%`);
    controlsForPlane.range.style.setProperty("--clip-end-percent", `${clipping.endPercent}%`);
  }
  setClippingControlsEnabled(
    volumeLayer.available
    && Boolean(volumeRayMarcher.current)
    && Boolean(state.mpr.descriptor),
  );
  const clipping = applyPatientClipping();
  syncSliceRenderingControlsFromMpr();
  return clipping;
}

function updateClippingBoundaryFromControl(plane, boundary) {
  const controlsForPlane = clippingRegistry.get(plane);
  if (!CLIPPING_PLANES[plane] || !controlsForPlane) return;
  const clipping = state.clipping[plane];
  if (boundary === "start") {
    clipping.startPercent = clamp(
      Number(controlsForPlane.start.value),
      0,
      clipping.endPercent - CLIPPING_MINIMUM_GAP_PERCENT,
    );
  } else if (boundary === "end") {
    clipping.endPercent = clamp(
      Number(controlsForPlane.end.value),
      clipping.startPercent + CLIPPING_MINIMUM_GAP_PERCENT,
      100,
    );
  }
  syncClippingControlsFromMpr();
}

function resetPatientClipping() {
  for (const plane of Object.keys(CLIPPING_PLANES)) {
    state.clipping[plane].enabled = false;
    state.clipping[plane].startPercent = 0;
    state.clipping[plane].endPercent = 100;
  }
  syncClippingControlsFromMpr();
}

function applyOpacity() {
  volumeRayMarcher.setOpacity(state.opacity);
  applyCombinedPresentationBalance();
  applyVolumeVisibility();
  opacityValue.textContent = `${Math.round(state.opacity * 100)}%`;
  requestViewerRender();
}

function resetReconstructionVisualizationForStudy() {
  automaticSurfaceMode?.invalidate();
  segmentationSurfaceGate?.invalidate();
  autoSurfaceBuildPromise = null;
  autoSurfaceBuildStudyId = null;
  state.reconstructionVisualization.surfaceSourceSelection = {
    ...DEFAULT_RECONSTRUCTION_SURFACE_SOURCE_SELECTION,
  };
  reconstructionVisualizationController?.reset();
}

function clearPatientVolumeRendering() {
  qualification?.resetWindow();
  volumeRenderingQuality.deactivate();
  volumeRayMarcher.dispose();
  volumeLayer.root = null;
  volumeSurfaceDescriptorPromise = null;
  state.volumeSurface.descriptor = null;
  volumeSurfaceLayer.clear();
  volumeSurfaceBuild.disabled = true;
  volumeSurfaceClear.disabled = true;
  volumeSurfaceIsovalue.disabled = true;
  setSegmentationSurfaceAvailability(null);
  clearTransferControls();
  setVolumeAvailability(false);
  resetReconstructionVisualizationForStudy();
  applyVolumeVisibility();
  setStatus(
    "loading",
    state.study?.volume_ready ? "Preparing patient volume..." : "Upload a DICOM study",
  );
}

async function activatePatientVolumeRendering(textureResource, task) {
  const volumeResource = volumeRayMarcher.create(textureResource);
  const compileScene = new THREE.Scene();
  compileScene.add(volumeResource.root);
  try {
    await renderer.compileAsync(compileScene, camera);
  } finally {
    compileScene.remove(volumeResource.root);
  }
  if (volumeRenderingTask !== task || volumeRayMarcher.current !== volumeResource) {
    throw new DOMException("Patient volume rendering was superseded", "AbortError");
  }

  volumeRenderingQuality.activate(
    volumeResource.descriptor,
    state.volumeRendering.capabilities,
    renderQualityPolicy.value,
  );
  if (state.autoRotate) {
    volumeRenderingQuality.beginInteraction("auto-rotate");
  }

  volumeLayer.root = volumeResource.root;
  anatomyGroup.add(volumeResource.root);
  volumeResource.root.updateMatrixWorld(true);
  configureTransferControls(volumeResource);
  setVolumeAvailability(true);
  syncClippingControlsFromMpr();
  applyOpacity();

  const box = updateVolumeBounds();
  if (box) fitCamera(box);
  requestViewerRender();
  setStatus("ready", "Patient volume rendering ready");
  setWorkflowStep(workflowVisualization, "complete");
  volumeStatusRow.dataset.state = "ready";
  volumeStatusText.textContent = "Patient volume rendered";
  void syncSegmentationSurface();
  return volumeResource;
}

function resetWorkspace() {
  resetPatientClipping();

  state.opacity = DEFAULT_OPACITY;
  opacitySlider.value = String(Math.round(DEFAULT_OPACITY * 100));
  if (state.volumeRendering.transferBasePresetId) {
    applyTransferPreset(state.volumeRendering.transferBasePresetId);
  }
  if (volumeRayMarcher.current) setMedicalRenderingMode("dvr");
  state.autoRotate = false;
  volumeRenderingQuality.endInteraction("auto-rotate");
  autoRotateButton.classList.remove("is-active");
  autoRotateButton.setAttribute("aria-pressed", "false");
  autoRotateButton.textContent = "Auto rotate";

  anatomyGroup.rotation.set(0, 0, 0);
  if (reconstructionVisualizationController?.snapshot().canVolume) {
    requestReconstructionVisualizationMode("volume");
  }
  applyOpacity();
  setViewerInteractionMode("rotate");
  fitSavedView();
}

function preferredTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // Storage can be blocked without affecting viewer operation.
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(theme, persist = false) {
  const normalized = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = normalized;
  themeToggle.setAttribute("aria-pressed", normalized === "light" ? "true" : "false");
  themeToggle.setAttribute(
    "aria-label",
    normalized === "light" ? "Switch to dark mode" : "Switch to light mode",
  );
  themeToggle.setAttribute(
    "title",
    normalized === "light" ? "Switch to dark mode" : "Switch to light mode",
  );
  if (themeColorMeta) {
    themeColorMeta.setAttribute("content", normalized === "light" ? "#eef5fb" : "#020915");
  }
  if (persist) {
    try {
      localStorage.setItem(THEME_KEY, normalized);
    } catch {
      // Theme persistence is optional.
    }
  }
}

async function refreshAccountName() {
  try {
    const response = await fetch("/api/auth/session", {
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    if (!response.ok) return;
    const payload = await response.json();
    if (payload.authenticated && typeof payload.username === "string" && payload.username.trim()) {
      accountName.textContent = payload.username.trim();
    }
  } catch {
    // The workspace remains usable if account decoration cannot refresh.
  }
}

function setWorkflowStep(element, stateName) {
  element.dataset.state = stateName;
  element.classList.toggle("is-active", stateName === "active");
  if (stateName === "active") {
    element.setAttribute("aria-current", "step");
  } else {
    element.removeAttribute("aria-current");
  }
}

function setWorkflowForStudy(study) {
  if (study) {
    setWorkflowStep(workflowData, "complete");
    if (study.volume_ready) {
      setWorkflowStep(workflowReconstruction, "complete");
      setWorkflowStep(workflowVisualization, "pending");
      volumeStatusRow.dataset.state = "ready";
      volumeStatusText.textContent = "Patient volume ready";
    } else {
      setWorkflowStep(workflowReconstruction, "active");
      setWorkflowStep(workflowVisualization, "pending");
      volumeStatusRow.dataset.state = study.reconstruction_ready ? "ready" : "pending";
      volumeStatusText.textContent = study.reconstruction_ready
        ? "Geometry ready - volume reconstruction pending"
        : "Geometry needs review before reconstruction";
    }
  } else {
    setWorkflowStep(workflowData, "active");
    setWorkflowStep(workflowReconstruction, "pending");
    setWorkflowStep(workflowVisualization, "pending");
    volumeStatusRow.dataset.state = "pending";
    volumeStatusText.textContent = "Awaiting DICOM";
  }
}

function setMprVolumeState(study) {
  const ready = Boolean(study?.volume_ready);
  for (const entry of mprRegistry.values()) {
    entry.renderedPlaneDescriptor = null;
    entry.renderedPositionLpsMm = null;
    renderMprClippingOverlay(entry.surface, null);
    clearSegmentationOverlay(entry.overlayCanvas);
  }
  clearPatientVolumeRendering();
  volumeTextureManager.dispose();
  volumeRenderingTask = null;
  state.volumeRendering.descriptor = null;
  state.volumeRendering.textureResource = null;
  for (const panel of mprPanels) {
    panel.dataset.volumeState = ready ? "loading" : "empty";
  }
  for (const message of mprVolumeMessages) {
    message.textContent = ready ? "Loading patient volume..." : "DICOM volume not loaded";
  }
  if (!ready) {
    state.mpr.descriptor = null;
    setSegmentationOverlayAvailability(null);
    resetPatientClipping();
    for (const entry of mprRegistry.values()) {
      entry.index.textContent = "-- / --";
      entry.position.textContent = `${entry.panel.id === "mprAxial" ? "Z" : entry.panel.id === "mprCoronal" ? "Y" : "X"}: --`;
      entry.wl.textContent = "W: --   L: --";
    }
  }
}

async function ensureVolumeRenderingFoundation() {
  if (!state.study?.volume_ready) return null;
  if (state.volumeRendering.textureResource) return state.volumeRendering.descriptor;
  if (volumeRenderingTask) return volumeRenderingTask.promise;

  const deviceQualification = qualifyCanonicalVolumeForDevice(
    state.study.volume,
    state.volumeRendering.capabilities,
  );
  if (!deviceQualification.ready) {
    setStatus("error", `${deviceQualification.reason}. Synchronized MPR remains available.`);
    return null;
  }

  const task = { promise: null };
  task.promise = (async () => {
    setStatus("loading", "Preparing patient volume...");
    const response = await fetch("/api/studies/latest/volume-rendering", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(
        payload.detail || `3D volume preparation failed (${response.status})`,
      );
    }
    if (volumeRenderingTask !== task) {
      throw new DOMException("Patient volume texture load was superseded", "AbortError");
    }
    const descriptor = payload.volume_rendering;
    const qualification = validateVolumeRenderingDescriptor(
      descriptor,
      state.volumeRendering.capabilities,
    );
    if (!qualification.ready) throw new Error(qualification.reason);
    setStatus("loading", "Loading verified patient volume...");
    const textureResource = await volumeTextureManager.load(descriptor);
    if (volumeRenderingTask !== task) {
      throw new DOMException("Patient volume texture load was superseded", "AbortError");
    }
    setStatus("loading", "Preparing GPU volume rendering...");
    await activatePatientVolumeRendering(textureResource, task);
    if (volumeRenderingTask !== task) {
      throw new DOMException("Patient volume rendering was superseded", "AbortError");
    }
    state.volumeRendering.descriptor = descriptor;
    state.volumeRendering.textureResource = textureResource;
    void refreshVolumeSurfaceDescriptor();
    return descriptor;
  })();
  volumeRenderingTask = task;

  try {
    return await task.promise;
  } catch (error) {
    if (volumeRenderingTask === task) {
      clearPatientVolumeRendering();
      volumeTextureManager.dispose();
      state.volumeRendering.descriptor = null;
      state.volumeRendering.textureResource = null;
      setStatus(
        "error",
        error instanceof Error
          ? `${error.message}. Synchronized MPR remains available.`
          : "3D volume preparation failed. Synchronized MPR remains available.",
      );
    }
    return null;
  } finally {
    if (volumeRenderingTask === task) volumeRenderingTask = null;
  }
}

const MPR_AXIS_INDEX = { x: 0, y: 1, z: 2 };

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function mprPlaneIndex(planeDescriptor) {
  const axis = MPR_AXIS_INDEX[planeDescriptor.normal_axis];
  const [minimum] = planeDescriptor.position_range_mm;
  const spacing = Number(planeDescriptor.slice_spacing_mm);
  const raw = Math.round((state.mpr.crosshairLpsMm[axis] - minimum) / spacing);
  return clamp(raw, 0, Number(planeDescriptor.slice_count) - 1);
}

function mprPositionForIndex(planeDescriptor, index) {
  return Number(planeDescriptor.position_range_mm[0])
    + Number(index) * Number(planeDescriptor.slice_spacing_mm);
}

function mprPhysicalMetrics(planeDescriptor) {
  const width = Math.max(1, Number(planeDescriptor.image_width) || 1);
  const height = Math.max(1, Number(planeDescriptor.image_height) || 1);
  const spacing = Array.isArray(planeDescriptor.pixel_spacing_mm)
    ? planeDescriptor.pixel_spacing_mm.map(Number)
    : [1, 1];
  const verticalSpacing = Number.isFinite(spacing[0]) && spacing[0] > 0 ? spacing[0] : 1;
  const horizontalSpacing = Number.isFinite(spacing[1]) && spacing[1] > 0 ? spacing[1] : 1;
  const hRange = Array.isArray(planeDescriptor.horizontal_range_mm)
    ? planeDescriptor.horizontal_range_mm.map(Number)
    : [0, Math.max(width - 1, 1) * horizontalSpacing];
  const vRange = Array.isArray(planeDescriptor.vertical_range_mm)
    ? planeDescriptor.vertical_range_mm.map(Number)
    : [0, Math.max(height - 1, 1) * verticalSpacing];
  const physicalWidth = Math.abs(hRange[1] - hRange[0])
    || Math.max(width - 1, 1) * horizontalSpacing;
  const physicalHeight = Math.abs(vRange[1] - vRange[0])
    || Math.max(height - 1, 1) * verticalSpacing;
  return { width, height, physicalWidth, physicalHeight };
}

function configureMprSurface(entry, planeDescriptor) {
  const frame = entry.view.getBoundingClientRect();
  const availableWidth = Math.max(frame.width, 1);
  const availableHeight = Math.max(frame.height, 1);
  const { physicalWidth, physicalHeight } = mprPhysicalMetrics(planeDescriptor);
  const aspect = physicalWidth / physicalHeight;

  let displayWidth = availableWidth;
  let displayHeight = displayWidth / aspect;
  if (displayHeight > availableHeight) {
    displayHeight = availableHeight;
    displayWidth = displayHeight * aspect;
  }

  // The diagnostic surface itself always fills the MPR viewport with black.
  // Only the patient image is contained inside that surface, preserving the
  // physical field of view without clipping, cropping or stretching anatomy.
  const imageWidth = Math.max(1, displayWidth);
  const imageHeight = Math.max(1, displayHeight);
  const imageLeft = Math.max(0, (availableWidth - imageWidth) / 2);
  const imageTop = Math.max(0, (availableHeight - imageHeight) / 2);
  const imageRight = imageLeft + imageWidth;
  const imageBottom = imageTop + imageHeight;

  entry.surface.style.width = "100%";
  entry.surface.style.height = "100%";
  entry.surface.style.setProperty("--mpr-image-width", `${imageWidth}px`);
  entry.surface.style.setProperty("--mpr-image-height", `${imageHeight}px`);
  entry.surface.style.setProperty("--mpr-image-left", `${imageLeft}px`);
  entry.surface.style.setProperty("--mpr-image-top", `${imageTop}px`);
  entry.surface.style.setProperty("--mpr-image-right", `${imageRight}px`);
  entry.surface.style.setProperty("--mpr-image-bottom", `${imageBottom}px`);
  entry.surface.style.setProperty("--mpr-image-center-x", `${imageLeft + imageWidth / 2}px`);
  entry.surface.style.setProperty("--mpr-image-center-y", `${imageTop + imageHeight / 2}px`);
  entry.imageRect = {
    left: imageLeft,
    top: imageTop,
    width: imageWidth,
    height: imageHeight,
    right: imageRight,
    bottom: imageBottom,
  };
  updateMprCrosshairOverlayForEntry(entry, planeDescriptor);
  updateMprClippingOverlays();
}

function updateMprCrosshairOverlayForEntry(entry, planeDescriptor) {
  const imageRect = entry.imageRect;
  if (!imageRect) return;
  const horizontalAxis = MPR_AXIS_INDEX[planeDescriptor.horizontal_axis];
  const verticalAxis = MPR_AXIS_INDEX[planeDescriptor.vertical_axis];
  const [hMin, hMax] = planeDescriptor.horizontal_range_mm.map(Number);
  const [vMin, vMax] = planeDescriptor.vertical_range_mm.map(Number);
  const hFraction = hMax > hMin
    ? (state.mpr.crosshairLpsMm[horizontalAxis] - hMin) / (hMax - hMin)
    : 0.5;
  let vFraction = vMax > vMin
    ? (state.mpr.crosshairLpsMm[verticalAxis] - vMin) / (vMax - vMin)
    : 0.5;
  if (planeDescriptor.vertical_reverse) vFraction = 1 - vFraction;

  const x = imageRect.left + clamp(hFraction, 0, 1) * imageRect.width;
  const y = imageRect.top + clamp(vFraction, 0, 1) * imageRect.height;
  entry.surface.style.setProperty("--mpr-crosshair-x-px", `${x}px`);
  entry.surface.style.setProperty("--mpr-crosshair-y-px", `${y}px`);
}

function updateMprCrosshairOverlays() {
  const descriptor = state.mpr.descriptor;
  if (!descriptor) return;
  for (const [plane, entry] of mprRegistry.entries()) {
    updateMprCrosshairOverlayForEntry(entry, descriptor.planes[plane]);
  }
}

function updateMprClippingOverlays() {
  const descriptor = state.mpr.descriptor;
  const request = clippingRequest();
  for (const [plane, entry] of mprRegistry.entries()) {
    const planeDescriptor = descriptor?.planes?.[plane];
    // Continuous crosshair motion may lead the asynchronous image request.
    // Only annotate the accepted image, never a pending or previous study.
    const geometry = mprClippingOverlayToggle.checked && planeDescriptor
      && entry.renderedPlaneDescriptor === planeDescriptor
      ? projectMprClipping(planeDescriptor, request, entry.renderedPositionLpsMm)
      : null;
    renderMprClippingOverlay(entry.surface, geometry);
  }
}

function drawGray8(entry, pixels, width, height, planeDescriptor) {
  entry.canvas.width = width;
  entry.canvas.height = height;
  const context = entry.canvas.getContext("2d", { alpha: false });
  const image = context.createImageData(width, height);
  for (let source = 0, target = 0; source < pixels.length; source += 1, target += 4) {
    const value = pixels[source];
    image.data[target] = value;
    image.data[target + 1] = value;
    image.data[target + 2] = value;
    image.data[target + 3] = 255;
  }
  context.putImageData(image, 0, 0);
  configureMprSurface(entry, planeDescriptor);
}

function clearAllSegmentationOverlays() {
  for (const entry of mprRegistry.values()) {
    clearSegmentationOverlay(entry.overlayCanvas);
  }
}

function redrawSegmentationOverlays() {
  const presentation = state.segmentationOverlay.presentation;
  if (!state.segmentationOverlay.enabled || !presentation) {
    clearAllSegmentationOverlays();
    return;
  }
  for (const entry of mprRegistry.values()) {
    if (!(entry.segmentationLabels instanceof Uint16Array)) continue;
    drawSegmentationLabels(
      entry.overlayCanvas,
      entry.segmentationLabels,
      entry.segmentationWidth,
      entry.segmentationHeight,
      presentation,
      state.segmentationOverlay.opacity,
    );
  }
}

function setVolumeSurfaceDescriptor(descriptor) {
  state.volumeSurface.descriptor = descriptor || null;
  volumeSurfaceLayer.setDescriptor(descriptor || null);
  if (!descriptor) {
    volumeSurfacePanel.dataset.state = "unavailable";
    volumeSurfaceBuild.disabled = true;
    volumeSurfaceClear.disabled = true;
    volumeSurfaceIsovalue.disabled = true;
    syncReconstructionVisualizationResources();
    return;
  }
  const range = Array.isArray(descriptor.source_value_range) ? descriptor.source_value_range : [];
  const minimum = Number(range[0]);
  const maximum = Number(range[1]);
  const defaultLevel = Number(descriptor.default_isovalue);
  if (Number.isFinite(minimum) && Number.isFinite(maximum) && minimum < maximum) {
    const epsilon = Math.max(0.001, Math.abs(maximum - minimum) * 1e-6);
    volumeSurfaceIsovalue.min = String(minimum + epsilon);
    volumeSurfaceIsovalue.max = String(maximum - epsilon);
  }
  if (Number.isFinite(defaultLevel)) {
    volumeSurfaceIsovalue.value = String(defaultLevel);
  } else if (Number.isFinite(minimum) && Number.isFinite(maximum) && minimum < maximum) {
    volumeSurfaceIsovalue.value = String(Math.round((minimum + maximum) / 2));
  }
  volumeSurfaceBuild.disabled = !descriptor.available;
  volumeSurfaceIsovalue.disabled = !descriptor.available;
  volumeSurfaceClear.disabled = !volumeSurfaceLayer.current;
  syncReconstructionVisualizationResources();
}

async function refreshVolumeSurfaceDescriptor() {
  if (!state.study?.volume_ready || !volumeRayMarcher.current) {
    setVolumeSurfaceDescriptor(null);
    return null;
  }
  if (volumeSurfaceDescriptorPromise) return volumeSurfaceDescriptorPromise;
  const studyId = state.study.study_id;
  const request = (async () => {
    try {
      const response = await fetch("/api/studies/latest/volume-surface", {
        credentials: "same-origin",
        headers: { "Accept": "application/json" },
      });
      const payload = await response.json().catch(() => ({}));
      // An earlier study's delayed response may never replace the active study.
      if (studyId !== state.study?.study_id) return null;
      if (!response.ok) throw new Error(payload.detail || `Volume surface availability failed (${response.status})`);
      if (payload.volume_surface?.study_id !== studyId) return null;
      setVolumeSurfaceDescriptor(payload.volume_surface);
      return payload.volume_surface;
    } catch (error) {
      if (studyId !== state.study?.study_id) return null;
      setVolumeSurfaceDescriptor(null);
      volumeSurfacePanel.dataset.state = "error";
      volumeSurfaceStatus.textContent = error instanceof Error ? error.message : "Volume-derived surface availability failed";
      return null;
    }
  })();
  volumeSurfaceDescriptorPromise = request;
  try {
    return await request;
  } finally {
    if (volumeSurfaceDescriptorPromise === request) volumeSurfaceDescriptorPromise = null;
  }
}
async function requestVolumeSurfaceBuild() {
  const level = Number(volumeSurfaceIsovalue.value);
  try {
    const built = await volumeSurfaceLayer.build(level);
    if (built && volumeSurfaceLayer.current === built) {
      volumeSurfaceRegionStatus.textContent = "Qualifying resident Direct CT regions…";
      try {
        const evidence = await volumeSurfaceLayer.loadRegionEvidence();
        if (!evidence.available) {
          volumeSurfaceRegionStatus.textContent = "This surface has no two distinct qualified regions; full geometry remains visible.";
        }
      } catch {
        // An evidence failure must never alter or prevent the original surface.
        if (volumeSurfaceLayer.current === built) {
          volumeSurfaceRegionStatus.textContent = "Region evidence unavailable. Full geometry is retained.";
        }
      }
    }
    return built;
  } catch {
    // The volume surface layer owns its actionable build error status.
    return null;
  } finally {
    syncReconstructionVisualizationResources();
    volumeSurfaceClear.disabled = !volumeSurfaceLayer.current;
    if (volumeSurfaceLayer.current?.regionVisibility?.available) syncDirectCtRegionControls();
  }
}

function clearVolumeDerivedSurface() {
  volumeSurfaceLayer.clearSurface();
  syncReconstructionVisualizationResources();
  volumeSurfaceClear.disabled = true;
}

function clearSegmentationWorkflowPoll() {
  if (segmentationWorkflowPollTimer !== null) {
    window.clearTimeout(segmentationWorkflowPollTimer);
    segmentationWorkflowPollTimer = null;
  }
}

function segmentationWorkflowIsActive(workflow) {
  return ["queued", "starting", "running", "cancelling", "finalizing"].includes(
    String(workflow?.state || ""),
  );
}

function scheduleSegmentationWorkflowPoll(delay = 900) {
  clearSegmentationWorkflowPoll();
  const generation = segmentationWorkflowGeneration;
  segmentationWorkflowPollTimer = window.setTimeout(() => {
    segmentationWorkflowPollTimer = null;
    if (generation !== segmentationWorkflowGeneration) return;
    void refreshSegmentationWorkflowStatus({ activateAvailable: true });
  }, delay);
}

function renderSegmentationWorkflow(workflow) {
  segmentationWorkflowSnapshot = workflow;
  segmentationWorkflowPanel.render(workflow);
  if (activeSegmentationLabelMapId) {
    segmentationWorkflowPanel.setActivated(activeSegmentationLabelMapId);
  }
}

async function activateSegmentationResult(labelMapId) {
  const requestedLabelMapId = String(labelMapId || "");
  if (!requestedLabelMapId || !state.study?.study_id) return null;
  const descriptor = await refreshSegmentationOverlayDescriptor(requestedLabelMapId);
  if (!descriptor) return null;
  activeSegmentationLabelMapId = requestedLabelMapId;
  syncReconstructionVisualizationResources();
  segmentationWorkflowPanel.setActivated(requestedLabelMapId);
  scheduleMprRender();
  return descriptor;
}

async function refreshSegmentationWorkflowStatus({ activateAvailable = false } = {}) {
  if (!state.study?.study_id || !state.study?.volume_ready) {
    segmentationWorkflowPanel.reset();
    return null;
  }
  const generation = segmentationWorkflowGeneration;
  try {
    const response = await fetch("/api/studies/latest/segmentation-workflow", {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `Segmentation status failed (${response.status})`);
    }
    const workflow = payload.workflow;
    if (
      generation !== segmentationWorkflowGeneration
      || !workflow
      || workflow.study_id !== state.study.study_id
    ) {
      return null;
    }
    renderSegmentationWorkflow(workflow);
    if (workflow.state === "available" && activateAvailable && workflow.label_map_id) {
      clearSegmentationWorkflowPoll();
      await activateSegmentationResult(workflow.label_map_id);
    } else if (segmentationWorkflowIsActive(workflow)) {
      scheduleSegmentationWorkflowPoll();
    } else {
      clearSegmentationWorkflowPoll();
    }
    return workflow;
  } catch (error) {
    if (generation !== segmentationWorkflowGeneration) return null;
    clearSegmentationWorkflowPoll();
    segmentationWorkflowPanel.reset(
      error instanceof Error ? error.message : "Segmentation status unavailable",
    );
    return null;
  }
}

async function requestSegmentationStart() {
  if (!state.study?.study_id || !state.study?.volume_ready) return;
  const generation = segmentationWorkflowGeneration;
  segmentationWorkflowPanel.setBusy(
    segmentationWorkflowSnapshot?.state === "available"
      ? "Activating existing segmentation..."
      : "Starting segmentation...",
  );
  try {
    const response = await fetch("/api/studies/latest/segmentation-workflow/start", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `Segmentation start failed (${response.status})`);
    }
    if (generation !== segmentationWorkflowGeneration) return;
    const workflow = payload.workflow;
    renderSegmentationWorkflow(workflow);
    if (workflow?.state === "available" && workflow.label_map_id) {
      await activateSegmentationResult(workflow.label_map_id);
    } else if (segmentationWorkflowIsActive(workflow) || workflow?.state === "output_ready") {
      scheduleSegmentationWorkflowPoll(500);
    }
  } catch (error) {
    if (generation !== segmentationWorkflowGeneration) return;
    segmentationWorkflowPanel.reset(
      error instanceof Error ? error.message : "Segmentation could not start",
    );
    void refreshSegmentationWorkflowStatus();
  }
}

async function requestSegmentationCancel() {
  if (!state.study?.study_id) return;
  const generation = segmentationWorkflowGeneration;
  segmentationWorkflowPanel.setBusy("Requesting segmentation cancellation...");
  try {
    const response = await fetch("/api/studies/latest/segmentation-workflow/cancel", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `Segmentation cancellation failed (${response.status})`);
    }
    if (generation !== segmentationWorkflowGeneration) return;
    renderSegmentationWorkflow(payload.workflow);
    if (segmentationWorkflowIsActive(payload.workflow)) scheduleSegmentationWorkflowPoll(500);
  } catch (error) {
    if (generation !== segmentationWorkflowGeneration) return;
    segmentationWorkflowPanel.reset(
      error instanceof Error ? error.message : "Segmentation cancellation failed",
    );
    void refreshSegmentationWorkflowStatus();
  }
}

function setSegmentationSurfaceAvailability(descriptor) {
  segmentationSurfaceGate?.invalidate();
  const ready = Boolean(descriptor?.ready);
  state.segmentationSurface.descriptor = ready ? descriptor : null;
  segmentationSurfaceToggle.disabled = !ready;
  segmentationSurfacePanel.dataset.state = ready ? "ready" : "unavailable";
  if (ready) {
    segmentationSurfaceLayer.setDescriptor(descriptor);
    segmentationSurfaceLayer.setEnabled(state.segmentationSurface.enabled);
  } else {
    segmentationSurfaceLayer.clear();
  }
  syncSegmentation3dAppearance();
  syncReconstructionVisualizationResources();
}

async function syncSegmentationSurface() {
  if (!state.segmentationSurface.descriptor || !volumeRayMarcher.current) return null;
  try {
    return await segmentationSurfaceLayer.sync(state.segmentationOverlay.presentation);
  } catch (error) {
    segmentationSurfacePanel.dataset.state = "error";
    segmentationSurfaceStatus.textContent = error instanceof Error
      ? error.message
      : "Segmentation surface unavailable";
    return null;
  }
}

async function refreshSegmentationSurfaceDescriptor(labelMapId) {
  if (!labelMapId || !state.study?.study_id) {
    setSegmentationSurfaceAvailability(null);
    return null;
  }
  if (segmentationSurfaceDescriptorPromise) return segmentationSurfaceDescriptorPromise;
  segmentationSurfaceDescriptorPromise = (async () => {
    const params = new URLSearchParams({ label_map_id: labelMapId });
    const response = await fetch(`/api/studies/latest/segmentation-surfaces?${params}`, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `3D segmentation initialization failed (${response.status})`);
    }
    const descriptor = payload.surface;
    if (
      descriptor?.ready !== true
      || descriptor.label_map_id !== labelMapId
      || descriptor.source_study_id !== state.study.study_id
      || descriptor.coordinate_system !== "patient_lps"
    ) {
      throw new Error("3D segmentation study binding is invalid");
    }
    setSegmentationSurfaceAvailability(descriptor);
    void syncSegmentationSurface();
    return descriptor;
  })();
  try {
    return await segmentationSurfaceDescriptorPromise;
  } catch (error) {
    setSegmentationSurfaceAvailability(null);
    segmentationSurfacePanel.dataset.state = "error";
    segmentationSurfaceStatus.textContent = error instanceof Error
      ? error.message
      : "3D segmentation unavailable";
    return null;
  } finally {
    segmentationSurfaceDescriptorPromise = null;
  }
}

function setSegmentationOverlayAvailability(descriptor) {
  const ready = Boolean(descriptor?.ready);
  const nextLabelMapId = ready ? descriptor.label_map_id : null;
  if (segmentation3dAppearanceLabelMapId !== nextLabelMapId) {
    segmentation3dAppearanceMode = "scientific";
    segmentation3dAppearanceLabelMapId = nextLabelMapId;
    segmentation3dAppearance.value = "scientific";
    segmentationSurfaceLayer?.set3dColorOverrides(new Map());
  }
  state.segmentationOverlay.descriptor = ready ? descriptor : null;
  state.segmentationOverlay.presentation = null;
  segmentationOverlayPanel.dataset.state = ready ? "ready" : "unavailable";
  segmentationOverlayToggle.disabled = !ready;
  segmentationOverlayOpacity.disabled = !ready;
  for (const entry of mprRegistry.values()) {
    entry.segmentationLabels = null;
    entry.segmentationWidth = null;
    entry.segmentationHeight = null;
  }
  if (ready) {
    state.segmentationOverlay.presentation = segmentationStructurePanel.load(descriptor);
    syncSegmentationCorrectionContext(state.segmentationOverlay.presentation);
    syncSegmentationOverlayPresentationStatus(state.segmentationOverlay.presentation);
  } else {
    segmentationStructurePanel.clear();
    segmentationCorrectionPanel.clear();
    segmentationOverlayStatus.textContent = "No canonical label map for this study.";
    clearAllSegmentationOverlays();
    setSegmentationSurfaceAvailability(null);
  }
  syncSegmentation3dAppearance();
}

async function refreshSegmentationOverlayDescriptor(labelMapId) {
  if (!state.study?.study_id || !state.mpr.descriptor || !labelMapId) {
    setSegmentationOverlayAvailability(null);
    return null;
  }
  if (segmentationOverlayDescriptorPromise) return segmentationOverlayDescriptorPromise;
  segmentationOverlayDescriptorPromise = (async () => {
    const params = new URLSearchParams({ label_map_id: String(labelMapId) });
    const response = await fetch(`/api/studies/latest/segmentation-overlay?${params}`, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `Segmentation overlay initialization failed (${response.status})`);
    }
    const descriptor = payload.overlay;
    if (!descriptor?.ready) {
      setSegmentationOverlayAvailability(null);
      return null;
    }
    if (
      descriptor.source_study_id !== state.study.study_id
      || descriptor.label_map_id !== labelMapId
    ) {
      throw new Error("Segmentation overlay study binding is invalid");
    }
    setSegmentationOverlayAvailability(descriptor);
    await refreshSegmentationSurfaceDescriptor(descriptor.label_map_id);
    return descriptor;
  })();
  try {
    return await segmentationOverlayDescriptorPromise;
  } catch (error) {
    setSegmentationOverlayAvailability(null);
    segmentationOverlayPanel.dataset.state = "error";
    segmentationOverlayStatus.textContent = error instanceof Error
      ? error.message
      : "Segmentation overlay unavailable";
    return null;
  } finally {
    segmentationOverlayDescriptorPromise = null;
  }
}

async function renderSegmentationOverlayPlane(
  plane,
  index,
  generation,
  signal,
  expectedWidth,
  expectedHeight,
) {
  const descriptor = state.segmentationOverlay.descriptor;
  const entry = mprRegistry.get(plane);
  if (!entry) return;
  if (!descriptor || !state.segmentationOverlay.enabled) {
    clearSegmentationOverlay(entry.overlayCanvas);
    return;
  }
  const params = new URLSearchParams({
    index: String(index),
    label_map_id: descriptor.label_map_id,
  });
  const response = await fetch(
    `/api/studies/latest/segmentation-overlay/${plane}?${params}`,
    {
      credentials: "same-origin",
      headers: { "Accept": "application/x-voxelatlas-rgba8" },
      signal,
    },
  );
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Segmentation overlay rendering failed (${response.status})`);
  }
  const width = Number(response.headers.get("X-VoxelAtlas-Width"));
  const height = Number(response.headers.get("X-VoxelAtlas-Height"));
  const labelMapId = response.headers.get("X-VoxelAtlas-Label-Map-Id");
  const pixels = new Uint8Array(await response.arrayBuffer());
  if (generation !== mprRenderGeneration) return;
  if (
    width !== expectedWidth
    || height !== expectedHeight
    || labelMapId !== descriptor.label_map_id
  ) {
    throw new Error("Segmentation overlay geometry binding is invalid");
  }
  entry.segmentationLabels = decodeSegmentationLabels(
    pixels,
    width,
    height,
    descriptor.palette,
  );
  entry.segmentationWidth = width;
  entry.segmentationHeight = height;
  drawSegmentationLabels(
    entry.overlayCanvas,
    entry.segmentationLabels,
    width,
    height,
    state.segmentationOverlay.presentation,
    state.segmentationOverlay.opacity,
  );
}

async function renderMprPlane(plane, generation, signal) {
  const descriptor = state.mpr.descriptor;
  const entry = mprRegistry.get(plane);
  if (!descriptor || !entry) return;
  const planeDescriptor = descriptor.planes[plane];
  const index = mprPlaneIndex(planeDescriptor);
  const position = mprPositionForIndex(planeDescriptor, index);
  const params = new URLSearchParams({
    index: String(index),
    window: String(state.mpr.window),
    level: String(state.mpr.level),
  });
  const response = await fetch(`/api/studies/latest/mpr/${plane}?${params}`, {
    credentials: "same-origin",
    headers: { "Accept": "application/x-voxelatlas-gray8" },
    signal,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `MPR rendering failed (${response.status})`);
  }
  const width = Number(response.headers.get("X-VoxelAtlas-Width"));
  const height = Number(response.headers.get("X-VoxelAtlas-Height"));
  const buffer = new Uint8Array(await response.arrayBuffer());
  if (generation !== mprRenderGeneration) return;
  if (!Number.isInteger(width) || !Number.isInteger(height) || buffer.length !== width * height) {
    throw new Error("MPR image payload is invalid");
  }
  entry.renderedPlaneDescriptor = planeDescriptor;
  entry.renderedPositionLpsMm = position;
  drawGray8(entry, buffer, width, height, planeDescriptor);
  try {
    await renderSegmentationOverlayPlane(
      plane,
      index,
      generation,
      signal,
      width,
      height,
    );
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    clearSegmentationOverlay(entry.overlayCanvas);
    segmentationOverlayPanel.dataset.state = "error";
    segmentationOverlayStatus.textContent = error instanceof Error
      ? error.message
      : "Segmentation overlay rendering failed";
  }
  entry.panel.dataset.volumeState = "ready";
  entry.index.textContent = `${index + 1} / ${planeDescriptor.slice_count}`;
  entry.position.textContent = `${planeDescriptor.coordinate}: ${position.toFixed(2)} mm`;
  entry.wl.textContent = `W: ${Math.round(state.mpr.window)}   L: ${Math.round(state.mpr.level)}`;
}

async function renderAllMprPlanes() {
  if (!state.mpr.descriptor) return;
  const generation = ++mprRenderGeneration;
  mprAbortController?.abort();
  mprAbortController = new AbortController();
  const signal = mprAbortController.signal;
  updateMprCrosshairOverlays();
  try {
    await Promise.all([
      renderMprPlane("axial", generation, signal),
      renderMprPlane("coronal", generation, signal),
      renderMprPlane("sagittal", generation, signal),
    ]);
    if (generation === mprRenderGeneration) {
      for (const entry of mprRegistry.values()) entry.panel.dataset.volumeState = "ready";
    }
  } catch (error) {
    if (generation !== mprRenderGeneration || error?.name === "AbortError") return;
    for (const entry of mprRegistry.values()) {
      entry.panel.dataset.volumeState = "loading";
      entry.message.textContent = error instanceof Error ? error.message : "MPR rendering failed";
    }
  }
}

function scheduleMprRender(delay = 0) {
  if (mprRenderTimer !== null) window.clearTimeout(mprRenderTimer);
  mprRenderTimer = window.setTimeout(() => {
    mprRenderTimer = null;
    void renderAllMprPlanes();
  }, delay);
}

async function ensureMprReady() {
  if (!state.study?.volume_ready) return null;
  if (state.mpr.descriptor) {
    scheduleMprRender();
    return state.mpr.descriptor;
  }
  if (mprDescriptorPromise) return mprDescriptorPromise;

  mprDescriptorPromise = (async () => {
    const response = await fetch("/api/studies/latest/mpr", {
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.mpr?.ready) {
      throw new Error(payload.detail || `MPR initialization failed (${response.status})`);
    }
    state.mpr.descriptor = payload.mpr;
    state.mpr.crosshairLpsMm = payload.mpr.crosshair_lps_mm.map(Number);
    state.mpr.window = Number(payload.mpr.default_window.width);
    state.mpr.level = Number(payload.mpr.default_window.level);
    syncClippingControlsFromMpr();
    for (const entry of mprRegistry.values()) {
      entry.panel.dataset.volumeState = "loading";
      entry.message.textContent = "Rendering patient volume...";
    }
    await renderAllMprPlanes();
    return payload.mpr;
  })();

  try {
    return await mprDescriptorPromise;
  } catch (error) {
    for (const entry of mprRegistry.values()) {
      entry.panel.dataset.volumeState = "loading";
      entry.message.textContent = error instanceof Error ? error.message : "MPR initialization failed";
    }
    return null;
  } finally {
    mprDescriptorPromise = null;
  }
}

function setMprCrosshairFromPointer(plane, event) {
  const descriptor = state.mpr.descriptor;
  const entry = mprRegistry.get(plane);
  if (!descriptor || !entry) return;
  const planeDescriptor = descriptor.planes[plane];
  const rect = entry.canvas.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) return;
  const x = clamp((event.clientX - rect.left) / rect.width, 0, 1);
  const y = clamp((event.clientY - rect.top) / rect.height, 0, 1);
  const hAxis = MPR_AXIS_INDEX[planeDescriptor.horizontal_axis];
  const vAxis = MPR_AXIS_INDEX[planeDescriptor.vertical_axis];
  const [hMin, hMax] = planeDescriptor.horizontal_range_mm.map(Number);
  const [vMin, vMax] = planeDescriptor.vertical_range_mm.map(Number);
  state.mpr.crosshairLpsMm[hAxis] = hMin + x * (hMax - hMin);
  const verticalFraction = planeDescriptor.vertical_reverse ? 1 - y : y;
  state.mpr.crosshairLpsMm[vAxis] = vMin + verticalFraction * (vMax - vMin);
  syncClippingControlsFromMpr();
  updateMprCrosshairOverlays();
  scheduleMprRender(35);
}

function stepMprSlice(plane, direction) {
  const descriptor = state.mpr.descriptor;
  if (!descriptor) return;
  const planeDescriptor = descriptor.planes[plane];
  const axis = MPR_AXIS_INDEX[planeDescriptor.normal_axis];
  const currentIndex = mprPlaneIndex(planeDescriptor);
  const nextIndex = clamp(currentIndex + direction, 0, Number(planeDescriptor.slice_count) - 1);
  state.mpr.crosshairLpsMm[axis] = mprPositionForIndex(planeDescriptor, nextIndex);
  syncClippingControlsFromMpr();
  updateMprCrosshairOverlays();
  scheduleMprRender(20);
}

function adjustMprWindowLevel(start, event) {
  const dx = event.clientX - start.x;
  const dy = event.clientY - start.y;
  const widthScale = Math.max(start.window / 240, 0.5);
  state.mpr.window = Math.max(1, start.window + dx * widthScale);
  state.mpr.level = start.level - dy * widthScale;
  for (const entry of mprRegistry.values()) {
    entry.wl.textContent = `W: ${Math.round(state.mpr.window)}   L: ${Math.round(state.mpr.level)}`;
  }
  scheduleMprRender(45);
}

for (const [plane, entry] of mprRegistry.entries()) {
  let pointerMode = null;
  let wlStart = null;
  entry.view.addEventListener("contextmenu", (event) => event.preventDefault());
  entry.view.addEventListener("pointerdown", (event) => {
    if (!state.mpr.descriptor || entry.panel.dataset.volumeState === "empty") return;
    if (event.button === 2) {
      pointerMode = "window-level";
      wlStart = { x: event.clientX, y: event.clientY, window: state.mpr.window, level: state.mpr.level };
      entry.view.dataset.interaction = "window-level";
    } else if (event.button === 0) {
      pointerMode = "crosshair";
      state.mpr.activePlane = plane;
      setMprCrosshairFromPointer(plane, event);
    } else {
      return;
    }
    entry.view.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  });
  entry.view.addEventListener("pointermove", (event) => {
    if (pointerMode === "crosshair") setMprCrosshairFromPointer(plane, event);
    if (pointerMode === "window-level" && wlStart) adjustMprWindowLevel(wlStart, event);
  });
  const finishPointer = (event) => {
    if (pointerMode !== null) entry.view.releasePointerCapture?.(event.pointerId);
    pointerMode = null;
    wlStart = null;
    delete entry.view.dataset.interaction;
  };
  entry.view.addEventListener("pointerup", finishPointer);
  entry.view.addEventListener("pointercancel", finishPointer);
  entry.view.addEventListener("wheel", (event) => {
    if (!state.mpr.descriptor) return;
    event.preventDefault();
    stepMprSlice(plane, event.deltaY >= 0 ? 1 : -1);
  }, { passive: false });
}

function centerMprCrosshair() {
  const descriptor = state.mpr.descriptor;
  if (!descriptor) return;
  const bounds = descriptor.patient_bounds_lps_mm;
  state.mpr.crosshairLpsMm = ["x", "y", "z"].map((axis) => {
    const range = Array.isArray(bounds?.[axis]) ? bounds[axis].map(Number) : [0, 0];
    return (range[0] + range[1]) / 2;
  });
  syncClippingControlsFromMpr();
  updateMprCrosshairOverlays();
  scheduleMprRender();
}

function resetMprWindowLevel() {
  const descriptor = state.mpr.descriptor;
  if (!descriptor) return;
  state.mpr.window = Number(descriptor.default_window.width);
  state.mpr.level = Number(descriptor.default_window.level);
  for (const entry of mprRegistry.values()) {
    entry.wl.textContent = `W: ${Math.round(state.mpr.window)}   L: ${Math.round(state.mpr.level)}`;
  }
  scheduleMprRender();
}

function acknowledgeMprTool(button) {
  button.classList.remove("is-confirmed");
  window.requestAnimationFrame(() => button.classList.add("is-confirmed"));
  window.setTimeout(() => button.classList.remove("is-confirmed"), 420);
}

document.querySelectorAll("[data-mpr-center]").forEach((button) => {
  button.addEventListener("click", () => {
    centerMprCrosshair();
    acknowledgeMprTool(button);
  });
});

document.querySelectorAll("[data-mpr-reset-window]").forEach((button) => {
  button.addEventListener("click", () => {
    resetMprWindowLevel();
    acknowledgeMprTool(button);
  });
});

async function toggleMprFullscreen(plane) {
  const entry = mprRegistry.get(plane);
  if (!entry || !state.mpr.descriptor) return;
  try {
    if (document.fullscreenElement === entry.panel) {
      await document.exitFullscreen();
    } else if (!document.fullscreenElement && entry.panel.requestFullscreen) {
      await entry.panel.requestFullscreen();
    }
  } catch (error) {
    console.error(error);
  }
}

document.querySelectorAll("[data-mpr-fullscreen]").forEach((button) => {
  button.addEventListener("click", () => {
    void toggleMprFullscreen(button.dataset.mprFullscreen);
  });
});


function formatStudyDate(raw) {
  if (typeof raw !== "string" || !/^\d{8}$/.test(raw)) return raw || "-";
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

function formatSpacing(value) {
  if (!Array.isArray(value) || value.length < 2) return "-";
  return `${value.slice(0, 2).map((item) => Number(item).toFixed(3)).join(" × ")} mm`;
}

function primarySeries(study) {
  if (!study || !Array.isArray(study.series)) return null;
  const preferredUid = study.reconstruction_series_uid || study.primary_series_uid;
  return study.series.find((item) => item.series_instance_uid === preferredUid)
    || study.series[0]
    || null;
}

function geometrySummary(series) {
  const geometry = series?.geometry;
  if (!geometry) return "Geometry unavailable";
  if (!geometry.reconstruction_ready) {
    const count = Array.isArray(geometry.issues) ? geometry.issues.length : 0;
    return count > 0 ? `Geometry review - ${count} issue${count === 1 ? "" : "s"}` : "Geometry needs review";
  }
  const orientation = typeof geometry.orientation_label === "string"
    ? geometry.orientation_label.charAt(0).toUpperCase() + geometry.orientation_label.slice(1)
    : "Geometry";
  const spacing = Number(geometry.slice_spacing_mm);
  return Number.isFinite(spacing)
    ? `${orientation} • ${spacing.toFixed(3)} mm slice spacing`
    : `${orientation} • geometry ready`;
}

function setUploadStatus(kind, message) {
  uploadStatus.dataset.state = kind;
  uploadStatus.textContent = message;
}

function setPatientVolumeReadyStatus() {
  setUploadStatus("ready", "Patient volume and synchronized MPR ready.");
}

function formatSampleSize(sizeBytes) {
  const bytes = Number(sizeBytes);
  if (!Number.isFinite(bytes) || bytes < 0) return "Size unavailable";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

function sampleLink(label, url) {
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = label;
  return link;
}

function renderSampleCatalog(samples) {
  sampleCatalogGrid.replaceChildren();
  sampleCatalogEmpty.hidden = samples.length !== 0;
  if (samples.length === 0) return;

  for (const sample of samples) {
    const card = document.createElement("article");
    card.className = "sample-study-card";
    card.dataset.sampleId = sample.sampleId;

    const preview = document.createElement("div");
    preview.className = "sample-study-preview";
    if (sample.previewAvailable && sample.previewUrl) {
      const image = document.createElement("img");
      image.src = sample.previewUrl;
      image.alt = `${sample.title} preview`;
      image.loading = "lazy";
      image.referrerPolicy = "same-origin";
      preview.appendChild(image);
    } else {
      const monogram = document.createElement("span");
      monogram.textContent = sample.modality;
      preview.appendChild(monogram);
    }

    const copy = document.createElement("div");
    copy.className = "sample-study-card-copy";
    const tags = document.createElement("div");
    tags.className = "sample-study-tags";
    for (const [text, muted] of [[sample.modality, false], [sample.bodyRegion, true]]) {
      const tag = document.createElement("span");
      tag.className = `sample-study-tag${muted ? " is-muted" : ""}`;
      tag.textContent = text;
      tags.appendChild(tag);
    }
    const title = document.createElement("h3");
    title.textContent = sample.title;
    const summary = document.createElement("p");
    summary.className = "sample-study-summary";
    summary.textContent = sample.summary;
    const metadata = document.createElement("p");
    metadata.className = "sample-study-meta";
    metadata.textContent = `${sample.fileCount} files · ${formatSampleSize(sample.sizeBytes)}`;
    const links = document.createElement("div");
    links.className = "sample-study-links";
    links.append(
      sampleLink(sample.sourceLabel, sample.sourceUrl),
      sampleLink(sample.licenseLabel, sample.licenseUrl),
    );
    const open = document.createElement("button");
    open.className = "sample-study-open";
    open.type = "button";
    open.textContent = "Open in VoxelAtlas";
    open.addEventListener("click", () => void requestSampleLoad(sample));
    copy.append(tags, title, summary, metadata, links, open);
    card.append(preview, copy);
    sampleCatalogGrid.appendChild(card);
  }
}

function setSampleCatalogProgress(visible, title = "Preparing study", message = "") {
  sampleCatalogLoading = visible;
  sampleCatalogProgress.hidden = !visible;
  sampleCatalogClose.disabled = visible;
  sampleCatalogProgressTitle.textContent = title;
  sampleCatalogProgressText.textContent = message;
}

async function openSampleCatalog() {
  if (!sampleCatalogDialog.open && typeof sampleCatalogDialog.showModal === "function") {
    sampleCatalogDialog.showModal();
  }
  sampleCatalogEmpty.hidden = true;
  sampleReplaceConfirm.hidden = true;
  setSampleCatalogProgress(
    true,
    "Loading demonstration studies",
    "Reading the installed catalog and provenance records...",
  );
  try {
    renderSampleCatalog(await sampleStudyCatalogClient.list());
  } catch (error) {
    renderSampleCatalog([]);
    const message = sampleCatalogEmpty.querySelector("p");
    if (message) {
      message.textContent = error instanceof Error
        ? error.message
        : "Demonstration studies could not be loaded.";
    }
  } finally {
    setSampleCatalogProgress(false);
  }
}

function confirmSampleReplacement(sample) {
  if (!state.study) return Promise.resolve(true);
  if (sampleReplacementResolver) sampleReplacementResolver(false);
  sampleReplaceText.textContent = (
    `Opening ${sample.title} will replace the scan currently shown. `
    + "The source files already stored on the server are not deleted."
  );
  sampleReplaceConfirm.hidden = false;
  sampleReplaceAccept.focus();
  return new Promise((resolve) => {
    sampleReplacementResolver = resolve;
  });
}

function resolveSampleReplacement(accepted) {
  if (!sampleReplacementResolver) return;
  const resolve = sampleReplacementResolver;
  sampleReplacementResolver = null;
  sampleReplaceConfirm.hidden = true;
  resolve(accepted);
}

async function requestSampleLoad(sample) {
  if (!await confirmSampleReplacement(sample)) return;
  setSampleCatalogProgress(
    true,
    `Opening ${sample.title}`,
    "Verifying every file before normal CT/MR ingestion...",
  );
  try {
    const payload = await sampleStudyCatalogClient.load(sample.sampleId);
    const activation = classifySampleStudyActivation(payload);
    applyStudy(payload.study);
    sampleCatalogDialog.close();
    if (activation === "restore") {
      await restoreReadyPatientVolume(
        `${sample.title} restored. Loading its synchronized patient volume...`,
      );
    } else if (activation === "construct") {
      setUploadStatus(
        "uploading",
        `${sample.title} verified. Building its canonical patient volume...`,
      );
      await ensureCanonicalVolume(payload.study);
    } else {
      setUploadStatus("warning", "Demonstration study loaded, but its geometry needs review.");
    }
  } catch (error) {
    setUploadStatus(
      "error",
      error instanceof Error ? error.message : "Demonstration study could not be opened",
    );
  } finally {
    setSampleCatalogProgress(false);
  }
}

function renderSeriesDialog(study) {
  seriesDialogList.replaceChildren();
  if (!study || !Array.isArray(study.series) || study.series.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = "No DICOM series are available.";
    seriesDialogList.appendChild(empty);
    return;
  }

  for (const series of study.series) {
    const item = document.createElement("article");
    item.className = "series-dialog-item";
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = series.series_description || `Series ${series.series_number ?? "-"}`;
    const metadata = document.createElement("span");
    metadata.textContent = `${series.modality || "-"} • ${series.rows || "-"} × ${series.columns || "-"}`;
    const geometry = document.createElement("span");
    geometry.className = "series-dialog-geometry";
    geometry.dataset.state = series.geometry?.reconstruction_ready ? "ready" : "review";
    geometry.textContent = geometrySummary(series);
    const uid = document.createElement("small");
    uid.textContent = series.series_instance_uid || "Series UID unavailable";
    copy.append(title, metadata, geometry, uid);

    const count = document.createElement("span");
    count.className = "series-dialog-count";
    count.textContent = `${series.instance_count || 0} instance${series.instance_count === 1 ? "" : "s"}`;
    item.append(copy, count);
    seriesDialogList.appendChild(item);
  }
}

function applyStudy(study) {
  const previousStudyId = state.study?.study_id || null;
  const nextStudyId = study?.study_id || null;
  if (previousStudyId !== nextStudyId) {
    mprAbortController?.abort();
    state.mpr.descriptor = null;
    segmentationWorkflowGeneration += 1;
    clearSegmentationWorkflowPoll();
    segmentationWorkflowSnapshot = null;
    activeSegmentationLabelMapId = null;
    segmentationWorkflowPanel.reset();
    setSegmentationOverlayAvailability(null);
  }
  state.study = study;
  setWorkflowForStudy(study);
  setMprVolumeState(study);

  if (!study) {
    studyCard.dataset.studyState = "empty";
    studyLabel.textContent = "No DICOM study loaded";
    studyOriginBadge.hidden = true;
    studyId.textContent = "-";
    studyModality.textContent = "-";
    studyDate.textContent = "-";
    studyModalityValue.textContent = "-";
    studyInstanceCount.textContent = "-";
    studySeriesCount.textContent = "-";
    seriesDescription.textContent = "Not loaded";
    seriesManufacturer.textContent = "-";
    seriesPixelSpacing.textContent = "-";
    seriesMatrix.textContent = "-";
    seriesSliceThickness.textContent = "-";
    seriesButton.disabled = true;
    seriesButtonLabel.textContent = "DICOM series unavailable";
    uploadDicomLabel.textContent = "Upload DICOM";
    setVolumeAvailability(false);
    return;
  }

  const series = primarySeries(study);
  const modalities = Array.isArray(study.modalities) ? study.modalities.join(" / ") : "-";
  studyCard.dataset.studyState = "ready";
  studyLabel.textContent = study.study_description || "DICOM study";
  const isSampleStudy = study.origin?.kind === "sample";
  studyOriginBadge.hidden = !isSampleStudy;
  studyOriginBadge.textContent = isSampleStudy ? "Sample study" : "";
  studyId.textContent = String(study.study_id || "-").slice(0, 12).toUpperCase();
  studyModality.textContent = modalities || "-";
  studyDate.textContent = formatStudyDate(study.study_date);
  studyModalityValue.textContent = modalities || "-";
  studyInstanceCount.textContent = String(study.file_count ?? "-");
  studySeriesCount.textContent = String(study.series_count ?? "-");
  seriesDescription.textContent = series?.series_description || "-";
  seriesManufacturer.textContent = series?.manufacturer || "-";
  seriesPixelSpacing.textContent = formatSpacing(series?.pixel_spacing);
  seriesMatrix.textContent = series?.rows && series?.columns
    ? `${series.rows} × ${series.columns}`
    : "-";
  seriesSliceThickness.textContent = Number.isFinite(Number(series?.slice_thickness))
    ? `${Number(series.slice_thickness).toFixed(3)} mm`
    : "-";
  seriesButton.disabled = false;
  seriesButtonLabel.textContent = `${study.series_count} DICOM series discovered`;
  uploadDicomLabel.textContent = "Upload DICOM";
  renderSeriesDialog(study);
  setVolumeAvailability(volumeLayer.available);
}

async function ensureCanonicalVolume(study) {
  if (!study?.reconstruction_ready || study.volume_ready) return study;
  if (volumeBuildPromise) return volumeBuildPromise;

  volumeStatusRow.dataset.state = "pending";
  volumeStatusText.textContent = "Building patient volume...";
  setUploadStatus("uploading", "Geometry qualified. Building canonical patient volume...");

  volumeBuildPromise = (async () => {
    const response = await fetch("/api/studies/latest/volume", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `Patient volume construction failed (${response.status})`);
    }
    applyStudy(payload.study || null);
    setUploadStatus(
      "ready",
      "Canonical patient volume built. Loading synchronized MPR views...",
    );
    // Post-6F stabilization: start the independent GPU volume path immediately
    // while synchronized MPR initializes. The later await reuses the same task.
    void ensureVolumeRenderingFoundation();
    await ensureMprReady();
    setPatientVolumeReadyStatus();
    await ensureVolumeRenderingFoundation();
    void refreshSegmentationWorkflowStatus({ activateAvailable: false });
    return payload.study || null;
  })();

  try {
    return await volumeBuildPromise;
  } catch (error) {
    setUploadStatus(
      "error",
      error instanceof Error ? error.message : "Patient volume construction failed",
    );
    volumeStatusRow.dataset.state = "pending";
    volumeStatusText.textContent = "Geometry ready - volume construction failed";
    return study;
  } finally {
    volumeBuildPromise = null;
  }
}

async function restoreReadyPatientVolume(message) {
  setUploadStatus("ready", message);
  // Post-6F stabilization: restore MPR and the GPU volume in parallel so the
  // workspace becomes useful sooner when switching between ready studies.
  void ensureVolumeRenderingFoundation();
  await ensureMprReady();
  setPatientVolumeReadyStatus();
  await ensureVolumeRenderingFoundation();
  void refreshSegmentationWorkflowStatus({ activateAvailable: false });
}

async function refreshLatestStudy() {
  try {
    const response = await fetch("/api/studies/latest", {
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
    if (!response.ok) return;
    const payload = await response.json();
    applyStudy(payload.study || null);
    if (payload.study) {
      if (payload.study.volume_ready) {
        await restoreReadyPatientVolume(
          "Stored canonical patient volume restored. Loading MPR views...",
        );
      } else if (payload.study.reconstruction_ready) {
        setUploadStatus("uploading", "Stored DICOM geometry restored. Building patient volume...");
        await ensureCanonicalVolume(payload.study);
      } else {
        setUploadStatus("warning", "Stored DICOM study restored. Geometry needs review before reconstruction.");
      }
    }
  } catch {
    // Study restoration is best effort; upload remains available.
  }
}


async function uploadDicomFiles(files) {
  if (!files || files.length === 0) return;
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name || "dicom-instance");
  }

  uploadDicomButton.disabled = true;
  uploadDicomButton.dataset.state = "uploading";
  uploadDicomLabel.textContent = "Upload DICOM";
  setUploadStatus("uploading", "Validating DICOM headers and grouping Study/Series metadata...");

  try {
    const response = await fetch("/api/studies/dicom", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
      body: formData,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `DICOM upload failed (${response.status})`);
    }
    applyStudy(payload.study);
    const skipped = Number(payload.study?.skipped_file_count || 0);
    if (payload.study?.reconstruction_ready) {
      setUploadStatus(
        "ready",
        skipped > 0
          ? `Geometry ready. ${payload.study.file_count} DICOM instances accepted; ${skipped} file${skipped === 1 ? "" : "s"} skipped.`
          : `Geometry ready. ${payload.study.file_count} DICOM instances validated across ${payload.study.series_count} series.`,
      );
      await ensureCanonicalVolume(payload.study);
    } else {
      setUploadStatus("warning", "Study accepted. Geometry needs review before reconstruction.");
    }
  } catch (error) {
    setUploadStatus("error", error instanceof Error ? error.message : "DICOM upload failed");
  } finally {
    uploadDicomLabel.textContent = "Upload DICOM";
    uploadDicomButton.disabled = false;
    uploadDicomButton.dataset.state = "idle";
    dicomFileInput.value = "";
  }
}

uploadDicomButton.addEventListener("click", () => dicomFileInput.click());
sampleCatalogButton.addEventListener("click", () => void openSampleCatalog());
sampleCatalogClose.addEventListener("click", () => {
  if (!sampleCatalogLoading) sampleCatalogDialog.close();
});
sampleCatalogDialog.addEventListener("cancel", (event) => {
  if (sampleCatalogLoading) event.preventDefault();
  resolveSampleReplacement(false);
});
sampleCatalogDialog.addEventListener("click", (event) => {
  if (event.target === sampleCatalogDialog && !sampleCatalogLoading) {
    resolveSampleReplacement(false);
    sampleCatalogDialog.close();
  }
});
sampleReplaceCancel.addEventListener("click", () => resolveSampleReplacement(false));
sampleReplaceAccept.addEventListener("click", () => resolveSampleReplacement(true));

dicomFileInput.addEventListener("change", () => {
  void uploadDicomFiles(Array.from(dicomFileInput.files || []));
});

seriesButton.addEventListener("click", () => {
  if (seriesButton.disabled || !state.study) return;
  renderSeriesDialog(state.study);
  if (typeof seriesDialog.showModal === "function") {
    seriesDialog.showModal();
  }
});

seriesDialogClose.addEventListener("click", () => seriesDialog.close());
seriesDialog.addEventListener("click", (event) => {
  if (event.target === seriesDialog) seriesDialog.close();
});

for (const [plane, controlsForPlane] of clippingRegistry.entries()) {
  controlsForPlane.start.addEventListener("input", () => {
    updateClippingBoundaryFromControl(plane, "start");
    volumeRenderingQuality.pulseInteraction("clipping");
  });
  controlsForPlane.end.addEventListener("input", () => {
    updateClippingBoundaryFromControl(plane, "end");
    volumeRenderingQuality.pulseInteraction("clipping");
  });
}

clippingResetButton.addEventListener("click", () => {
  resetPatientClipping();
  volumeRenderingQuality.pulseInteraction("clipping-reset");
});

mprClippingOverlayToggle.addEventListener("change", updateMprClippingOverlays);

for (const button of reconstructionModeButtons) {
  button.addEventListener("click", () => {
    if (button.disabled) return;
    requestReconstructionVisualizationMode(button.dataset.reconstructionMode);
  });
}

for (const input of reconstructionSurfaceSourceInputs) {
  input.addEventListener("change", () => {
    if (input.disabled) return;
    requestReconstructionSurfaceSourceSelection(
      input.dataset.reconstructionSurfaceSource,
      input.checked,
    );
  });
}

for (const button of reconstructionPresentationProfileButtons) {
  button.addEventListener("click", () => {
    requestReconstructionPresentationProfile(button.dataset.reconstructionPresentationProfile);
  });
}

volumeSurfaceBuild.addEventListener("click", () => {
  void requestVolumeSurfaceBuild();
});

volumeSurfaceClear.addEventListener("click", clearVolumeDerivedSurface);

volumeSurfaceRegionMode.addEventListener("change", () => {
  try {
    volumeSurfaceLayer.setRegionDisplayMode(volumeSurfaceRegionMode.value);
    syncDirectCtRegionControls();
  } catch {
    // Fail closed: disable the control rather than guess a region identity.
    volumeSurfaceRegionMode.disabled = true;
    volumeSurfaceRegionMode.value = "all";
    volumeSurfaceRegionStatus.textContent = "Region selection unavailable. Rebuild the full surface if needed.";
  }
});

volumeSurfaceIsovalue.addEventListener("change", () => {
  const snapshot = reconstructionVisualizationController?.snapshot();
  if ((snapshot?.mode === "surface" || snapshot?.mode === "combined")
      && state.reconstructionVisualization.surfaceSourceSelection["volume-derived"]
      && Number(volumeSurfaceIsovalue.value) !== volumeSurfaceLayer.current?.isovalue
      && !volumeSurfaceIsovalue.disabled) {
    void requestVolumeSurfaceBuild();
  }
});

volumeSurfaceIsovalue.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !volumeSurfaceBuild.disabled) {
    event.preventDefault();
    void requestVolumeSurfaceBuild();
  }
});

segmentationOverlayToggle.addEventListener("change", () => {
  state.segmentationOverlay.enabled = segmentationOverlayToggle.checked;
  if (state.segmentationOverlay.enabled) {
    scheduleMprRender();
  } else {
    clearAllSegmentationOverlays();
  }
});

segmentationOverlayOpacity.addEventListener("input", () => {
  state.segmentationOverlay.opacity = clamp(
    Number(segmentationOverlayOpacity.value) / 100,
    0,
    1,
  );
  segmentationOverlayOpacityValue.textContent = `${Math.round(state.segmentationOverlay.opacity * 100)}%`;
  for (const entry of mprRegistry.values()) {
    entry.overlayCanvas.style.opacity = String(state.segmentationOverlay.opacity);
  }
});

segmentation3dAppearance.addEventListener("change", () => {
  if (segmentation3dAppearance.disabled) return;
  const requested = segmentation3dAppearance.value;
  if (requested !== "scientific" && requested !== "anatomical") return;
  segmentation3dAppearanceMode = requested;
  syncSegmentation3dAppearance();
});

segmentationSurfaceToggle.addEventListener("change", () => {
  state.segmentationSurface.enabled = segmentationSurfaceToggle.checked;
  if (!state.segmentationSurface.enabled) segmentationSurfaceGate?.invalidate();
  segmentationSurfaceLayer.setEnabled(state.segmentationSurface.enabled);
  syncReconstructionVisualizationResources();
  if (state.segmentationSurface.enabled) void syncSegmentationSurface();
});

transferPresetSelect.addEventListener("change", () => {
  applyTransferPreset(transferPresetSelect.value);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferWindowCenter.addEventListener("input", () => {
  applyTransferAdjustments(transferWindowCenter);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferWindowWidth.addEventListener("input", () => {
  applyTransferAdjustments(transferWindowWidth);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferRangeLow.addEventListener("input", () => {
  applyTransferAdjustments(transferRangeLow);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferRangeHigh.addEventListener("input", () => {
  applyTransferAdjustments(transferRangeHigh);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferDensity.addEventListener("input", () => {
  applyTransferAdjustments(transferDensity);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferOpacitySoftness.addEventListener("input", () => {
  applyTransferAdjustments(transferOpacitySoftness);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferEdgeDefinition.addEventListener("input", () => {
  applyTransferAdjustments(transferEdgeDefinition);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferShadingStrength.addEventListener("input", () => {
  applyTransferAdjustments(transferShadingStrength);
  volumeRenderingQuality.pulseInteraction("transfer");
});

transferResetButton.addEventListener("click", () => {
  applyTransferPreset(state.volumeRendering.transferBasePresetId);
  volumeRenderingQuality.pulseInteraction("transfer");
});

renderQualityPolicy.addEventListener("change", () => {
  qualification?.resetWindow();
  volumeRenderingQuality.setPolicy(renderQualityPolicy.value);
  if (state.autoRotate) volumeRenderingQuality.beginInteraction("auto-rotate");
});

renderingModeSelect.addEventListener("change", () => {
  setMedicalRenderingMode(renderingModeSelect.value);
  volumeRenderingQuality.pulseInteraction("rendering-mode");
});

slicePlaneSelect.addEventListener("change", () => {
  state.volumeRendering.slicePlane = slicePlaneSelect.value;
  syncSliceRenderingControlsFromMpr();
  updateMprCrosshairOverlays();
  volumeRenderingQuality.pulseInteraction("medical-plane");
});

slicePosition.addEventListener("input", () => {
  const planeDescriptor = state.mpr.descriptor?.planes?.[state.volumeRendering.slicePlane];
  if (!planeDescriptor) return;
  const axisIndex = MPR_AXIS_INDEX[planeDescriptor.normal_axis];
  state.mpr.crosshairLpsMm[axisIndex] = Number(slicePosition.value);
  syncClippingControlsFromMpr();
  syncSliceRenderingControlsFromMpr();
  updateMprCrosshairOverlays();
  scheduleMprRender(35);
  volumeRenderingQuality.pulseInteraction("medical-plane-position");
});

slabThicknessSelect.addEventListener("change", () => {
  state.volumeRendering.slabThicknessPreset = slabThicknessSelect.value;
  slabCustomThicknessControl.hidden = slabThicknessSelect.value !== "custom";
  state.volumeRendering.slabThicknessMm = selectedSlabThicknessMm();
  syncSliceRenderingControlsFromMpr();
  volumeRenderingQuality.pulseInteraction("slab-thickness");
});

slabCustomThickness.addEventListener("input", () => {
  state.volumeRendering.slabThicknessPreset = "custom";
  state.volumeRendering.slabThicknessMm = Number(slabCustomThickness.value);
  syncSliceRenderingControlsFromMpr();
  volumeRenderingQuality.pulseInteraction("slab-thickness");
});

slabProjectionSelect.addEventListener("change", () => {
  state.volumeRendering.slabProjection = slabProjectionSelect.value;
  syncSliceRenderingControlsFromMpr();
  volumeRenderingQuality.pulseInteraction("slab-projection");
});

opacitySlider.addEventListener("input", () => {
  state.opacity = Number(opacitySlider.value) / 100;
  applyOpacity();
  volumeRenderingQuality.pulseInteraction("opacity");
});

const qualityInteractionControls = [
  ...Array.from(clippingRegistry.values()).flatMap((entry) => [entry.start, entry.end]),
  transferWindowCenter,
  transferWindowWidth,
  transferRangeLow,
  transferRangeHigh,
  transferDensity,
  transferOpacitySoftness,
  transferEdgeDefinition,
  transferShadingStrength,
  slicePosition,
  slabCustomThickness,
  opacitySlider,
].filter(Boolean);

for (const control of qualityInteractionControls) {
  const source = `control:${control.id || "range"}`;
  control.addEventListener("pointerdown", () => {
    volumeRenderingQuality.beginInteraction(source);
  });
  const endQualityInteraction = () => {
    volumeRenderingQuality.endInteraction(source);
  };
  control.addEventListener("pointerup", endQualityInteraction);
  control.addEventListener("pointercancel", endQualityInteraction);
  control.addEventListener("change", endQualityInteraction);
}

resetButton.addEventListener("click", resetWorkspace);

autoRotateButton.addEventListener("click", () => {
  state.autoRotate = !state.autoRotate;
  if (state.autoRotate && volumeLayer.root) {
    volumeRenderingQuality.beginInteraction("auto-rotate");
  } else {
    volumeRenderingQuality.endInteraction("auto-rotate");
  }
  autoRotateButton.classList.toggle("is-active", state.autoRotate);
  autoRotateButton.setAttribute("aria-pressed", state.autoRotate ? "true" : "false");
  autoRotateButton.textContent = state.autoRotate ? "Stop rotate" : "Auto rotate";
  requestViewerRender();
});

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(next, true);
});

function setViewerInteractionMode(mode) {
  const nextMode = mode === "pan" ? "pan" : "rotate";
  state.viewerInteractionMode = nextMode;
  if (nextMode === "pan") {
    controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
  } else {
    controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
  }
  controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
  rotateToolButton.classList.toggle("is-active", nextMode === "rotate");
  panToolButton.classList.toggle("is-active", nextMode === "pan");
  rotateToolButton.setAttribute("aria-pressed", nextMode === "rotate" ? "true" : "false");
  panToolButton.setAttribute("aria-pressed", nextMode === "pan" ? "true" : "false");
  renderer.domElement.style.cursor = nextMode === "pan" ? "grab" : "default";
  if (primaryInteractionHint) {
    primaryInteractionHint.textContent = nextMode === "pan" ? "Left drag - Pan" : "Left drag - Rotate";
  }
}

rotateToolButton.addEventListener("click", () => setViewerInteractionMode("rotate"));
panToolButton.addEventListener("click", () => setViewerInteractionMode("pan"));
fitViewButton.addEventListener("click", fitSavedView);
zoomInButton.addEventListener("click", () => zoomBy(0.82));
zoomOutButton.addEventListener("click", () => zoomBy(1.22));
fullscreenButton.addEventListener("click", async () => {
  try {
    if (document.fullscreenElement === viewerStage) {
      await document.exitFullscreen();
    } else if (viewerStage.requestFullscreen) {
      await viewerStage.requestFullscreen();
    }
  } catch (error) {
    console.error(error);
  }
});

function syncFullscreenControls() {
  const viewerActive = document.fullscreenElement === viewerStage;
  fullscreenButton.setAttribute("aria-pressed", viewerActive ? "true" : "false");
  fullscreenButton.classList.toggle("is-active", viewerActive);
  fullscreenButton.setAttribute("title", viewerActive ? "Exit fullscreen" : "Fullscreen");

  document.querySelectorAll("[data-mpr-fullscreen]").forEach((button) => {
    const plane = button.dataset.mprFullscreen;
    const entry = mprRegistry.get(plane);
    const active = Boolean(entry && document.fullscreenElement === entry.panel);
    const label = plane.charAt(0).toUpperCase() + plane.slice(1);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    button.classList.toggle("is-active", active);
    button.setAttribute("title", active ? `Exit ${plane} fullscreen` : `Expand ${plane} slice`);
    button.setAttribute(
      "aria-label",
      active ? `Exit ${label} slice fullscreen` : `Open ${label} slice fullscreen`,
    );
  });
}

document.addEventListener("fullscreenchange", () => {
  syncFullscreenControls();
  resize();
  if (state.mpr.descriptor) scheduleMprRender();
});

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  clearPatientVolumeRendering();
  volumeTextureManager.dispose();
  state.volumeRendering.textureResource = null;
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });
  } finally {
    window.location.assign("/login");
  }
});

function resize() {
  const width = Math.max(viewport.clientWidth, 1);
  const height = Math.max(viewport.clientHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  requestViewerRender();
  if (state.mpr.descriptor) {
    for (const [plane, entry] of mprRegistry.entries()) {
      const planeDescriptor = state.mpr.descriptor.planes[plane];
      configureMprSurface(entry, planeDescriptor);
    }
  }
}

window.addEventListener("resize", resize, { passive: true });
if (window.ResizeObserver) {
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(viewport);
  for (const entry of mprRegistry.values()) resizeObserver.observe(entry.view);
}

applyTheme(preferredTheme());
setVolumeAvailability(false);
applyOpacity();
setViewerInteractionMode("rotate");
resize();
void refreshAccountName();
void refreshLatestStudy();

const timer = new THREE.Timer();
timer.connect(document);
window.addEventListener("pagehide", () => {
  clearSegmentationWorkflowPoll();
  qualification?.dispose();
  volumeRenderingQuality.deactivate();
  volumeRayMarcher.dispose();
  volumeSurfaceLayer.dispose();
  segmentationSurfaceLayer.dispose();
  volumeTextureManager.dispose();
  timer.dispose();
}, { once: true });
function animate(timestamp) {
  timer.update(timestamp);
  const dt = Math.min(timer.getDelta(), 0.05);

  let shouldRender = viewerRenderRequested;
  const qualificationSampling = Boolean(qualification) && volumeLayer.available && Boolean(volumeRayMarcher.current);
  if (qualificationSampling) shouldRender = true;
  if (state.autoRotate) {
    anatomyGroup.rotation.y += dt * 0.32;
    shouldRender = true;
  }

  if (controls.update()) shouldRender = true;
  if (volumeRenderingQuality.update(timestamp)) shouldRender = true;
  const qualificationContinuous = qualificationSampling || state.autoRotate || volumeRenderingQuality.isInteractive();
  if (!shouldRender || !qualificationContinuous) qualification?.pause();
  if (shouldRender) {
    viewerRenderRequested = false;
    updateOrientationGizmo();
    surfaceLightingRig.syncToView(camera, controls.target);
    const qualificationStart = qualification ? performance.now() : 0;
    renderer.render(scene, camera);
    if (volumeLayer.available && volumeRayMarcher.current) {
      qualification?.recordFrame(timestamp, performance.now() - qualificationStart,
        state.volumeRendering.renderingMode, qualificationContinuous,
        document.visibilityState === 'visible');
    }
    if (
      volumeRenderingQuality.isInteractive()
      && lastRenderedTimestamp !== null
      && timestamp - lastRenderedTimestamp < 250
    ) {
      volumeRenderingQuality.recordFrameDuration(timestamp - lastRenderedTimestamp);
    }
    lastRenderedTimestamp = timestamp;
  }
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
