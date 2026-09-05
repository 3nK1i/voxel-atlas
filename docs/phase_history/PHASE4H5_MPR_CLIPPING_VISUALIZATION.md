# Phase 4H5 - MPR clipping visualization and readable controls

## Baseline and scope

- Target branch: `phase4-volume-rendering`.
- Required upstream H4 base: `90244e576f1a278c4b224c2fdd171c27f9d56f60`.
- H5 development uses a separate local content baseline, matched byte-for-byte
  against every file in the verified delivered H4 package. Its local synthetic
  Git commit is not the upstream release SHA.
- Production remains on H4. Commit/push H5 after local acceptance; deploy only
  after H6 qualification. No production script or service changes in H5.

## Behavior

- Dashed amber lines show enabled clipping boundaries in the physical image
  rectangle; translucent amber shading marks excluded regions.
- Four disjoint shading strips avoid double shading at ROI corners.
- A displayed slice outside its normal-axis clipping interval receives light
  full-image shading and an explicit `Slice outside clipping ROI` label. The
  reference image is not blanked or modified.
- `Show clipping on MPR` hides the annotation only, not 3D clipping. Reset
  clipping disables all axes and hides overlays without moving the crosshair.
- Physical ranges come from the same `clippingRequest()` as the ray marcher.
  Coronal/sagittal vertical reversal follows the backend MPR descriptor.
- Overlays use the accepted rendered slice position, not a continuous crosshair
  whose asynchronous image is still pending. A previous study's descriptor
  cannot annotate a new study. Non-ready MPR panels hide annotations.
- SVG shares the source image's physical-fit rectangle; resize/fullscreen use
  the existing fitting function, with an observer on each MPR viewport.
- DOM node pools are reused during dragging. No extra MPR HTTP requests,
  canvas pixel writes, source voxel edits, texture uploads, or shader changes.
- Percentages, anatomical endpoint labels, and LPS millimetre values are 12 px
  with stronger contrast; slider accessibility text includes direction and mm.

## Validation

Test-first: three new H5 tests failed before implementation (missing projection
module, missing UI integration, undersized labels). The geometry/behavior probe
covers all axes, reversed directions, combined ROI, exact boundary inclusion,
normal-axis exclusion, invalid data, disabled/reset states, non-mutating inputs,
asynchronous accepted-image binding, and constant DOM size across 1,000 updates.

Run `bash scripts/run_phase4h5_checks.sh` for H5 checks, H4 and earlier probes,
full Python unit regression, syntax and whitespace validation. Logs are kept
in a reported temporary directory for troubleshooting.

Optional browser check: `node scripts/check_phase4h5_browser.mjs` requires
Playwright and Chromium. It uses the actual workspace HTML/CSS, clipping
functions and event handlers, with synthetic images and a stubbed 3D renderer.
It checks layout at 1920/1366/768/390 px in light/dark themes, overlay image
registration, control events, reset/toggle, and unchanged canvas pixels.
This is not a substitute for CT/MR or GPU validation on the user's machine.

Local evidence: all 247 Python tests passed, as did H4 and historical checks.
Browser execution was blocked by the missing Chromium binary; the browser
download timed out. Browser runtime and actual CT/MR visual acceptance remain
pending; only the optional browser probe's syntax was validated here.

## Focused manual acceptance

1. Open localhost, hard-refresh, load one CT and one MR sample in turn.
2. Confirm all percentage/direction/mm labels are legible without overlaps.
3. Enable sagittal bounds: vertical lines appear in axial/coronal. Enable axial
   bounds: horizontal lines appear in coronal/sagittal. Coronal bounds affect
   axial horizontally and sagittal vertically on screen (line orientation).
4. Narrow all axes. Verify excluded shading follows the same 3D ROI, without
   moving the crosshair, changing MPR images, or requesting slices on drag.
5. Scroll a slice beyond its normal-axis bounds: the outside-ROI notice appears
   after the new image arrives. Return inside: the notice clears.
6. Hide/show MPR clipping overlays: only annotations change. Reset clipping:
   all annotations disappear and full 3D volume returns; crosshair stays put.
7. Resize and enter/exit MPR fullscreen; annotations stay image-registered.
8. One brief compatibility check: switch DVR/MIP/Slice/Thick Slab, verify normal
   behavior, and check that the browser console has no new errors.

On any failure, stop before commit or H6 and retain the logs/screenshot. No H5
production deployment is requested.
