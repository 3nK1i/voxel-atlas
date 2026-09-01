# Authoritative visual reference contract

The supplied VoxelAtlas visual assets under `design/reference/` are authoritative product inputs and are covered by automated SHA256 checks.

- `logo.png` is the product logo and must be used as the visible VoxelAtlas brand mark.
- `login.png` is the authoritative login-page reference for composition, spacing, medical-blue tone, card treatment, and hierarchy.
- `ui.png` is the original dashboard reference that established the medical-tech design language and multi-panel imaging composition.
- `workspace_v1_target.png` is the **locked V1 workspace target** from Phase 2B. It is the primary reference for the production workspace layout, proportions, dark medical-blue treatment, workflow header, study panel, large 3D viewer, MPR row, directional-cut controls, anatomical layers, opacity, and actions.

## Phase 2B fidelity contract

The production workspace should reproduce `workspace_v1_target.png` at approximately **95-100% visual fidelity** where the target represents implemented functionality. Differences are allowed only when required for truthful runtime state, accessibility, responsiveness, or real application behavior.

The reference images are design evidence only. They **must never be used as a page background** or as a screenshot substitute for real controls. Every interactive control in the production workspace must have real behavior or be visibly disabled until its backing feature exists.

Phase 2B therefore keeps DICOM upload, patient volume, Brain, Skull + Brain, and MPR data in explicit unavailable/empty states until later V1 phases provide real medical data. The existing demo skull remains the only active anatomy layer in this shell.

`design/reference/SHA256SUMS` records the expected fingerprints of the exact reference files.
