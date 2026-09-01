# Runtime anatomy models

`skull_full.glb` is the currently qualified demo skull used by the Phase 2B workspace while the patient-data reconstruction pipeline is being built.

The final V1 anatomy layers do **not** rely on manually copied static brain or volume files. Later reconstruction phases will register patient-derived layers in one shared coordinate system and make them available to the viewer as real runtime outputs.

The locked V1 layer architecture is:

- Full Volume
- Skull
- Brain
- Skull + Brain

Only Skull is available in the current demo shell. Full Volume, Brain, and Skull + Brain remain disabled until the DICOM and reconstruction pipeline provides qualified patient-specific data. The browser must never fabricate missing anatomy.
