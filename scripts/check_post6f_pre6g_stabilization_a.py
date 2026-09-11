#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


html = (ROOT / "web/index.html").read_text(encoding="utf-8")
css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
direct_ct = (ROOT / "scripts/diagnose_post6f_direct_ct_surface.py").read_text(encoding="utf-8")
loading = (ROOT / "scripts/diagnose_post6f_study_loading.py").read_text(encoding="utf-8")

right = html.split('<aside class="right-panel panel"', 1)[1].split('</aside>', 1)[0]
order = [
    'id="volumeRenderingPanel"',
    'id="reconstructionVisualizationPanel"',
    'id="volumeSurfacePanel"',
    'id="segmentationWorkflowPanel"',
    'id="segmentationOverlayPanel"',
    'id="segmentationSurfacePanel"',
    'id="segmentationStructurePanel"',
    'id="directionalCutPanel"',
    'id="segmentationCorrectionPanel"',
]
positions = [right.index(marker) for marker in order]
require(positions == sorted(positions), "right-sidebar section order is not the stabilization contract")

volume = right[right.index('id="volumeRenderingPanel"'):right.index('id="reconstructionVisualizationPanel"')]
require(volume.index('id="renderQualityPolicy"') < volume.index('id="transferPresetSelect"'), "render quality must precede preset")
require(volume.index('id="transferPresetSelect"') < volume.index('id="renderingModeSelect"'), "preset must precede mode")
require(volume.index('id="renderingModeSelect"') < volume.index('id="transferWindowCenter"'), "mode must precede window/level")

for token in (
    '.sidebar-action-button',
    '.sidebar-action-button.is-primary',
    '.sidebar-action-button.is-secondary',
    'repeat(2, minmax(0, 1fr))',
):
    require(token in css, f"shared sidebar action styling missing: {token}")
for token in (
    'id="volumeSurfaceBuild" class="sidebar-action-button is-primary',
    'id="volumeSurfaceClear" class="sidebar-action-button is-secondary',
    '>Remove Surface</button>',
):
    require(token in html, f"Direct-CT action ergonomics missing: {token}")

for function_name in ("async function ensureCanonicalVolume", "async function restoreReadyPatientVolume"):
    section = app.split(function_name, 1)[1]
    section = section.split("async function ", 1)[0]
    require(section.index("void ensureVolumeRenderingFoundation();") < section.index("await ensureMprReady();"), f"GPU volume prestart missing in {function_name}")
    require(section.index("await ensureMprReady();") < section.index("await ensureVolumeRenderingFoundation();"), f"MPR/GPU join order changed in {function_name}")

for token in (
    "CANONICAL_VOLUME_MUTATION=NO",
    "ARBITRARY_LARGEST_COMPONENT_REMOVAL=NOT_APPLIED",
    "DIRECT_CT_CORRECTION_DECISION=REQUIRES_COMPONENT_EVIDENCE",
    "scipy.ndimage",
):
    require(token in direct_ct, f"Direct-CT diagnostic contract missing: {token}")
require("np.save(" not in direct_ct and "write_bytes(" not in direct_ct, "Direct-CT diagnostic must remain read-only")

for token in (
    "VOLUME_RENDERING_PREPARE_MS=SKIPPED_READ_ONLY",
    "SAMPLE_PAYLOAD_VERIFY_MS=SKIPPED_NON_SAMPLE",
    "FRONTEND_READY_STUDY_ORCHESTRATION=MPR_AND_GPU_VOLUME_PRESTARTED_IN_PARALLEL",
    "DIAGNOSTIC_MUTATION=NO",
):
    require(token in loading, f"loading diagnostic contract missing: {token}")
require("activate_study(" not in loading and "build_latest(" not in loading, "loading diagnostic must remain read-only")

print("POST6F_PRE6G_STABILIZATION_A_ARCHITECTURE_OK=YES")
print("RIGHT_SIDEBAR_ORDER=GLOBAL_TO_SPECIFIC")
print("VOLUME_RENDERING_QUALITY_FIRST=YES")
print("DIRECT_CT_ACTION_ERGONOMICS=SHARED_BUTTON_SYSTEM")
print("READY_STUDY_MPR_GPU_PRESTART=PARALLEL")
print("DIRECT_CT_DIAGNOSTIC=READ_ONLY_COMPONENT_EVIDENCE")
print("LOADING_DIAGNOSTIC=READ_ONLY_TIMING_EVIDENCE")
print("DIRECT_CT_SURFACE_CORRECTION=DEFERRED_UNTIL_REAL_STUDY_DIAGNOSTIC")
print("PHASE6G=NOT_STARTED")
