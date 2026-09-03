# Phase 4F: Adaptive Volume-rendering Quality

## Outcome

The true CT/MR patient-volume renderer now changes GPU workload according to the uploaded volume, display density, and active interaction state. Rotation, pan, zoom, multi-plane clipping, opacity, transfer-function adjustment, and auto-rotation use a responsive interactive profile. After 180 ms without interaction, the same renderer restores the higher-quality settled profile.

## Workload policy

The policy uses the qualified 3D texture dimensions and the browser device pixel ratio. It does not inspect anatomy, infer a body region, or change medical intensity values.

| Workload | Voxel count | Settled sampling limit | Interactive sampling limit | Settled pixel-ratio limit | Interactive pixel-ratio limit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Light | Up to 64 Mi voxels | 512 | 256 | 2.00 | 1.00 |
| Balanced | Up to 192 Mi voxels | 448 | 192 | 1.50 | 1.00 |
| Heavy | Above 192 Mi voxels | 384 | 144 | 1.25 | 0.90 |

Every sampling rate remains bounded by the ray marcher's 512-step shader limit. While interaction is active, twelve measured frame intervals above the 30 fps target can reduce the interactive sampling rate in bounded 15% steps. The controller never drops below half of the workload's initial interactive rate or 64 samples, whichever is greater. Returning to settled mode restores the deterministic settled profile.

## Idle GPU behavior

The browser animation callback remains available for interaction timing, but Three.js renders only after a scene, camera, control, resize, quality, or auto-rotation change. A stable view therefore stops issuing unnecessary GPU draws. Auto-rotation remains an intentional continuous interaction and uses the responsive profile until stopped.

## Preserved medical contracts

- RG8 samples still decode to the original CT HU or MR modality-value domain.
- Medical transfer functions, density, and global opacity are unchanged.
- Axial, Coronal, and Sagittal clipping remains in DICOM Patient LPS millimetres.
- The canonical volume, GPU artifact, revision, SHA256, and provenance are unchanged.
- No segmentation, surface mesh, OBJ, STL, or GLB representation is created.

## Qualification

The automated policy probe covers a representative 574 x 512 x 112 head volume, a 512 x 512 x 512 body volume, and a 768 x 768 x 512 large volume. It verifies workload classification, lower interactive cost, settled restoration, bounded frame-pressure backoff, and render requests. This deterministic policy validation is not a claim of a specific frame rate on every GPU.

Manual validation should confirm responsive orbiting and clipping, automatic settled-quality restoration, a stable quality-status label, unchanged patient orientation, and no visual change to medical transfer or clipping semantics.

## Deferred work

Sample dataset catalog integration remains Phase 4G. Production security and final V1 qualification follow after the Phase 4 rendering workflow is accepted.
