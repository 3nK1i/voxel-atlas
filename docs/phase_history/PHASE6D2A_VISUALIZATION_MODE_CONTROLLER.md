# Phase 6D2A — Reconstruction visualization-mode controller foundation

Expected continuation base: `e96f0138bbfe55963b7069680d8ead3d641d64d7` on `phase6-accurate-surfaces`.

Phase 6D2A begins the locked Phase 6D2 Volume / Surface / Combined work without redesigning the qualified Phase 6D1 or Phase 6C rendering paths.

## Controller contract

The browser now has a presentation-only reconstruction visualization-mode controller with three explicit mode identities:

- **Volume** — direct patient volume presentation.
- **Surface** — selected resident surface source(s), without the direct volume.
- **Combined** — direct patient volume plus selected resident surface source(s).

Visualization mode is deliberately independent from **surface source**. The controller recognizes two source identities without building, fetching, or mutating either one:

- `volume-derived` — the Phase 6D1 canonical-volume CT isosurface path;
- `segmentation-derived` — the existing Phase 6C refined segmentation-surface path.

A source has separate `available`, `resident`, and `selected` presentation state. A surface-capable mode becomes eligible only when at least one selected source is already resident. Switching mode therefore cannot trigger marching cubes, segmentation execution, surface generation, HTTP traffic, or provenance changes.

The controller produces a deterministic visibility plan rather than directly mutating Three.js objects. If a currently required resource becomes unavailable, it falls back conservatively to an eligible presentation state; a study/reset boundary clears all source state.

Repository inspection also found an important 6D2B integration constraint: `PatientSegmentationSurfaceLayer.setEnabled(false)` aborts pending surface requests. Visualization-mode switching must therefore use a new non-destructive presentation-visibility path instead of reusing the semantic Show toggle / `setEnabled(false)` lifecycle. Resident geometry and pending explicit user work must not be discarded merely because the user switches to Volume mode.

## Deliberate 6D2A boundary

6D2A is the state/controller foundation. It does **not** yet replace the Phase 6D1 surface-only preview in the visible workspace and does not wire the mode controller to the direct-volume or surface-layer visibility. That integration is Phase **6D2B**. Phase **6D2C** adds the full Combined/source presentation integration, and Phase 6D2D closes study/reset/error qualification.

No Phase 6E Fidelity/Presentation profile, lighting/material overhaul, Phase 6F advanced structure grouping/exploded view, geometry algorithm change, automatic semantic segmentation, or clinical interpretation is introduced here.

Clinical validation is not claimed.
