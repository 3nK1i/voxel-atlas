# Phase 6I-B1 — Direct CT automatic mode preparation

## Scope and baseline

Narrow Phase 6I-B substep following committed Phase 6I-A GitHub checkpoint
`f08800209ced3b4f5a80340a8798bd4d2a86dfdd` on
`phase6-accurate-surfaces`. The source candidate was reconstructed for audit by
verifying and overlaying the previously supplied 6I-A r2/r3 patch manifests on
the 495-file working-tree handoff. This is a source-only handoff, not a Git
repository nor proof of browser/real-study acceptance.

## Functionality

- Hide obsolete Build Surface / Remove Surface UI buttons while preserving their
  IDs for legacy source contracts; no hidden UI action is required for normal
  Direct CT Surface/Combined operation.
- In Volume, present only the volume; preserve resident surface geometry.
- In Surface or Combined, reuse already selected resident geometry. If a
  qualified matching-study Direct CT source is selected but not resident,
  explicitly prepare that source on demand, without running segmentation.
- A selected resident segmentation surface may appear immediately while an
  independently selected Direct CT surface is prepared in the background.
- Coalesce concurrent Direct CT preparation for the same active study; the
  last requested visualization mode wins. Volume switching invalidates pending
  mode intent but does not dispose/cancel reusable in-flight geometry.
- A study reset invalidates old mode intent and its build promise; the existing
  layer owns the real request abort and cleanup. Late volume-surface descriptor
  responses cannot overwrite the new study's descriptor or clear its request.
- Direct CT source checkbox remains selectable before geometry is resident,
  even after being unchecked; CT isovalue change regenerates the selected
  Direct CT surface when already viewing Surface or Combined.

No backend API, segmentation workflow, source DICOM/volume, labeling, Patient-LPS
geometry, clipping, surface fallback, or qualification logic is changed.

## Explicitly deferred within Phase 6I-B

Segmentation-specific on-demand surface presentation for an already activated
label map when no segmentation mesh is resident, and final Use Segmentation
control styling. Neither a rendering-mode switch nor this substep initiates
TotalSegmentator processing. Finish those in 6I-B2 before closing all of 6I-B.

## Acceptance and regression

Run `bash scripts/run_phase6i_b1_checks.sh` in the real development environment.
The source-only snapshot omits local/secret-bearing `passwords.py`, environments,
and patient studies, so full backend tests, browser WebGL, and real-study
qualification must be run locally. The older 6D2B expectation that Combined is
permanently deferred and the older 6D2D manual Build Surface instruction were
updated to the new 6I-B scope; their other historical safety assertions remain.

Manual local preview: with a qualified CT loaded and no resident Direct CT
surface, choose Surface and wait for the surface; switch Volume then Surface
again and confirm instant reuse; choose Combined and confirm CT volume + surface.
Switch Volume while a first surface builds, then Surface again; the latest mode
intent must win without another build. If segmentation is already activated,
confirm no segmentation job starts from mode switches. Confirm the Direct CT
source checkbox can be unchecked and rechecked before build; check CT isovalue
change while in Surface. Confirm a new study cannot display previous-study
surface. Check browser console/network errors without sharing patient details.

This is a non-clinical development milestone. No production changes, Git
closure, or full Phase 6I-B acceptance are claimed by the patch itself.
