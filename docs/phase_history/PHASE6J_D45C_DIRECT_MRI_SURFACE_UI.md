# Phase 6J-D4.5C — Direct MRI surface UI and hybrid visualization integration

## Scope

Phase 6J-D4.5C exposes the already-qualified D4.5B Direct MR backend in the existing VoxelAtlas surface-source workflow. It does not introduce another surface transport, does not run segmentation, and does not assign anatomical identity to MRI intensity-derived geometry.

## Modality-aware direct surface contract

The internal source remains `volume-derived` and continues to use the existing authenticated VXVS Patient-LPS transport.

- CT remains **Direct CT**, uses native Hounsfield units, retains the 300 HU bone baseline, and keeps the existing CT-only broad-region presentation evidence.
- MR becomes **Direct MR**, uses `normalized_signal` from the D4.5B robust 2nd–98th percentile normalization and 0.75 mm physical Gaussian presentation smoothing, and exposes a normalized `(0, 1)` isovalue control with 0.50 as the baseline.
- Direct MR never requests the CT region-evidence endpoint.
- Both direct surface types remain independent of semantic segmentation.
- The original CT and MR canonical volumes remain immutable.

## Surface and Combined modes

The existing `volume-derived` source can be prepared on demand for either qualified CT or qualified MR studies. Surface and Combined mode behavior remains non-destructive and reuses resident geometry. Segmentation-derived surfaces remain an independent source and may coexist with Direct MR.

## UI clarification

The `?` contextual-help buttons beside the left-sidebar Volume, Surface, and Combined mode cards are removed by request. The mode cards and their concise availability/status text remain unchanged and fully clickable when qualified. Other contextual parameter help remains available.

## Safety and boundaries

- Direct MR is an MRI signal isosurface, not a brain/tissue segmentation.
- MRI is never presented in HU.
- Direct CT region evidence remains CT-only.
- No MRI inference is started by Direct MR.
- `clinical_validation=not_claimed` remains the product contract.
- Real-study visual/performance acceptance remains D4.5D.
## D4.5C manual-acceptance correction

The first real-MR UI pass exposed the legacy **Direct CT visibility** region control on MR because the control's `hidden` attribute was overridden by its grid-display CSS. The correction makes the visibility caption modality-aware and, more importantly, enforces the existing architectural boundary: CT broad-region visibility remains CT-only and is fully hidden for MR studies. Direct MR therefore exposes only the normalized MRI isovalue and non-semantic surface presentation controls. CT behavior is unchanged.
