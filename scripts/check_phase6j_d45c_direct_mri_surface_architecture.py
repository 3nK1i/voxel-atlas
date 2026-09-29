#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"{label}=FAIL")
    print(f"{label}=PASS")

backend = (ROOT / "backend/voxelatlas/volume_surfaces.py").read_text(encoding="utf-8")
app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
viewer = (ROOT / "web/js/volume-surface-viewer.js").read_text(encoding="utf-8")
index = (ROOT / "web/index.html").read_text(encoding="utf-8")
help_js = (ROOT / "web/js/parameter-help.js").read_text(encoding="utf-8")
css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
regions = (ROOT / "backend/voxelatlas/direct_ct_surface_regions.py").read_text(encoding="utf-8")

require('available = bool(backend_available)' in backend, "D45C_MR_UI_BACKEND_AVAILABLE")
require('"ui_activation": "enabled" if backend_available else "unavailable"' in backend, "D45C_UI_ACTIVATION_ENABLED")
require('MRI_SURFACE_INTENSITY_UNITS = "normalized_signal"' in backend, "D45C_NORMALIZED_SIGNAL_PRESERVED")
require('DEFAULT_CT_BONE_ISOVALUE_HU = 300.0' in backend, "D45C_CT_300HU_PRESERVED")
require('body_threshold: float = -500.0' in regions, "D45C_CT_REGION_POLICY_PRESERVED")

for identifier in (
    'volumeSurfaceSourceLabel', 'volumeSurfaceSourceBadge', 'volumeSurfaceIsovalueTitle',
    'volumeSurfaceIsovalueHint', 'volumeSurfaceIsovalueUnits', 'volumeSurfaceRegionControl',
    'volumeSurfaceRegionTitle',
    'volumeSurfaceContractNote', 'reconstructionSurfaceSourceNote',
):
    require(f'id="{identifier}"' in index, f"D45C_UI_ID_{identifier}")

require('descriptor?.source_modality === "MR" ? "Direct MR" : "Direct CT"' in app, "D45C_MODALITY_AWARE_SOURCE_LABEL")
require('"Normalized MRI isovalue"' in app and 'volumeSurfaceIsovalue.step = "0.01"' in app, "D45C_MR_NORMALIZED_CONTROL")
require('volumeSurfaceIsovalue.step = "10"' in app and '"CT isovalue"' in app, "D45C_CT_HU_CONTROL_PRESERVED")
require('descriptor.surface_isovalue_range' in app and 'this.descriptor.surface_isovalue_range' in viewer, "D45C_SURFACE_RANGE_BINDING")
require('units !== directSurfaceUnits(this.descriptor)' in viewer, "D45C_MODALITY_UNIT_BINDING")
require('this.descriptor?.source_modality !== "CT"' in viewer, "D45C_MR_CT_REGION_GUARD")
require('state.volumeSurface.descriptor?.source_modality === "CT"' in app, "D45C_CT_REGION_REQUEST_GUARD")
require('volumeSurfaceRegionControl.hidden = true' in app, "D45C_MR_REGION_UI_HIDDEN")
require('volumeSurfaceRegionTitle.textContent = `${label} visibility`' in app, "D45C_MODALITY_AWARE_VISIBILITY_LABEL")
require('.volume-surface-region-control[hidden]' in css and '#volumeSurfaceRegionStatus[hidden]' in css and 'display: none !important;' in css, "D45C_MR_REGION_HIDDEN_CSS_ENFORCED")
require('non-semantic visualization' in app and 'no segmentation required' in app, "D45C_NO_SEMANTIC_CLAIM")
require('canPrepareAutomaticDirectVolumeSurface' in app and 'ensureAutomaticDirectVolumeSurface' in app, "D45C_AUTOMATIC_DIRECT_VOLUME_PREPARATION")
require('sourceId === "volume-derived"' in app, "D45C_INTERNAL_SOURCE_ID_PRESERVED")
require('volumeSurfaceLayer.build(level)' in app, "D45C_EXISTING_BUILD_PATH_REUSED")

panel = index.split('id="reconstructionPanel"', 1)[1].split('</section>', 1)[0]
require('va-reconstruction-mode-help-row' not in panel, "D45C_MODE_HELP_WRAPPERS_REMOVED")
require('data-help-reconstruction-mode' not in panel, "D45C_MODE_HELP_BINDINGS_REMOVED")
require('"mode-volume": [' not in help_js and '"mode-surface": [' not in help_js and '"mode-combined": [' not in help_js, "D45C_MODE_HELP_ENTRIES_REMOVED")
require('.va-reconstruction-mode-help-row > .va-parameter-help' not in css, "D45C_MODE_HELP_CSS_REMOVED")
for mode in ('volume', 'surface', 'combined'):
    require(panel.count(f'data-reconstruction-mode="{mode}"') == 1, f"D45C_MODE_{mode.upper()}_PRESERVED")

print("PHASE6J_D45C_ARCHITECTURE_OK=YES")
