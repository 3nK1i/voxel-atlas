# Phase 4B - Direct Patient Volume Rendering Foundation

Phase 4B pivots VoxelAtlas toward true GPU rendering of the uploaded CT or MRI voxel volume. It does not perform segmentation, extract a surface, or claim that the Phase 4C ray marcher is already available.

## Source-volume contract

The Phase 3 canonical `float32` volume remains authoritative and immutable:

- native array order `[slice, row, column]`
- CT values in HU after the qualified DICOM modality transform
- MR values preserved as modality intensities, never interpreted as HU
- physical spacing in canonical array order
- voxel-centre `array_index_to_patient_lps` affine
- source SeriesInstanceUID, creation time and descriptor identity

Phase 4B verifies the manifest, `volume.json`, `volume.npy`, dtype, shape, axis order, intensity semantics and invertible patient-LPS affine before producing any rendering artifact.

## Derived GPU representation

The browser representation is a derived presentation artifact under the Git-ignored study directory. The canonical medical volume is never replaced or rewritten.

Each voxel is linearly quantized to 16 bits and stored as two interleaved `RG8` bytes in little-byte/high-byte order. The descriptor records `decode_offset` and `decode_scale`, allowing a shader to recover CT HU or MR modality intensity. Conversion is chunked to avoid a second full-volume allocation.

Texture dimensions are `[column, row, slice]`, matching WebGL width, height and depth while preserving canonical C-order voxel traversal. The descriptor also includes:

- the unmodified voxel-centre patient-LPS affine
- a texture-coordinate-to-patient-LPS transform covering the full voxel-cell bounds
- patient-LPS physical bounds
- source descriptor identity
- artifact SHA256, revision and exact byte length

Artifacts are published atomically and are rejected if corrupt, stale, inconsistent with their metadata, or requested using a revision that is not current.

The direct foundation uses a bounded 512 MiB derived-artifact limit. Larger studies remain available through MPR and require the adaptive representation work planned for Phase 4F.

## Authenticated transport

Phase 4B adds:

- `POST /api/studies/latest/volume-rendering` to prepare or restore the current derivative
- `GET /api/studies/latest/volume-rendering` to inspect its safe public descriptor
- `GET /api/studies/latest/volume-rendering/data?revision=...` to stream revision-bound RG8 bytes

All endpoints require the existing session authentication and use `Cache-Control: no-store`. The binary response uses `X-Content-Type-Options: nosniff`. Internal artifact and metadata paths are never exposed.

## Browser qualification and truthful UI

The current Three.js renderer reports WebGL2 and `MAX_3D_TEXTURE_SIZE` capability before the application prepares a rendering artifact. Source dimensions and the two-byte-per-voxel client allocation are checked first.

Phase 4B does not download the binary artifact into a 3D texture and does not enable `Full Volume`. The existing MPR remains available if browser or size qualification fails. The demo skull remains explicitly a demo until Phase 4C replaces the normal real-study 3D workflow with the actual patient volume.

For a workstation that already contains the qualified real patient volume, prepare and inspect the artifact with:

```bash
python scripts/check_phase4b_latest_volume_rendering.py
```

The probe verifies that both canonical files remain byte-for-byte unchanged and reports the safe rendering descriptor, artifact hash and revision without printing patient paths.

## Out of scope

- ray casting or ray marching
- `Data3DTexture` allocation
- transfer functions and clinical presets
- 3D clipping and MPR synchronization
- adaptive downsampling or multi-resolution transport
- skull or brain segmentation
- surface-mesh extraction
- production deployment
