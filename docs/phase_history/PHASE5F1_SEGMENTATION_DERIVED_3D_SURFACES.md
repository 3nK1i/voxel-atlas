# Phase 5F1 - Segmentation-Derived 3D Surfaces

## Scope

Phase 5F1 introduces the first segmentation-derived geometry in the VoxelAtlas
3D workspace. It converts one selected nonzero label from the immutable Phase 5C
Patient LPS label map into a bounded triangle surface and displays that surface
together with the existing patient volume.

This step does not smooth, repair, decimate, edit, or export anatomy. Those
operations remain Phase 6 work. The surface is a non-clinical visualization.

## Backend contract

`SegmentationSurfaceService` accepts only the canonical `uint16` NPY label map
whose source study matches the currently active DICOM study. Background label
zero, absent labels, invalid quality profiles, changed array geometry, and
cross-study requests are rejected.

Extraction uses deterministic exposed voxel-boundary faces. `preview` and
`balanced` profiles choose a bounded sampling stride and enforce hard triangle
budgets. Vertex positions are transformed by the canonical
`array_index_to_patient_lps` affine and remain in Patient LPS millimetres.

The authenticated descriptor route is:

`GET /api/studies/latest/segmentation-surfaces`

The authenticated per-label binary route is:

`GET /api/studies/latest/segmentation-surfaces/{label_id}`

The versioned binary payload contains a fixed 32-byte header followed by
little-endian float32 Patient LPS positions and uint32 triangle indices. Response
headers bind the payload to the label map, label, extraction profile, counts,
bounds, and SHA-256. All responses use `no-store` and `nosniff`.

## Browser contract

The selected structure is loaded on demand. The browser verifies the response
binding and SHA-256 before constructing a Three.js `BufferGeometry`. It maps
Patient LPS coordinates through the exact center and scale of the active patient
volume, computes display normals, and renders the selected surface in the same
rotating anatomy group as the volume.

Phase 5E selection, visibility, color, opacity, and isolation controls drive the
surface presentation as well as the synchronized MPR overlays. Only the selected
structure is resident as a 3D mesh in Phase 5F1, keeping CPU, network, browser,
and GPU work bounded.

## Qualification boundary

Automated checks cover deterministic geometry, physical bounds, payload layout,
authentication, no-store transport, browser decoding, heavy dependency
isolation, patient-data Git safety, and full previous regression.

Real qualification extracts a present public-study label, records its geometry
and payload digest, then requires manual confirmation that the colored anatomy
surface is aligned with and visible together with the CT volume. This is not a
clinical accuracy claim.
