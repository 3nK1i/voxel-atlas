# Phase 4C2 - True Patient Volume Ray Marching

Phase 4C2 is the first VoxelAtlas step that displays the actual uploaded CT/MRI voxel volume interactively in the central 3D viewer. It consumes only the verified Phase 4C1 `Data3DTexture`; it does not generate a surface or infer anatomy.

## Direct rendering pipeline

The WebGL2 fragment shader intersects each camera ray with the patient-volume proxy box, samples the 3D texture along the complete entry-to-exit segment, decodes the RG8 low/high bytes to the descriptor's medical intensity domain, and composites color and opacity front to back. Early termination stops rays that have become effectively opaque.

The Phase 4B RG8 derivative remains a two-byte transport representation. The shader uses nearest texture fetches so the two encoded bytes are decoded before any value mapping. Hardware interpolation of the separate low and high byte channels is intentionally avoided because it would not preserve 16-bit values across byte carries.

## Patient-space presentation

The descriptor's `texture_coordinate_to_patient_lps` matrix is authoritative. The renderer maps its DICOM Patient LPS millimetres into the existing VoxelAtlas Right/Superior/Anterior viewer frame, computes the eight transformed voxel-cell corners, recenters the proxy, and applies one uniform presentation scale. Physical proportions and acquisition orientation are retained; the canonical volume and its affine are unchanged.

## Activation and lifecycle

`Full Volume` remains disabled in initial HTML and becomes available only after all of the following succeed:

- WebGL2 and 3D texture qualification
- authenticated artifact preparation and download
- revision, header, length, and SHA256 verification
- GPU texture initialization
- ray-marching shader compilation

On success, Full Volume becomes the active layer and the demo skull becomes an explicitly selectable fallback. Replacement studies, logout, and page unload dispose the volume proxy geometry, shader material, and owned texture through their separate lifecycle managers. A failure leaves Full Volume disabled and synchronized MPR available.

## Deliberately narrow baseline

CT HU and MR modality intensities use conservative baseline mappings so the renderer can show true voxels now. Phase 4D remains responsible for clinical transfer-function presets and adjustment controls. Phase 4E remains responsible for synchronized axial, coronal, and sagittal clipping. Phase 4F remains responsible for adaptive rendering quality and large-study performance qualification.

Directional Cut is therefore disabled while Full Volume is active in C2. It remains unchanged for the demo surface fallback and will be connected to the voxel ray interval in Phase 4E.

No segmentation, skull extraction, brain extraction, marching cubes, or patient surface mesh is introduced in Phase 4C2.
