# Inactive historical anatomy models

The files in this directory are retained only as historical assets from the earlier workspace foundation. Phase 4D1 removes their browser import and runtime loading path.

Patient Full Volume is not a static model. It is the only V1 3D representation and is rendered directly from the uploaded patient-specific CT/MRI voxel data.

The locked V1 Anatomical Layers contract is:

- Full Volume

The browser must never fabricate or substitute missing anatomy. It does not load these assets when patient-volume rendering is unavailable.
