# Phase 4D1 - Volume-Only Workspace

## Objective

Phase 4D1 locks VoxelAtlas V1 to one patient-specific 3D representation: the full CT or MRI voxel volume reconstructed from the uploaded DICOM series and rendered directly by the verified GPU ray marcher.

## Runtime contract

`Full Volume` is the only entry under Anatomical Layers. The workspace no longer presents Skull, Brain, Skull + Brain, Skin, Sinuses, or Vessels as separate modes. These are not hidden future controls and are not generated as OBJ, STL, GLB, segmentation, or surface-mesh outputs.

The browser no longer imports `GLTFLoader`, requests a static anatomy model, constructs a mesh material, or keeps a demo surface fallback. Before a qualified patient volume is ready, the 3D viewport remains empty and truthfully asks for a DICOM study. If GPU volume preparation fails, synchronized MPR remains available and the 3D failure is reported without substituting unrelated anatomy.

## Preserved behavior

- authenticated CT/MR DICOM upload
- canonical full-resolution patient volume
- authenticated and integrity-checked RG8 presentation artifact
- WebGL2 3D texture and patient-volume ray marcher
- DICOM Patient LPS geometry and physical proportions
- Axial, Coronal, and Sagittal MPR
- rotate, pan, zoom, reset, fullscreen, opacity, and auto-rotate
- explicit disposal on replacement, logout, and page unload

Directional Cut remains visible but disabled until Phase 4E connects patient-space clipping to the volume ray interval. Phase 4D2 adds medical transfer-function presets and adjustment controls to the same full volume. Neither step introduces segmentation or surface reconstruction.

## Data safety

The canonical medical volume is unchanged. Phase 4D1 changes only browser presentation, tests, validation, and documentation. Raw DICOM, canonical volume files, and derived patient artifacts remain excluded from Git.
