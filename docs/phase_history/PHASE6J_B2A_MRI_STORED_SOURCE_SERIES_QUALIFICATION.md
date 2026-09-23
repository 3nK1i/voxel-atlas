# Phase 6J-B2A — Canonical MRI source and series qualification

Baseline: development branch `phase6-accurate-surfaces`, commit prefix `32d9d7d`.

The existing sample-activation and user-DICOM-upload paths both persist the same
study manifest and canonical-volume descriptor. This narrow slice qualifies the
active canonical MR source and the exact reconstruction-ready DICOM series, not
raw upload admission or MRI model-sequence suitability. Fail closed when the
volume's modality/shape/affine, source series UID, reconstruction geometry,
dimensions, or source-instance count disagree; return safe actionable status.

Only the `totalsegmentator/total_mr` workflow uses this check. CT, previously
qualified CT surfaces, and generic provider contracts remain unchanged. MRI
inference remains unavailable until separate provider/runtime/weights/GPU
qualification in 6J-C. Do not infer suitability for all MRI sequences.

6J-B2B must expose pre-volume qualification/error states for sample activation
and newly uploaded studies and test the real UI paths with privacy-safe local
fixtures. The present step does not mutate patient studies or start ML workers.

Run targeted checks and the full prior B1/CT regression on the full repository,
review exact change set and diff checks before any commit or push.
