# Phase 6J-D4.5B — Direct MRI intensity-surface backend

## Scope

D4.5B extends the existing provider-neutral canonical-volume surface engine so a qualified MRI volume can produce a Patient-LPS display surface **without segmentation or model inference**.

This step is backend-only. The existing CT-facing web UI remains unchanged and Direct MR activation is explicitly deferred to D4.5C.

## Modality contracts

### CT

- source modality: `CT`
- source intensity units: `HU`
- surface parameter: native HU isovalue
- established 300 HU bone baseline remains unchanged
- Direct CT region evidence remains CT-only

### MRI

- source modality: `MR`
- source intensity units: `modality`
- surface parameter: normalized signal in the open interval `(0, 1)`
- default backend isovalue: `0.50`
- robust normalization profile: `robust_percentile_v1`
- robust bounds: 2nd to 98th percentile of the immutable canonical volume
- clipping: `[0, 1]`
- presentation smoothing: Gaussian `0.75 mm`, converted to per-axis index sigma from the Patient-LPS affine
- semantic identity: none

The MRI surface is therefore an intensity-derived visualization, not an anatomical segmentation and not a diagnostic claim.

## Geometry and provenance

The existing isolated `phase6d1_volume_surface_worker.py` remains authoritative for the VXVS transport and Patient-LPS mesh chain. CT and MRI both use the immutable canonical `volume.npy`, SHA256 binding, bounded geometry budgets, degenerate-face cleanup, canonical normals, and the existing isolated surface runtime.

MRI normalization parameters and the actual robust signal bounds are included in the worker report and surface provenance. The canonical MRI volume is never modified.

## Phase boundary

D4.5B deliberately reports the MRI backend as qualified while keeping the legacy CT-only UI unavailable for MRI. D4.5C will make the source label, normalized-signal control, status messages, region controls, and Surface/Combined behavior modality-aware.

## Safety

- `DIRECT_MR_SEGMENTATION_REQUIRED=NO`
- `MRI_INFERENCE=NOT_RUN`
- `SOURCE_VOLUME=IMMUTABLE`
- `DIRECT_CT_BEHAVIOR=PRESERVED`
- `DIRECT_MR_UI_ACTIVATION=DEFERRED_TO_D45C`
- `CLINICAL_VALIDATION=NOT_CLAIMED`
