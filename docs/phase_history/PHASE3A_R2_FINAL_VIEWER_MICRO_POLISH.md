# Phase 3A-R2 - Final Viewer Micro-Polish

This step closes the small presentation issues observed during Phase 3A-R1 manual validation. It does not modify DICOM ingestion, storage, authentication, reconstruction state, or medical metadata behavior.

## Scope

- extend anatomy opacity to the full 0-100% range with direct semantics: 100% is fully opaque and 0% hides the layer
- keep the accepted solid 100% clinical material while using front-face rendering below 100% to reduce transparent back-face/internal-surface noise in the current demo mesh
- keep depth testing and writing enabled so transparent mode behaves as a clean surface fade rather than an x-ray preset
- preserve the accepted approximately 15% smaller initial skull framing
- preserve the authoritative `web/assets/logo.png` bytes and remove the visible square-corner effect with circular CSS clipping, avoiding a second or regenerated logo asset
- make the anatomical S/A/R/L gizmo background transparent
- align the gizmo bottom edge with the interaction helper on desktop
- enlarge the desktop gizmo modestly and add color-matched arrowheads to all four anatomical axes
- keep gizmo synchronization with camera orientation and anatomy auto-rotation

## Opacity contract

- 100%: fully opaque clinical surface
- intermediate values: progressively transparent surface
- 0%: anatomy layer hidden

The control is named Opacity, so its direction is intentionally not inverted.

## Logo contract

The authoritative runtime logo image is not edited in this step. CSS clips its opaque square canvas to a circle so the corners blend with the workspace background while preserving the qualified logo asset and its existing fingerprint.

## Non-goals

This step does not remesh the temporary demo skull, add volume/MPR data, add patient-specific anatomy, or validate DICOM slice geometry. Those remain subsequent medical-pipeline steps.
