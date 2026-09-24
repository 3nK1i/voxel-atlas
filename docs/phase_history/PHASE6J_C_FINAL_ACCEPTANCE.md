# Phase 6J-C — Controlled MRI inference acceptance

Date: 2026-09-24
Development branch: `phase6-accurate-surfaces`
Validated code checkpoint: `82653614be1361825c8b0ef8c23df260898e6891`

## Scope

Phase 6J-C establishes a controlled, isolated TotalSegmentator
`total_mr` execution path and technical acceptance of one persisted MRI
segmentation result. It does not enable routine MRI model execution
in the normal VoxelAtlas application.

## C5E — one authorized real-model trial

The operator-authorized, single-run trial completed on GPU 0 in
`fastest` mode. The runner reported:

- `C5D_ONE_SHOT_TRIAL=SUCCEEDED`
- `C5D_RESULT_VALIDATION=WORKER_AND_STUDY_BOUND_CHECKS_PASS`
- `C5E_RUNNER_EXIT=0`

The trial was not automatically retried.

## C5F — independent persisted-result acceptance

A subsequent read-only inspection of the saved result reported:

- Completed job and sealed terminal provenance: PASS
- MRI study, series, source, model, and GPU binding: PASS
- Persisted input and mask artifact hashes: PASS
- Provider report: PASS
- Mask geometry, label range, and voxel counts: PASS
- Original MRI source unchanged: PASS
- `C5F_PERSISTED_RESULT_ACCEPTANCE=PASS`

No additional MRI inference was run during C5F acceptance.

## Final regressions

The final C5D synthetic checks and prior CT/MRI regression suite passed.
The dedicated MRI-interpreter geometry regression executed five tests,
all passing. The broad application-interpreter suite skipped the
nibabel-dependent geometry test because nibabel was unavailable in that
interpreter; the dedicated isolated MRI-interpreter run executed and
passed the same test.

Local regression report:
`~/Downloads/voxelatlas_phase6j_c_final_regression_20260924.txt`

This report is retained locally and is not included in the repository.
C5E and C5F real-result statuses above were reviewed from the
operator's local terminal output; private study artifacts, job
manifests, and model logs are not included in this record.

## Acceptance boundary

Phase 6J-C technical acceptance: PASS.

This acceptance does not establish clinical accuracy, diagnostic
suitability, or clinical validation. It does not authorize automatic,
repeated, or user-facing MRI inference. MRI mask presentation in MPR
and segmentation-derived 3D surfaces remain outside this phase and
require separate Phase 6J-D implementation and validation.

CT behavior, existing application workflow, and the default
non-executable MRI provider registration remain unchanged.
