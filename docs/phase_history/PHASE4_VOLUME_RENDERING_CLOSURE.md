# Phase 4 - Volume Rendering Closure

## Decision

Phase 4 direct patient-volume rendering is formally accepted as an engineering
and research implementation. Automated regression, target-PC runtime evidence,
production deployment, health checks, and manual visual acceptance passed.

This closure does not claim clinical validation, diagnostic fitness, certified
performance, segmentation accuracy, or measurement accuracy.

## Accepted release

- Branch: `phase4-volume-rendering`
- Final deployed release:
  `ff1b77727dc9b8efc1ba7a66d74861cffddcc5b9`
- Dual-intensity implementation:
  `a648d2b633afc1031c65daa73de9638b81b97429`
- Closure date: `2026-09-07`
- Immutable closure tag:
  `phase4-volume-rendering-closed-20260907`
- Production URL: `https://em.eiatech.ma`
- Production service: `voxelatlas.service`
- Production data directory: `/var/lib/voxelatlas`
- Preserved production sample count: `4`
- Rollback backup:
  `/var/backups/voxelatlas/pre-phase4h6-final-update-20260907T103701Z.tar.gz`

The closure commit and tag contain documentation and validation only. The
deployed application release remains the exact Git object identified above.

## Automated acceptance

The final `scripts/run_phase4h6_checks.sh` run reported:

- H6 qualification and evidence tests: PASS
- H5 and full previous regression: PASS
- repeated renderer lifecycle probe: PASS
- application, ray marcher, diagnostics, and probe JavaScript syntax: PASS
- Python compile: PASS
- shell syntax: PASS
- diff whitespace: PASS
- `PHASE4H6_AUTOMATED_CHECKS_OK=YES`
- `TEST_RC=0`

## Target-PC runtime evidence

- Evidence file: `voxelatlas_phase4h6_runtime_evidence.json`
- Evidence SHA256:
  `415fbcbf3dc636137db775099a4562f6ed623448ceaf9e4053db2e8a4007137f`
- Schema/build: `voxelatlas-phase4h6-v1` / `phase4h6`
- Quality policy: Balanced
- Captures: CT-1, MR-1, CT-2, MR-2
- Modes per capture: DVR, MIP, MinIP, Average, Slice, Thick Slab
- Qualified slot/mode combinations: `24`
- Continuous-frame interval count: minimum `63`, maximum `600`
- Continuous-frame interval p95: `16.7` to `16.8` ms
- Acceptance limit: p95 at most `100` ms with at least `30` intervals
- Window errors: `0`
- Unhandled rejections: `0`
- WebGL context losses: `0`
- Detected shader errors: `0`
- Repeated CT/MR dimensions and viewport: stable
- Geometry, texture, program, and overlay-node counts: stable
- Evidence checker: `PHASE4H6_RUNTIME_EVIDENCE=PASS`

The timing metric is a foreground rendered-frame interval and CPU-submission
proxy. It is not GPU timing, VRAM measurement, or a certified FPS benchmark.
The evidence remains outside Git and contains no images or study identifiers.

## Production acceptance

The final guarded deployment reported:

- release source guard: PASS
- release content guard: PASS
- verified rollback backup: PASS
- byte-for-byte production content checks: PASS
- internal `/api/health`: PASS
- public `/api/health`: PASS
- service restart with a replaced PID: PASS
- sample-study catalog unchanged at four studies: PASS
- final deployed asset revision: `phase4h6-r1`

Manual production acceptance covered CT and MR, every rendering mode, all three
Slice planes, Thick Slab projection methods and thickness, dual-sided clipping,
MPR clipping overlays, the non-crossing dual intensity range, preset reset,
rotation, pan, zoom, and an error-free browser console.

## Frozen Phase 4 guarantees

- The canonical patient volume remains the source of truth.
- CT uses HU and MR uses truthful relative intensity semantics.
- GPU transport remains authenticated, integrity-bound, and source-revision-bound.
- Volume geometry preserves DICOM Patient LPS orientation and physical proportions.
- Windowing, transfer functions, clipping, opacity, and shading are display controls.
- Slice and Thick Slab sample the verified volume in patient space.
- No surface, anatomical label, measurement, or segmentation claim is introduced.

## Next phase boundary

Phase 4 no longer blocks subsequent segmentation work. Segmentation and any
segmentation-derived surface visualization must be implemented and qualified as
a separate phase. They must preserve the accepted canonical volume, MPR,
patient-space geometry, direct volume renderer, and explicit provenance.
