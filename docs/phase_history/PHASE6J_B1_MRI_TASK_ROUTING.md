# Phase 6J-B1 — MRI task identity and fail-closed workflow foundation

Base: `phase6-accurate-surfaces` at `9f7b9f1b61c12e9a535019152b33057eda2863eb`.
This is the first narrow implementation slice of Phase 6J-B; do not equate
source-level eligibility with MRI inference qualification.

- Preserve TotalSegmentator `total` as the CT model. For a canonical MR study,
  use the distinct `total_mr` model identity. Until that model is separately
  registered and qualified in a later phase, MRI status is **unavailable**,
  Start is disabled, and no CT job may be started for an MR study.
- Pin the 50 labels (IDs 1–50) observed in the installed TotalSegmentator
  2.18.0 `map_to_binary.py` MRI task. The inspected AST source mapping
  fingerprint was `63226e21df16918303452b90fb3f76a7640c5d5f7974b340cf942067bbfb28c7`.
  This fingerprint is review evidence, **not** runtime verification of
  installed weights or authorization to execute the MRI provider.
- Preserve CT structure classification. Use separate name-based MRI grouping;
  label indices mean different anatomy in CT `total` and MR `total_mr`.
- Provide a pure canonical MR image/geometry eligibility function for the next
  ingestion-qualification integration. Existing DICOM ingestion already
  supports certain CT and MR series; it does not establish suitability of
  all MRI sequences for the model. This function does **not** run inference
  and has not yet been wired to the study-admission path.
- Remove outdated Phase 7 MRI deferral text; display the selected task and
  the server's accurate unavailable reason. Refresh browser asset revisions.

## Boundaries and outstanding tasks

B1 does not register an MRI provider, enable MRI job creation in production,
change the CT execution bridge, alter stored studies, download models, or
claim clinical fitness. In B2, bind MR source/series qualification to the
normal existing-sample and uploaded-DICOM workflows and test unsupported
series. In 6J-C, qualify the exact `total_mr` package/task/weights/GPU and
implement worker execution. In 6J-D, integrate MRI label map, MPR and 3D
visualization, retaining Patient-LPS geometry and CT behavior.

## Required validation before any commit

Run `bash scripts/run_phase6j_b1_checks.sh` in the **full original repository**
with its existing `.venv`, complete CT-B3A runner and all prior scripts.
Run `git diff --check` and verify the exact ten-file inventory. The source
review ZIP used to prepare the candidate does not include all historical
scripts/dependencies; isolated baseline regression failures due solely to
those missing files must not be misreported as passes. No automatic commit,
push, merge, or production deployment.
