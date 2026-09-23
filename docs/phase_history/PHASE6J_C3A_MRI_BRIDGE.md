# Phase 6J-C3A — isolated MRI canonical NIfTI bridge

Pre-apply baseline: `a585783296741bae2ad15cf7288ea7b2dde2adfa` on `phase6-accurate-surfaces`.

## Narrow scope

- A **new** independent MRI-only NPY-to-NIfTI bridge; CT Phase 5B2 bridge remains unchanged.
- Requires a ready float32 three-axis MR descriptor, finite voxels, nonsingular Patient-LPS affine, and shape agreement with canonical NPY.
- Converts Patient-LPS to NIfTI Patient-RAS using the explicit diagonal x/y sign inversion; the NIfTI `sform` is authoritative.
- Independently checks output mask geometry, finite integral IDs in `[0,50]`, hash/provenance, and nonzero voxel count without accepting CT's 117-label contract.
- Validation uses synthetic data only. No real MRI study is read, no weights are downloaded, and no inference, provider registration, UI changes, or study artifacts are produced during automated checks.

## Acceptance and remaining C3 scope

Run the new targeted tests and existing C2/CT regressions on the user's local application interpreter, plus the synthetic NIfTI roundtrip in the dedicated environment that has nibabel and NumPy. The physical hardware/model execution, supervised MRI subprocess invocation and job binding are **not qualified** by this bridge; C3B handles the independently supervised worker path, C4 handles provider/job integration, and C5 handles real MRI execution/hardware limits.

The synthetic roundtrip test is skipped rather than represented as PASS when nibabel is absent from the test interpreter. Run it in the dedicated MRI interpreter for completion evidence.
