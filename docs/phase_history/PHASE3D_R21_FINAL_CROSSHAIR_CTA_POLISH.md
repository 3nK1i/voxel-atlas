# Phase 3D-R2.1 - Final MPR Crosshair & DICOM CTA Polish

## Scope

This is a presentation-only closure correction on top of the validated Phase 3D-R2 state.

- register MPR crosshair overlays to the actual physically contained canvas rectangle
- clip the vertical and horizontal crosshair lines to that image rectangle
- ignore pointer presses in black letterbox margins instead of snapping them to an anatomy edge
- preserve patient-space crosshair synchronization, slice navigation, W/L, physical aspect, and orientation labels
- give Upload/Replace DICOM the same premium blue clinical visual language as the accepted active controls, with action-specific hover/press feedback
- no DICOM parsing, geometry, canonical volume, MPR sampling, or 3D anatomy changes

## Acceptance

Crosshair intersections must visually land on the same displayed patient coordinate in Axial, Coronal, and Sagittal views, and no crosshair line may extend beyond the displayed patient-image rectangle into letterbox margins. The DICOM CTA remains clearly actionable rather than state-selected.
