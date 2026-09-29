# Phase 6F-A — Structure interaction state architecture

Phase 6F-A establishes the provider-neutral, non-destructive state foundation for advanced anatomical structure interaction. It is a continuation of the qualified Phase 6E presentation architecture, not a rendering or geometry redesign.

## Scope

The existing segmentation structure presentation remains authoritative for semantic color, user visibility, explicit 3D-surface request state and per-structure opacity. Phase 6F-A adds only transient interaction state and future-facing display controls:

- one optional isolated structure identifier at presentation level;
- per-structure clipping participation, defaulting to enabled;
- per-structure exploded display offset in Patient LPS millimetres, defaulting to `[0, 0, 0]`;
- a pure resolver that computes effective display state without mutating the underlying user state.

Isolation precedence is intentionally non-destructive: when an isolation target is active it controls effective visibility, while the original user `visible` values remain unchanged for later restoration. Explicit 3D surface request state remains independent, so interaction-state resolution cannot silently request or build geometry. User opacity remains authoritative and is returned unchanged by the interaction resolver.

## Safety and provenance boundaries

- No geometry rebuild.
- No geometry fetch.
- No marching-cubes execution.
- No segmentation execution.
- No vertex, index, topology or Patient LPS coordinate mutation.
- Exploded offsets are display-state metadata only; Phase 6F-A does not apply them to meshes.
- Clipping participation is state only; Phase 6F-A does not change clipping behavior.
- Fidelity / Presentation profiles remain independent of structure interaction state.
- No clinical validation or regulatory claim is made.

## UI boundary

Phase 6F-A intentionally adds no new user controls. The existing Phase 5E `Iso` action remains unchanged in this step. Phase 6F-B will wire Show / Hide / Isolate / Restore to the new non-destructive interaction model after this foundation is qualified.

## Locked continuation roadmap

- **6F-B** — Show / hide / isolate / restore using the non-destructive state model.
- **6F-C** — Robust per-structure transparency across visualization modes and presentation profiles.
- **6F-D** — Per-structure participation in the existing clipping system.
- **6F-E** — Anatomical grouping and bounded exploded presentation using display transforms only.
- **6F-F** — Final real-study interaction qualification and Phase 6F closure.
