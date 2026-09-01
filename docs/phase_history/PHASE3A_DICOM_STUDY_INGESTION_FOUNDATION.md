# Phase 3A - DICOM Study Ingestion Foundation

## Goal

Phase 3A starts the locked V1 Data -> Reconstruction -> 3D Visualization pipeline with a real authenticated DICOM ingestion boundary. It does not reconstruct a volume or fabricate MPR output.

## Scope

- enable the workspace `Upload DICOM` action
- select a DICOM study folder from the browser
- upload files through authenticated FastAPI multipart handling
- enforce the configured total upload-size limit and a bounded file count
- parse DICOM metadata only with `pydicom` (`stop_before_pixels=True`)
- support CT and MR image instances for the V1 ingestion path
- ignore non-DICOM / non-image / unsupported-modality objects rather than storing them
- reject mixed StudyInstanceUID selections and duplicate SOPInstanceUID values
- group accepted instances by SeriesInstanceUID
- persist raw accepted instances under generated internal filenames
- persist a versioned canonical study manifest under `VOXELATLAS_DATA_DIR`
- expose public study/series metadata without raw paths, instance hashes, PatientName, or PatientID duplication
- restore the latest ingested study after workspace refresh
- show real study metadata and a real discovered-series dialog
- move the workflow state from Data to Reconstruction after a valid upload

## Storage contract

Phase 3A writes only below the configured data directory:

```text
<data_dir>/
  .staging/<generated-study-id>/
  studies/<generated-study-id>/
    manifest.json
    instance-000001.dcm
    instance-000002.dcm
    ...
```

Staging is removed on failure. A complete validated staging directory is promoted to the study directory only after the manifest is written.

Raw medical data remains excluded from Git by the repository `.gitignore` contract.

## Canonical metadata boundary

The manifest preserves Study/Series/SOP UIDs, acquisition geometry metadata needed by later phases, generated stored filenames, file hashes, and source-instance sizes. The browser-facing API intentionally returns a reduced metadata view and does not expose stored filenames or hashes.

Phase 3A does not copy `PatientName` or `PatientID` into the canonical manifest. Raw source files remain untouched for provenance and later controlled processing.

## Truthful reconstruction state

After ingestion:

```text
Data             complete
Reconstruction   active / pending
3D Visualization pending for patient data
```

The existing demo skull remains visibly labeled as demo anatomy. Full Volume, Brain, Skull + Brain, and all Axial/Coronal/Sagittal image content remain unavailable until later reconstruction phases provide patient-derived data.

## Deferred to Phase 3B+

- robust slice geometry validation and ordering qualification
- enhanced/multiframe DICOM handling qualification
- canonical patient volume construction
- Axial/Coronal/Sagittal rendering from the patient volume
- skull/brain segmentation and mesh reconstruction
- multi-study lifecycle management and deletion controls

## Validation

`bash scripts/run_phase3a_checks.sh` is compact on success and prints detailed output only for failed checks.
