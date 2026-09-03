# Phase 4E: Multi-plane Patient-space Clipping

## Outcome

The direct patient-volume ray marcher now supports simultaneous Axial, Coronal, and Sagittal clipping. These controls section the actual uploaded CT/MR voxels and do not create segmentation or surface geometry.

## Medical coordinate contract

- Axial clipping moves on Patient LPS Z and retains Inferior or Superior.
- Coronal clipping moves on Patient LPS Y and retains Anterior or Posterior.
- Sagittal clipping moves on Patient LPS X and retains Right or Left.
- All displayed positions are physical DICOM Patient LPS millimetres.
- Each clipping position and the corresponding MPR crosshair coordinate are the same state.

## GPU contract

The renderer transforms the local ray origin and direction into Patient LPS space using the qualified texture-to-patient affine. Each enabled half-space narrows the entry/exit interval before voxel sampling. The three independent half-spaces may be enabled in any combination, and clipping remains correct when the presentation volume rotates because the clipping definition stays in patient coordinates.

## Interaction contract

Each plane provides an enable control, a physical-position slider, and a retained-side selector. Moving a clipping plane updates the synchronized MPR crosshair and all three MPR views. Moving the MPR crosshair or stepping an MPR slice updates the clipping positions. Reset disables all planes, restores the minimum-coordinate retained sides, recenters the shared intersection, and preserves the active volume, transfer preset, density, and opacity behavior.

## Narrow Phase 4D2 label correction

The visible CT preset label `Lung` is now `Low-Density CT`, with anatomy-neutral explanatory copy. The stable internal preset ID remains `ct-lung`, so this correction does not change persisted or programmatic preset identity.

## Deferred work

Adaptive sampling quality, interaction-time resolution scaling, and large-study performance qualification remain Phase 4F. Sample dataset catalog integration remains Phase 4G.
