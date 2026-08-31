# Phase 2A — VA workspace migration and VB retirement

## Product decision

Phase 2A makes the authenticated `/workspace` use the retained VA cranial-opening lineage while adopting the compact production workspace layout. The change is an intentional migration, not a redesign from an unrelated implementation.

## Kept

- exact `prototypes/v2b3a/` source and GLB as preserved engineering evidence
- continuous GPU cranial aperture behavior, calibrated around the existing 58% standard opening
- interactive Three.js camera controls
- directional sectioning
- Clinical rendering
- skull opacity
- reset and auto rotate

## Removed

- the previous `<model-viewer>` skull-demo workspace
- AR entry points and AR-specific browser behavior
- XR / Holo / visual-preset controls
- `prototypes/v2b3b/` and its dedicated smoke checker from the current tree

VB remains available through Git history and the verified handoff archive.

## Anatomical-layer contract

The production workspace exposes the V1 target states Skull, Brain, and Skull + Brain. Skull is available now. Brain and Skull + Brain remain disabled until a real co-registered `web/assets/models/brain.glb` exists. No synthetic placeholder anatomy is rendered.

Atlas interaction is explicitly post-V1.

## TDD evidence

The Phase 2A contract was written first against the accepted Phase 1C checkpoint and failed because the old model-viewer workspace, AR/preset behavior, and VB tree were still present. The migration then implemented only the product decisions above.
## Final ergonomic correction

Manual browser validation of the migrated workspace showed that the first-load camera was too close to the skull. Before Phase 2A closure, the production viewer restored the proven VA camera framing from `prototypes/v2b3a`: the same oblique camera direction, larger starting distance, and VA zoom bounds. The workspace action label is `Logout`, and the login heading is the concise `Login`. These are presentation-only corrections; authentication behavior, cranial aperture calibration, clipping, Clinical rendering, and the anatomical-layer contract are unchanged.

Application-facing page titles use a plain ASCII hyphen (`-`) rather than an em dash, including `VoxelAtlas - Login` and `VoxelAtlas - Anatomy Workspace`.
