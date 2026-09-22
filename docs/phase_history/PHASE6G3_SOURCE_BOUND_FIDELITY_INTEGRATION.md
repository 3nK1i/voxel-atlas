# Phase 6G3 — source-bound sampled fidelity evidence (candidate)

Baseline: `39655190e94b9b7fffc09cfa162449d8414c7a80` on `phase6-accurate-surfaces`.

## Purpose and boundary

Additive opt-in numerical integration of 6G0 (local first-order proxy), 6G1
(sampled bidirectional polygonal mask/mesh distances), and 6G2 (sampled
three-world-plane MPR contour agreement). No HTTP endpoint, UI, patient-data
export, canonical artifact mutation, or production deployment. The caller must
obtain a *validated* canonical label-map descriptor, authoritative latest study
identity, 6A accurate and (if available) 6B refined surface objects and same
study MPR descriptor from their existing services; these service calls are
**not** invoked by the pure helper. In particular, the MPR study ID is
**caller-attested**, not independently authenticated by this helper. Source
MPR world bounds must also match the canonical label map's full LPS bounds.
Do not feed unrelated study snapshots, presentation-transformed positions, or
resampled masks. A caller must reverify latest study and revisions before and
after obtaining those objects when running a real-study qualification.

The helper checks the on-disk source `labels.npy` byte size and SHA256 against
its validated descriptor, validates the NPY array shape/dtype, crops the
selected label to a bounded bounding box and **translates its ROI affine** in
Patient LPS. Virtual-zero padding remains the 6A reference boundary. This
copy is for analysis only. It independently checks each surface v2 payload
SHA256, schema, label/map/quality, surface identity, bounds and (for refined)
the exact accurate reference payload link, then decodes native LPS positions
and triangles. Source NPY and surface payload hashes are checked again after
analysis; this is a best-effort consistency check, not an atomic database
snapshot or a substitute for service-level provenance verification.

Accurate and refined results remain separate. A missing refined surface is
`not_available`, not a fabricated zero or silent accurate fallback. A selected
MPR slice with no reference or candidate contour produces `needs_review`,
not a geometric failure score. Exceeded 6G0/1/2 budgets or invalid provenance
fail closed without a partial successful report; the source-label ROI limit is
8 million voxels. Refined vertices outside the ROI half-voxel domain may leave
the **first-order proxy** unevaluated without discarding valid 6G1/2 distance
evidence. Sampling fractions and selected slice indices must accompany any
reported numbers; they are not continuous-area coverage guarantees.

`sampled_evidence_only` means **calculations finished for the supplied
snapshots and chosen planes**, not a mesh-quality verdict, whole-surface
Hausdorff bound, raster-overlay pixel equivalence, model accuracy score,
validated diagnosis, or independent anatomical ground truth. No clinical
threshold or patient-space correction is introduced. Neither contour nor
surface sampling proves that every disconnected component was measured.

## Gates

Synthetic test-first integration tests cover source/ROI binding, anisotropic
patient-space geometry, accurate/refined separation, missing refined and
missing-contour reporting, wrong study/label/geometry, digest and reference
mismatch, symlink rejection, analysis budget fail-closed, and no source edits.
Run `VOXELATLAS_SURFACE_PYTHON="$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python" bash scripts/run_phase6g3_fidelity_checks.sh`.

Before claiming complete Phase 6G on the developer machine: run targeted plus
prior regressions, guarded exact-file review, and inspect source/MPR/surface
revision consistency. Phase 6H is reserved for **real-study** qualification,
including documented unmeasurable workloads, selected-slice coverage and
physical interpretation; it must not assume the synthetic results prove
patient-specific accuracy. Avoid printing or uploading study IDs, raw NPY,
surface payloads, DICOM, labels or measurements from identifiable cases.
