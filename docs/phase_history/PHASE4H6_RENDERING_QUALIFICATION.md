# Phase 4H6 - Rendering qualification and compact clipping typography

## Baseline and delivery boundary

- Target branch: `phase4-volume-rendering`.
- Required upstream H5 commit: `cb56d355fab335e4075899f2304c22294a7eaaf5`.
- H5 automated/manual acceptance and commit/push were confirmed by the user.
- Development here uses a separate synthetic Git baseline of the delivered H5
  content, not a claim of access to upstream Git history. The delivery apply
  script checks the real upstream SHA plus the SHA256 of every replaced file.
- This document began as the pre-acceptance qualification plan. The plan was
  completed on 2026-09-07 and the accepted evidence is recorded in
  `PHASE4_VOLUME_RENDERING_CLOSURE.md`.

## Changes

- Clipping plane titles, percentages, directions and LPS values: 12 px -> 11 px.
  Contrast, slider dimensions, hit targets and other interface fonts are unchanged.
- All three clipping axes now start enabled at their complete 0-100% physical
  ranges. This is visually and numerically the full patient volume, while making
  both handles immediately available. Reset clipping restores the same enabled
  full-range state; an individual axis can still be unchecked explicitly.
- Exact 0%/100% MPR boundaries are display-inset by one CSS pixel so their
  centered SVG strokes are not clipped at the image edge. Projection geometry
  and the actual Patient LPS clipping planes remain exact and unchanged.
- Validate replacement presentation/transfer/clipping/slice descriptors before
  disposing the current ray-marcher resource. Invalid geometry no longer destroys
  a valid resource at the renderer API boundary. This does not promise retaining
  the previous study through the entire asynchronous application load workflow.
- `?qualification=phase4h6` on localhost enables bounded engineering diagnostics.
  No public-host activation, new backend endpoint, dependency, patient data
  transmission, source mutation or persistent browser storage is introduced.
- Each mode retains at most 600 CPU-submission samples and 600 continuous-frame
  interval samples. Hidden-tab/idle/mode-switch gaps are excluded; actual slow
  foreground frames are retained. Policy and study transitions reset the window.
  Runtime fault counters persist across study changes.
- Four fixed capture slots prevent unbounded report growth. Reports contain
  modality, dimensions, quality, canvas size, resource counts and timing summaries;
  no images, patient/study identifiers, paths, revisions, credentials or raw errors.

## Evidence limitations

CPU submission time is NOT GPU execution time. Foreground rendered-frame intervals
are an observed responsiveness proxy, NOT a certified FPS benchmark. Three.js
texture/geometry/program counts detect some resource growth; they are NOT VRAM
bytes and do not prove the absence of all browser/driver leaks. GPU memory can
also be inspected locally with the browser's GPU tools or `nvidia-smi` if available.

H6 does not change ray-marching mathematics, source resolution or medical accuracy.
Clinical correctness, segmentation accuracy and measurement qualification are not
claimed. A successful H6 run qualifies only the tested hardware/browser/studies.

## Test-first evidence

New tests first failed for missing H6 diagnostics and the 12 px typography. A
separate lifecycle regression then demonstrated that an invalid replacement
disposed the current valid renderer. The narrow fix passes that regression.

Deterministic probes cover 20,000 diagnostic frames with bounded storage,
foreground stalls/idle/visibility handling, localhost gating, privacy allowlisting,
fault persistence, listener cleanup, and 100 alternating CT/MR renderer cycles
with all six modes, all slice planes and slab methods. Geometry/material ownership
balances, roots are removed, and control updates do not re-upload textures.
Those lifecycle probes use test doubles, not a physical GPU. Existing texture
transport, clipping, source-safety and adaptive-quality regressions also run.

The optional Playwright H5 browser probe uses the actual updated CSS/overlay
glue with synthetic images. This environment lacks a Chromium executable, so
live browser execution is not reported as passed here. Its syntax is checked.

## Local automated validation

```bash
source .venv/bin/activate
bash scripts/run_phase4h6_checks.sh
git diff --check
```

Required result: `PHASE4H6_AUTOMATED_CHECKS_OK=YES` and `TEST_RC=0`.
`PC_RUNTIME_AND_VISUAL_ACCEPTANCE=PENDING` is deliberate: unit checks cannot
approve the target GPU or the visual result. Logs are retained under the reported
`CHECK_LOG_DIR`. No full real-study or browser claim is inferred from syntax tests.

## Focused PC qualification (approximately 8-12 minutes)

1. Start the local server normally, sign in, then explicitly open
   `http://127.0.0.1:8000/workspace?qualification=phase4h6` in the same tab.
   The login redirect may drop the query, so open this URL AFTER signing in.
   Do not use the production hostname. Use approved sample studies only.
