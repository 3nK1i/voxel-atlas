# Phase 6D2B — Non-destructive Volume / Surface transitions

Expected continuation base: `e96f0138bbfe55963b7069680d8ead3d641d64d7` on `phase6-accurate-surfaces`, with the validated Phase 6D2A controller files applied but not staged.

Phase 6D2B wires the Phase 6D2A presentation-only controller into the real VoxelAtlas workspace without redesigning the validated Phase 6D1 CT isosurface path or Phase 6C refined segmentation surfaces.

## Visible mode integration

The right-side 3D controls now expose **Volume**, **Surface**, and **Combined** mode identities. In this incremental step, Volume and Surface are active when their required resident resources are available. **Combined remains visibly disabled until Phase 6D2C**, where the simultaneous volume-plus-surface presentation and source integration are qualified.

- **Volume** shows the qualified direct patient volume and hides resident surface groups presentation-only.
- **Surface** hides the direct patient volume and shows already-resident selected surface sources.
- A mode change does not build, fetch, clear, dispose, or regenerate geometry. Building a Phase 6D1 volume-derived surface remains an explicit user action and does not implicitly switch visualization mode.

The Phase 6D1 CT bone baseline remains editable and defaults to **300 HU**. No geometry filtering, intensity rewriting, smoothing, or decimation is introduced.

## Non-destructive segmentation visibility

Repository inspection showed that `PatientSegmentationSurfaceLayer.setEnabled(false)` aborts pending explicit surface requests. Phase 6D2B therefore adds `setPresentationVisible(...)` to both surface layers. This path changes only the Three.js group visibility and requests a render; it does not abort controllers, clear queues, dispose resident geometry, or mutate provenance. The existing segmentation **Show** toggle keeps its original lifecycle semantics and remains separate from visualization mode.

If a resident surface disappears while Surface mode is active and no other selected resident surface remains, the Phase 6D2A controller falls back deterministically to Volume when a direct volume is available. Study/reset teardown resets the mode controller with the rest of the 3D patient state.

## Deliberate boundary

Phase **6D2C** will enable Combined mode and complete simultaneous volume-plus-surface source presentation. Phase **6D2D** remains responsible for the final study-change/reset/error qualification and closure.

No Phase 6E Fidelity/Presentation profile or lighting/material overhaul is introduced. No Phase 6F advanced grouping, clipping/isolation expansion, exploded view, or export behavior is introduced. Semantic segmentation is never auto-started by a visualization-mode change.

Clinical validation is not claimed.
