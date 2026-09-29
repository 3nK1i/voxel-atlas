# Phase 6D2D — Reset, study-change, error-state qualification and Phase 6D2 closure

Authoritative Phase 6D2 base: `e96f0138bbfe55963b7069680d8ead3d641d64d7`.

This is a continuation of the validated Phase 6D2A / 6D2B / 6D2C stack, not a redesign.

## Scope

- Close the Volume / Surface / Combined visualization-mode workflow introduced across 6D2A, 6D2B and 6D2C.
- Relocate the three mode selectors to the left **Reconstruction** section as compact cards with distinct local SVG icons.
- The green check denotes the one active, available reconstruction mode only; it is not a generic readiness indicator.
- Keep detailed **Surface sources** controls in the right 3D View panel. Their selections apply in Surface and Combined modes and reuse resident geometry.
- Reset returns presentation to Volume when a patient volume is available without clearing or rebuilding resident surface geometry.
- A patient study change resets visualization mode and per-study source preferences to deterministic defaults before the new study becomes active.
- Removed or unavailable final surface sources reconcile Surface / Combined back to Volume when volume remains available.
- A failed Direct CT surface build does not force a mode change and does not trigger an implicit retry or replacement build.
- Mode/source changes remain presentation-only: no surface build, geometry fetch, segmentation auto-start, cancellation, or provenance mutation.
- Phase 6D1 remains the authoritative Direct CT surface extraction path with the editable 300 HU baseline.

## Boundaries

Phase 6E Fidelity / Presentation profiles are not enabled here. Lighting/material-profile work remains Phase 6E.
Phase 6F advanced structure interaction, groups, clipping and exploded views are not enabled here.

Clinical validation is not claimed. This phase qualifies application behavior and visualization state management only.
