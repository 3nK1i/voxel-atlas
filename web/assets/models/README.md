# Runtime anatomy models

`skull_full.glb` is the currently qualified demo skull used by the Phase 2B workspace while the patient-data reconstruction pipeline is being built.

Patient Full Volume is not a static model. It is the highest-priority V1 visualization and must be rendered directly from the uploaded patient-specific CT/MRI voxel data. Brain, Skull, and Skull + Brain are deferred patient-derived outputs.

The locked V1 layer architecture is:

- Full Volume
- Skull
- Brain
- Skull + Brain

Only the clearly labeled demo Skull is visible in the current shell. Phase 4B prepares a qualified patient-volume texture artifact, but Full Volume remains disabled until the Phase 4C ray marcher renders it. Brain and Skull + Brain also remain disabled. The browser must never fabricate missing anatomy.
