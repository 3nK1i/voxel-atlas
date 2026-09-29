# Phase 6J-D2 — Privacy-safe production import stage reporting

Base: `phase6-accurate-surfaces` at `d3864a6b48077b6fb4aa486deca54ccf7d09217a`.

This is an observability-only correction for the D2 command and the existing
canonical import path. The first authorized production MRI import returned the
previously generic `D2_STATUS=BLOCKED`; its original failure stage cannot be
reconstructed. Subsequent read-only qualification and a disposable full import
passed. Those outcomes **do not** prove that a production map exists or explain
the original failure.

On an import failure, the command still reports `D2_STATUS=BLOCKED` and now
reports one fixed stage token as `D2_FAILURE_STAGE=...`. The stage is a
bounded indication of the last operation entered, not an exception diagnosis;
a stage such as `ARTIFACT_PERSISTENCE` or `PERSISTED_MAP_RELOAD` does not prove
whether an artifact was already made durable. The `--check` output remains
unchanged. There is no exception message, private pathname, study identifier,
voxel data, anatomical label, process stderr, or model log in stage output.

Stage tracking is opt-in, from the D2 entrypoint through the MRI-only importer
to the existing canonical label-map service. Its default behavior for CT and
all other callers remains unchanged. The feature neither loosens qualification
checks nor catches new exceptions, retries a failed import, launches a model,
registers an executable MRI provider, or enables MPR/3D presentation.

Acceptance: run synthetic failure, success, and cleanup checks, D2 import
regression, prior CT/MRI regression, syntax and diff checks on the development
branch. Inspect and separately authorize the documentation/source commit and
push. A **new, separate operator authorization** is required before any
subsequent real production import of the already accepted MRI mask. Do not
rerun model inference. If a later import fails after creating a final map,
inspect its identity and integrity before attempting anything further.

Clinical validation is not claimed. Do not package patient images, masks,
model weights, private job manifests, or local diagnostic reports.
