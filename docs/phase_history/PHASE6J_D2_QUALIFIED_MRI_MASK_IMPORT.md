# Phase 6J-D2 — Qualified import of an already accepted MRI mask

Base: `phase6-accurate-surfaces` at `3d9e7561ed0fa146e9ad2123ead3b1915498f719`.

Scope: A **separate** MRI-only path qualifies the current stored MR source,
uniquely matching succeeded `totalsegmentator/total_mr` job, immutable terminal
provenance, pinned 50-label mapping, `fastest`-mode GPU-0 trial identity, source
and mask digests, source/series identity, and the original TotalSegmentator
provider report. It reuses the existing Phase 5C canonical NIfTI→NPY worker,
which rejects shape, Patient-LPS affine, noninteger labels and nonidentity
index-transform differences rather than resampling masks. A second qualification
and descriptor audit follow the import. The existing provider-neutral
import service gains an optional MRI-only nonzero-voxel equality guard; CT
imports retain their existing default behavior. Repeated imports reuse the same
validated immutable map. Incorrect or ambiguous current source/job matches
fail closed; no CT job is imported via the MRI-only path.

`--check` is read-only and must not create a label map or run inference.
`--import` is a separately confirmed, one-off **artifact import**, NOT a
model run: it is forbidden from an uncommitted/unpushed repository. Inference
remains disabled in the normal application and all UI presentation remains
read-only until later Phase D integration and validation.

The local validation script runs synthetic-only MRI import/rejection tests,
existing Phase 5C import regressions, and the full pre-existing C5D CT/MRI
suite. Real accepted MRI pixels, DICOM, model weights, job manifests, masks
and identifying logs must remain local and must never be included in a patch.

Technical artifact handling is not clinical validation or diagnostic approval.
