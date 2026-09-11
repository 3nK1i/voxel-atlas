# Phase 6F-B — Non-destructive Show / Hide / Isolate / Restore

Phase 6F-B layers user-facing structure visibility interaction onto the 6F-A interaction-state foundation. It is a continuation of the qualified segmentation/surface presentation architecture, not a redesign.

## Scope

- Preserve `structure.visible` as the authoritative user Show/Hide state.
- Preserve `structure.surfaceVisible` as the existing explicit 3D surface-request state.
- Implement **Iso** as a transient `isolatedLabelId` presentation gate rather than rewriting either base state.
- Implement **Restore** by clearing only the transient isolation gate, immediately recovering the pre-isolation Show/Hide and surface-request choices.
- Apply effective visibility consistently to MPR segmentation overlays and resident 3D segmentation surfaces.
- Keep visible-label status text synchronized with the effective presentation.
- Keep Show all / Hide all / direct checkbox edits explicit: those commands leave isolation and then update the base user state.

## Precedence

```text
user Show/Hide state
        +
transient isolatedLabelId
        ↓
effective MPR / 3D visibility
```

Isolation never changes the underlying user visibility map. A structure that was hidden before isolation remains hidden after Restore. A structure that had an explicit 3D surface request retains that request through isolation and Restore.

A hidden structure may be isolated temporarily for MPR inspection, but isolation does **not** silently request or build its 3D surface.

## Geometry / I/O boundary

6F-B changes display state only.

- No surface extraction.
- No geometry rebuild.
- No new geometry fetch caused by isolate/restore.
- No vertex/index/topology mutation.
- No Patient LPS coordinate mutation.
- No segmentation inference.
- No source label-map mutation.
- No source CT/MR volume mutation.

Resident surfaces are visibility-gated using the 6F-A resolver. The explicit surface-request set remains the same while isolation is active.

## UI

The existing compact structure panel remains authoritative. `Show all`, `Hide all`, `Restore`, and `Reset` share the existing bulk-action row. Each structure retains the compact `Iso` action. The active isolated row exposes `aria-pressed=true`; the summary names the isolated structure.

`Reset` remains the full presentation reset. `Restore` is intentionally narrower: it only exits transient isolation.

## Regression compatibility

Historical Phase 5E / 6C behavior probes are updated only where their former destructive isolation expectation is intentionally superseded. The 6F-A foundation remains intact, including clipping-participation and exploded-offset state, while 6F-D and 6F-E remain disabled.

## Roadmap boundary

- 6F-C: per-structure transparency qualification across modes/profiles — not enabled here.
- 6F-D: per-structure clipping participation — not enabled here.
- 6F-E: anatomical group / bounded exploded presentation — not enabled here.
- 6F-F: final real-study interaction qualification / Phase 6F closure — not closed here.

No clinical validation or diagnostic claim is made.
