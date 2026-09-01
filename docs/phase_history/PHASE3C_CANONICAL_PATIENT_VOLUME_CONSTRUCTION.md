# Phase 3C - Canonical Patient Volume Construction

Phase 3C turns one Phase 3B reconstruction-qualified CT/MR series into a persisted patient voxel volume. This is the first phase that decodes DICOM PixelData. It does not yet render MPR images or generate patient skull/brain surfaces.

## Construction contract

VoxelAtlas uses the Phase 3B geometric ordering as authoritative and constructs a NumPy `float32` array in explicit `[slice, row, column]` order. Each source slice must decode to the qualified Rows/Columns matrix. The service refuses unqualified geometry, incomplete source stacks, source files that no longer match their Phase 3A SHA256 provenance, invalid intensity transforms, non-finite pixel values, and arrays that exceed the bounded canonical-volume allocation limit.

The default DICOM pixel reader uses pydicom pixel decoding and `apply_modality_lut`, so standard Modality LUT or RescaleSlope/RescaleIntercept transforms are applied before values enter the canonical volume. CT volumes are reported in HU. MR values are reported as modality intensities because MRI intensity units are not universally standardized.

## Patient-coordinate provenance

The volume metadata stores:

- array shape and `float32` dtype
- axis order `[slice, row, column]`
- spacing in the same array-axis order
- first-slice ImagePositionPatient as the LPS origin
- a 4x4 `array_index_to_patient_lps` transform
- source SeriesInstanceUID and instance count
- intensity units and observed value range

For an array index `[k, j, i]`, the affine uses the Phase 3B slice normal for `k`, the DICOM second ImageOrientationPatient vector for row index `j`, and the first ImageOrientationPatient vector for column index `i`, with the corresponding geometric/PixelSpacing values.

Phase 3C preserves native acquired samples. It does not resample into a new axial grid; the patient LPS transform is the canonical spatial contract used by later MPR/reconstruction stages. Phase 3A schema-v1 studies are geometry-qualified again from their stored per-instance metadata during construction, so an already uploaded qualified study does not need to be uploaded again.

## Persistence

Derived data is written under the already Git-ignored study directory:

- `derived/volume.npy`
- `derived/volume.json`

Temporary files are written first and the study manifest is published last. The study manifest advances to schema version 3 only after successful construction. Public API responses expose volume provenance and geometry but never internal artifact filenames or stored DICOM filenames.

A missing published artifact is not trusted merely because an old manifest says `volume.ready=true`; the volume is rebuilt from the qualified DICOM source stack.

## UI behavior

The workspace automatically requests volume construction after a study becomes geometry-ready. When construction succeeds:

- Reconstruction workflow becomes complete for the volume stage.
- the left status reads `Patient volume ready`.
- MPR shells report `Volume ready - MPR rendering pending`.
- the demo skull remains clearly a demo surface.
- Full Volume, Brain, and Skull + Brain 3D modes remain unavailable until their actual visualization/reconstruction implementations exist.

No fake MPR image is produced in Phase 3C.

## Out of scope

- MPR slice rendering and window/level interaction
- native-volume reorientation/resampling
- tilted/sheared stack resampling
- enhanced multi-frame DICOM reconstruction
- 3D volume ray casting
- skull/brain segmentation or surface extraction
