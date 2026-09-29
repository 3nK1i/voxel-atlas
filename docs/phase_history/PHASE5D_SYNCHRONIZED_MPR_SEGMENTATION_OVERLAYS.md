# Phase 5D - Synchronized MPR Segmentation Overlays

## Status

Implemented on `phase5-segmentation` from the accepted Phase 5C base
`abb7e2f40a6dc3b9f0d228d478c9847ddc439e59`.

Phase 5D is the first phase that presents the qualified segmentation result in
the actual VoxelAtlas application. It does not run inference, alter canonical
voxels, edit labels, or claim clinical validation.

## Locked contract

- Select a label map only when its immutable `source_study_id` equals the
  currently loaded study.
- Reuse the existing MPR plane descriptors so the grayscale image and overlay
  have identical Patient-LPS position, dimensions, physical aspect, and
  orientation.
- Sample categorical labels with nearest-neighbor interpolation only.
- Keep label zero fully transparent and assign stable display colors to nonzero
  labels.
- Return raw RGBA8 through authenticated, `no-store` endpoints with explicit
  width, height, plane, index, position, and label-map identity headers.
- Composite on a separate non-interactive canvas so crosshair, wheel, pointer,
  fullscreen, and window/level interactions remain owned by the existing MPR.
- Preserve the grayscale MPR if overlay discovery or rendering fails.

## HTTP surface

- `GET /api/studies/latest/segmentation-overlay`
- `GET /api/studies/latest/segmentation-overlay/{plane}`

The descriptor returns `ready: false` when the current study has no canonical
label map. A requested label map from another study is rejected rather than
silently displayed.

## Browser presentation

Each axial, coronal, and sagittal surface now contains a second canvas registered
to the same contained image rectangle. The right panel exposes a truthful
availability message, a Show toggle, and a 0-100% overlay-opacity control.

Phase 5E owns label names, search, anatomical grouping, show/hide per structure,
isolation, per-structure color, selection, and per-structure opacity.

The Phase 5D regression excludes three historical Phase 4 assertions whose sole
purpose was to require segmentation UI to be absent before Phase 5. All other
tests in those modules and the complete remaining regression are preserved.

## Qualification

Run:

```bash
bash scripts/run_phase5d_checks.sh

python scripts/qualify_phase5d_real_segmentation_overlay.py \
  --data-dir /home/eiatech/Desktop/voxel-atlas/data \
  --label-map-id map-c2c950145b6f01686eb9fb4d870bf53f
```

Then open the existing public Head and Neck CT in the application and verify the
colored overlay remains registered while moving the shared crosshair and wheel
through all three planes. This is non-clinical engineering visualization;
clinical validation remains not claimed.
