# Phase 3B - DICOM Geometry and Reconstruction Readiness

Phase 3B converts Phase 3A Study/Series discovery into a geometry-qualified input for patient volume construction. It remains metadata-only: no pixel volume, MPR image, skull, or brain reconstruction is produced in this phase.

## Geometry contract

For each CT/MR series VoxelAtlas now validates:

- Rows and Columns consistency
- positive and consistent PixelSpacing
- valid and consistent ImageOrientationPatient direction cosines
- ImagePositionPatient on every slice
- geometric ordering by projection onto the slice normal, never by InstanceNumber alone
- duplicate slice positions
- median geometric slice spacing and spacing regularity
- probable gaps in the stack
- in-plane slice-origin drift / tilted or sheared stacking that requires later resampling support
- current exclusion of enhanced multi-frame geometry from the simple-stack path

A series is `reconstruction_ready` only when the canonical simple-stack geometry is complete and consistent.

## Canonical geometry evidence

A qualified series records:

- `(rows, columns, slices)` dimensions
- `(row, column, slice)` spacing in millimetres
- patient-space origin
- row and column direction cosines
- slice normal
- patient-space slice-position range
- internal geometric instance ordering
- explicit geometry issues when readiness is blocked

Internal filenames and instance hashes remain excluded from the public API.

## Backward compatibility

Phase 3A schema-v1 manifests already contain the required per-instance ImagePositionPatient and ImageOrientationPatient metadata. Phase 3B qualifies those stored manifests on read, so a previously uploaded study can become geometry-ready without re-uploading the DICOM files.

## UI behavior

The workspace now distinguishes:

- `Geometry ready - volume reconstruction pending`
- `Geometry needs review before reconstruction`

The DICOM Series dialog shows orientation and geometric slice spacing for qualified series. MPR panels remain empty until the next volume-construction phase.

## Out of scope

- pixel decoding and voxel array construction
- resampling tilted/sheared stacks
- enhanced multi-frame reconstruction
- MPR rendering
- patient skull/brain segmentation or surface extraction
