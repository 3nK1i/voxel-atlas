# 6H-A — local real-study fidelity qualification harness

Base: `3ae76199ad23d8c7d47f83c03e5a1c1739d26542`, `phase6-accurate-surfaces`.

This is an additive, opt-in development runner, **not** a production route, UI control,
patient-data export, clinical validation, or guarantee of exhaustive geometric fidelity.
It reuses the authoritative latest canonical CT source, validated Phase 5 label map,
Phase 3D MPR service and Phase 6A/6B accurate/refined surface services. The runner
binds study identity, CT/HU, canonical descriptor + volume artifact digests, LPS
shape/affine, map ID and artifact bytes, and pins the MPR service's latest manifest
path before and after the descriptor snapshot. It re-verifies manifest/volume/label
hashes and latest study identity after measurement. Because no transaction locks the
services, this is **best-effort snapshot consistency**, not an atomic database read.

By default the CLI runs **preflight only**, with no surface worker calls and no file
writes. It identifies ROI over-budget and acquisition-edge contact **without**
claiming a failed anatomical surface. In 6H-B, `--execute` calls the existing
surface services, which use transient worker files under `data/segmentation/surface-tmp`
(and may ensure the directory/permissions). The canonical volume, label map and
manifest are never intentionally modified; their hashes are rechecked. The execute
mode is *not* literally read-only across the entire data directory. No new
persistent artifact or report is written by this harness. Do not run concurrently
with study ingestion, label import, or production deployment.

One central slice through the selected label ROI is chosen independently for each
MPR plane in physical Patient LPS. Missing contours remain `needs_review`, not a
zero-distance success. A refined failure propagates; it is not silently replaced
with the accurate surface. The 6G budgets and sampled-only interpretation stay
unchanged. A large skull ROI, too many reference triangles, or an insufficient
search budget can make a real study **unmeasurable under the present limits**;
this warrants explicit 6H-B disposition, not a fabricated measurement or an
unreviewed increase to fidelity budgets. A central plane is not representative
of the whole acquisition. Phase 6H-B still requires additional representative
plane choices/coverage and direct visual review in the existing app.

No identifiers, hashes, raw measurements, or file paths are printed by the CLI.
Keep raw local exceptions, labels, DICOM, patient volumes, surface payloads,
private analysis results and logs on the development machine. Do not paste them
into chat or commit them. There are no changes to clinical claims, source labels,
canonical geometry, segmentation surfaces, MPR renderer, UI or production.

For 6H-A execute **only the synthetic tests**:
`VOXELATLAS_SURFACE_PYTHON="$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python" bash scripts/run_phase6h_a_checks.sh`.
Real-study execution is deferred to 6H-B after review of the preflight output.