2. In DevTools Console, `typeof window.voxelatlasH6` must return `"object"`.
   Keep the same browser window, zoom, viewport, theme and quality throughout
   all four captures. Undock DevTools to avoid changing viewport dimensions.
3. Warm up once: load your selected CT and then MR. In both, briefly enable all
   clipping axes and visit all six modes, so lazy overlays and shader programs
   have been initialized before comparing resource counts.
4. Collect the four slots below IN ORDER, reloading the indicated sample through
   the app for each slot. Use the same CT and MR samples on the repeat cycle.

| Slot | Study | Console command after the exercise |
| --- | --- | --- |
| CT-1 | Your chosen CT sample | `window.voxelatlasH6.capture('CT-1')` |
| MR-1 | Your chosen MR sample | `window.voxelatlasH6.capture('MR-1')` |
| CT-2 | Same CT sample | `window.voxelatlasH6.capture('CT-2')` |
| MR-2 | Same MR sample | `window.voxelatlasH6.capture('MR-2')` |

For EACH slot:

- Wait for rendering ready and set quality to Balanced. Start a fresh timing
  window with `window.voxelatlasH6.resetWindow()` (this does not clear faults).
- Enable all three clipping axes, narrow both ends to about 20-80%, rotate/zoom,
  and check the MPR overlays track the retained region without moving crosshairs.
- Reset clipping. Turn Auto rotate ON and spend about 10 seconds in EACH mode:
  DVR, MIP, MinIP, Average Intensity, Slice, Thick Slab. Keep the tab foreground.
  Each mode needs at least 30 continuous rendered-frame intervals.
- In Slice/Thick Slab, also visit axial/coronal/sagittal; in Thick Slab try MIP,
  MinIP, Average and thickness 5/20 mm. A projection is not expected to look like
  a polished surface. Check responsiveness, orientation, artifacts and controls.
- Finish in DVR, turn Auto rotate OFF, wait two seconds for quality to settle,
  then run the slot's capture command. Do not change quality mid-capture (it
  intentionally resets the timing window). Do not refresh the browser between
  slots, because captures and fault counters are intentionally memory-only.

Once per CT/MR pair, check overlay toggle/reset/outside-ROI notice and resize or
fullscreen. Restore your original viewport BEFORE capturing. Confirm the 11 px
labels remain legible and separated in both themes at normal browser zoom.
After the last slot, inspect the console for new errors and run:

```javascript
window.voxelatlasH6.download()
```

This downloads `voxelatlas_phase4h6_runtime_evidence.json`. If the browser adds
`(1)` to a duplicate filename, use that exact newer filename below; do not read
an older report accidentally. Keep runtime evidence OUTSIDE the repository.

```bash
python scripts/check_phase4h6_evidence.py \
  $HOME/Downloads/voxelatlas_phase4h6_runtime_evidence.json
```

Expected: `PHASE4H6_RUNTIME_EVIDENCE=PASS`. The report itself retains
`PENDING_REVIEW`; it never auto-certifies the release.

## Acceptance and stop conditions

- All automated checks pass; four captures cover CT/MR, repeats and all modes.
- No runtime error, rejection, context loss or detected shader compilation error.
- After warm-up, matched-study texture/geometry/program/overlay counts do not
  grow; overlay nodes remain at most 30. Growth is a review blocker, not automatic
  proof of a leak. Compare at matching viewport and settled quality.
- On Balanced, each mode's continuous foreground frame-interval p95 must be
  <= 100 ms as a minimum responsiveness gate. This is an engineering review
  threshold, not a claim of 30/60 FPS. If it fails, retain the evidence and review
  the hardware/workload; do not silently relax the threshold or drop slow frames.
- Visual checklist above passes with no freezes, stale-study images, incorrect
  clipping, unreadable labels, or new console errors.
- A short Max-quality visual trial may be done separately AFTER exporting the
  Balanced evidence; it must not overwrite the comparable capture windows.

Then review exact files, patient-data staging safety and diff; commit/push H6;
verify clean matching local/remote SHAs; prepare a fresh guarded combined H5/H6
deployment with backup, readiness retry and rollback. Deployment and final
Phase 4 closure require that subsequent evidence, not just this package.

## Closure record

- Automated qualification: run by `run_phase4h6_checks.sh`.
- Target-PC runtime report: PASS.
- Target-PC visual acceptance: PASS.
- H6 upstream commit/push: PASS.
- Final H5/H6 production deployment and public smoke test: PASS.
- Final deployed release: `ff1b77727dc9b8efc1ba7a66d74861cffddcc5b9`.
- Runtime evidence SHA256:
  `415fbcbf3dc636137db775099a4562f6ed623448ceaf9e4053db2e8a4007137f`.
- Clinical validation: NOT CLAIMED.
