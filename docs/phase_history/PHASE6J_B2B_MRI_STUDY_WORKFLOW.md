# Phase 6J-B2B — MRI study-workflow admission and presentation

Base: `phase6-accurate-surfaces` at `397a9014856b8bd39d81e04dfae637142548d60e`.
This is the final **planned** 6J-B implementation slice.

Both the existing-sample loader and newly uploaded DICOM study call the shared
`applyStudy()` path. Before canonical MR volume creation, the MRI segmentation
panel now explains whether the selected MR series has reconstruction-qualified
geometry, whether canonical volume construction is pending, or whether volume
construction has failed. A source without a verified canonical volume is never
eligible to start MRI segmentation. The same panel presents the server-authoritative
B2A stored-source qualification once the canonical MR volume is ready.

The pre-volume UI evaluation uses only public study descriptor fields, does not
read patient pixels, does not change DICOM ingestion, and is **not** model-sequence
suitability or clinical validation. A mixed study with CT selected keeps the
existing CT interface. The existing server-side CT job and MRI source/series
guards are unmodified; `total_mr` remains unavailable for execution until 6J-C.

Acceptance for final 6J-B closure additionally requires *real local manual*
verification of both an existing compatible MRI sample and a newly uploaded
MRI study through normal UI, including a no-volume/unsupported series scenario.
Synthetic tests prove shared-path wiring, fail-closed presentation and CT
regression only; they are not a substitute for those real-sample checks.
No patient files, service credentials, model weights or server logs are packaged.

## Local manual acceptance — 2026-09-23

Environment: development preview on 127.0.0.1:8011.
Evidence: local UI observations and the B2B automated regression output.
No patient files or identifying study metadata are included here.

- Existing compatible brain-MR sample: PASS. Canonical volume and three
  MPR planes rendered. The segmentation panel identified the MRI total_mr
  task, reported the unqualified provider, and disabled Start Segmentation.
- Compatible MRI study loaded through Upload DICOM: PASS. Canonical volume
  and MPR rendered. MRI task selection and disabled inference were observed.
- MRI study requiring geometry review, loaded through Upload DICOM: PASS
  for the unsupported-series UI scenario. The study was accepted for review,
  but no canonical volume or MPR was presented. The segmentation panel
  explained that reconstruction-qualified MR geometry was unavailable and
  disabled Start Segmentation. The specific DICOM geometry defect was not
  independently diagnosed.
- CT backward-compatibility sanity: PASS. CT volume and MPR remained
  available, the CT segmentation workflow retained its existing result,
  and the interface did not retain the preceding MRI task state.

Acceptance scope: study ingestion, source qualification, pre-volume
presentation, and fail-closed MRI segmentation gating. These observations
do not establish support for every MRI sequence, successful MRI model
execution, MRI anatomical surface generation, or clinical validation.
MRI provider execution remains reserved for Phase 6J-C.
