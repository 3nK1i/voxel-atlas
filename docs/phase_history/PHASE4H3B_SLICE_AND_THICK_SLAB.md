# Phase 4H3B - Slice and Thick Slab

## Scope

Phase 4H3B adds two patient-space medical plane modes beside Volume / DVR and the H3A full-volume projections:

- Slice samples one sharp plane from the canonical patient voxel texture.
- Thick Slab aggregates a configurable physical thickness using MIP, MinIP, or Average.

The plane can be Axial, Coronal, or Sagittal. Its position is the corresponding coordinate of the synchronized MPR crosshair. Standard slab thicknesses are 1, 5, 10, and 20 mm, with a bounded custom millimetre control.

## Medical and geometric contract

Plane orientation is defined by the DICOM Patient LPS axes, never by the current screen or raw Three.js axes. Plane position and slab thickness remain physical millimetre values. A Thick Slab is sampled along the selected patient-space plane normal, so its thickness does not change when the user rotates the 3D camera. Medical plane samples use explicit trilinear interpolation after decoding the packed texture texels, matching the interpolation model used by MPR without altering the RG8 transport artifact.

Slice and Thick Slab decode the same verified resident RG8 3D texture used by the other rendering modes. Window center/level and width are applied after direct slice sampling or slab aggregation. Slice windowing covers the full source plane, matching normal medical slice semantics; intensity minimum and maximum are therefore disabled in Slice mode instead of discarding out-of-range voxels. Thick Slab retains the selected intensity interval for projection filtering. Overall opacity, active Patient LPS clipping planes, and CT HU versus MR relative-intensity semantics remain active. DVR-only absorption, opacity softness, edge definition, and depth shading remain disabled because they do not apply to these grayscale medical plane modes.

Changing plane, crosshair position, thickness, or slab method updates shader uniforms and schedules a render. It does not fetch, rebuild, re-upload, resample, or modify the canonical medical volume. Slice and Thick Slab are derived views, not segmentation or surface geometry.

## Validation

The H3B checks cover Patient LPS plane mapping, bounded physical position and thickness, projection method selection, same-texture/resource identity, uniform-only UI changes, synchronized MPR crosshair ownership, canonical-volume safety, JavaScript and Python syntax, the full prior regression, diff whitespace, and patient-data Git safety.

Run:

```bash
bash scripts/run_phase4h3b_checks.sh
```
