# Phase 4D2 - Medical transfer functions

Phase 4D2 improves the clinical readability of the true patient voxel volume by replacing the single baseline mapping with modality-aware, piecewise color and opacity transfer functions. It does not create or display a patient surface.

## Delivered behavior

- CT volumes whose source units are HU receive General CT, Soft Tissue, Bone, and Low-Density CT presets expressed in calibrated Hounsfield units.
- MR volumes receive Balanced, Lower Intensities, and Higher Intensities presets expressed only against the qualified source intensity range. The application does not infer T1, T2, FLAIR, tissue class, or acquisition intent from the modality label.
- Unclassified modalities receive one generic relative-intensity preset.
- Every preset supplies six ordered GPU control points for medical intensity, opacity, and color.
- The lower intensity, upper intensity, and density controls update shader uniforms immediately. They do not refetch the volume, rebuild the derived texture, modify the canonical source, or change its provenance.
- The existing global opacity control remains independent of the transfer function.
- Transfer controls stay unavailable until the verified texture is active and the ray-marching shader has compiled.
- Reset restores the selected preset's default intensity range and density.

No segmentation, threshold-derived anatomy, marching cubes, surface reconstruction, OBJ, STL, or GLB patient model is introduced. Every rendered sample still comes from the authenticated RG8 derivative of the uploaded CT or MR voxel volume.

## Safety and scope

The presets are visualization starting points, not diagnostic protocols. MR signal is not standardized like CT HU, so MR controls remain explicitly relative to the source series. The application remains an engineering and research system rather than a certified medical device.

Directional Cut remains disabled in this step. The locked next step is Phase 4E multi-plane patient-space clipping: independent Axial, Coronal, and Sagittal planes may be active simultaneously, with a depth and retained side for each plane. That work must clip the ray interval in patient space and remain synchronized with the MPR coordinates.

Adaptive quality and performance qualification remain later Phase 4 work.

## Validation target

Phase 4D2 closes only after automated regression, real CT visual inspection of every CT preset, intensity and density adjustment checks, reset verification, rotation and opacity regression, and confirmation that the browser console remains clean. A qualified MR study is required before MR visual behavior can be accepted beyond its structural contract.
