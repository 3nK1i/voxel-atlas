# Phase 6F-E — Anatomical group and bounded exploded presentation

Phase 6F-E activates the exploded-display state established in Phase 6F-A. It is a narrow interaction/presentation continuation of the qualified Phase 6F-D clipping work, not a geometry or reconstruction redesign.

## Scope

The Anatomical Structures panel exposes one **Explode anatomy** control. The control separates segmentation-derived 3D surfaces by anatomical group while preserving the internal spatial relationship of structures that belong to the same group.

- The provider-neutral structure catalog remains authoritative for anatomical group membership.
- All structures in one anatomical group receive the same display offset.
- Group directions are deterministic from catalog order and do not depend on transient visibility, loading order, or camera state.
- Separation is bounded to **40 mm** in Patient LPS display-state metadata.
- `0 mm` is canonical presentation and restores every exploded offset to `[0, 0, 0]`.
- The existing per-structure `explodedOffsetLpsMm` state remains the authority consumed by the 3D segmentation surface viewer.

## display-only transform boundary

Exploded presentation is applied with a Three.js mesh transform after the immutable segmentation surface geometry has already been decoded and transformed from Patient LPS into viewer coordinates. The vertex/index buffers are not rewritten.

Directional Cut remains defined in canonical Patient LPS. When a segmentation surface is visually displaced, its material clipping planes receive the same display translation so the already-defined Patient-LPS cut continues to intersect the same anatomical portion of that structure. Per-structure `Follow Directional Cut` participation from Phase 6F-D remains authoritative.

## State preservation

Changing exploded separation does not overwrite:

- Show / Hide choices;
- isolation / restore state;
- explicit 3D surface request state;
- semantic color;
- user structure opacity;
- per-structure Directional Cut participation;
- Fidelity / Presentation profile state.

MPR overlays remain in canonical Patient LPS and are intentionally **not exploded**. Direct CT volume/surface geometry is also not translated by this control; exploded presentation is a semantic segmentation-surface inspection aid only.

## Safety and provenance boundaries

- No geometry rebuild.
- No geometry fetch caused by the exploded transform itself.
- No marching-cubes or refinement execution.
- No vertex, index or topology mutation.
- No source label-map mutation.
- No Patient LPS provenance mutation.
- No Direct CT geometry mutation.
- No segmentation execution.
- No clinical validation or regulatory claim is made.

## Continuation

**Phase 6F-F** owns the final real-study interaction qualification and Phase 6F closure. The known Direct CT 300-HU slab/occlusion investigation remains deliberately separate from 6F-E and is deferred until Phase 6F interaction work is closed.
