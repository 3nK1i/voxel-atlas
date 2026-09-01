# Phase 2B - Final V1 workspace target alignment

## Goal

Phase 2B freezes and implements the final V1 workspace shell before DICOM ingestion and patient reconstruction begin.

The authoritative visual target is:

```text
design/reference/workspace_v1_target.png
```

with expected SHA256:

```text
02994e3e1bd56e914d4da1c442c1037346699f67ddeffd6c47d962656af92c9d
```

The target is implemented as real HTML/CSS/JavaScript rather than a screenshot background. The visual goal is approximately 95-100% fidelity where functionality is available.

## Locked workspace structure

- VoxelAtlas branding
- ergonomic dark/light theme toggle
- Data -> Reconstruction -> 3D Visualization workflow header
- Study / Reconstruction / Data left panel
- large interactive Three.js viewer
- real viewer toolbar: fit, zoom in, zoom out, fullscreen
- Axial / Coronal / Sagittal MPR panels
- directional anatomical cut as the sole V1 sectioning system
- Full Volume / Skull / Brain / Skull + Brain layer architecture
- future Skin / Sinuses / Vessels placeholders
- opacity
- reset
- auto rotate
- Logout

## Truthful pre-data state

Phase 2B does not invent patient data. DICOM upload remains visibly planned for Phase 3. The MPR panels show explicit empty states, and only the current demo Skull layer is active. Full Volume, Brain, and Skull + Brain remain disabled until later reconstruction phases provide real patient-derived layers.

The viewer no longer auto-loads a static brain file. Later phases register reconstructed layers through the shared layer registry.

## Intentional retirement

Phase 2B removes both historical prototype directories plus the specialized demo-only scripts/model artifact associated with behavior outside the locked V1 product. Git history and the verified handoff archive preserve that historical evidence.

## TDD sequence

The Phase 2B contract was written first against the accepted deployed Phase 2A checkpoint. It failed on the missing final target asset, missing workflow/theme/MPR shell, missing viewer toolbar/layer registry, and still-present retired behavior. Implementation followed only after that expected red state was captured.

## Visual-density refinement

The first real-browser comparison against the frozen target showed that the shell structure was correct but desktop density was too small. The accepted Phase 2B refinement therefore removes the 1600 px desktop cap, scales the header and side panels proportionally, increases the MPR share of the workspace, raises desktop typography/control floors, and tunes the clinical skull material to avoid near-opaque transparency sorting artifacts. The functional scope is unchanged.

`run_phase2b_checks.sh` is intentionally compact on success and prints detailed captured output only when a check fails.
