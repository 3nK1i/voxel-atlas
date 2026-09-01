# Phase 3D-R2 Final Selection-State Harmonization

This correction is the final visual-state refinement for the Phase 3 workspace before closure.

## Scope

- Keep the accepted Phase 3D-R2 MPR presentation and six-button 3D viewer toolbar unchanged.
- Give the active anatomical layer the same illuminated blue selected treatment as the active Directional Cut button.
- Preserve disabled Full Volume, Brain and Skull + Brain states until patient-specific reconstruction provides those layers.
- Synchronize `aria-pressed` with the active anatomical layer so the visual state and accessibility state cannot drift.
- Refresh workspace CSS/JS cache markers for the final visual check.

## Non-goals

- No DICOM ingestion changes.
- No geometry, canonical-volume or MPR resampling changes.
- No patient-specific anatomy reconstruction.
- No fake activation of unavailable anatomy layers.

## Closure rule

Phase 3 may close after the complete Phase 3D-R2 final regression passes and manual validation confirms a centered representative slice in Axial, Coronal and Sagittal is displayed without presentation distortion/cropping, MPR interactions still work, the 3D toolbar works, and the active Skull layer visually matches the selected Directional Cut treatment.
