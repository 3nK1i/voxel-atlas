# Post-6F / Pre-6G Stabilization A

## Scope

This step is a narrow stabilization checkpoint after Phase 6F closure and before Phase 6G.
It does not claim the Direct-CT 300 HU slab issue is fixed yet. It establishes evidence and
low-risk UI/loading improvements before a data-driven Direct-CT correction.

Authoritative base: `f47e984c8cc4dd0e04544dba4e1d6782ffb499b0`.

## Direct-CT diagnostic

`scripts/diagnose_post6f_direct_ct_surface.py` inspects the immutable canonical CT volume
without writing to it. It reports connected components at the current Direct-CT isovalue
(default 300 HU) and at a broad body-support threshold (default -500 HU), including component
size, index bounds, boundary contact, flatness, and fill ratio.

The diagnostic deliberately does not remove the largest component or apply a filtering policy.
The next Direct-CT correction must be chosen from real-study evidence so valid anatomy is not
silently deleted.

## Study-loading diagnostic and safe overlap

`scripts/diagnose_post6f_study_loading.py` times read-only stages that are relevant when an
already-ingested study is reopened: latest-study lookup, MPR descriptor lookup, prepared volume
rendering inspection/artifact validation, and strict sample-payload verification when the latest
study is a bundled sample.

The browser now prestarts the independent GPU-volume path before awaiting synchronized MPR.
The existing task de-duplication remains authoritative, so the later await reuses the same task.
This changes orchestration only; it does not weaken study identity or sample-integrity checks.
Further caching or backend optimizations are deferred until timing evidence identifies the
material bottleneck.

## Right-sidebar UX

The right sidebar now follows a global-to-specific decision order:

1. Volume Rendering
2. 3D View
3. Direct CT Surface
4. Segmentation
5. Segmentation Overlay
6. 3D Segmentation Surfaces
7. Anatomical Structures
8. Directional Cut
9. Segmentation Review

Within Volume Rendering, Rendering quality precedes Medical preset, Rendering mode, contextual
mode controls, Window level/width, and Advanced rendering.

A shared sidebar action-button language is applied to primary, secondary, destructive, and
compact actions. Direct-CT `Build Surface` / `Remove Surface` are equal-height, equal-width
sibling actions rather than one oversized button plus floating text.

## Preserved boundaries

- Canonical CT voxel values remain immutable.
- Patient LPS remains unchanged.
- Direct-CT default provenance remains 300 HU.
- No Direct-CT component is removed in this step.
- Segmentation masks/surfaces are unchanged.
- Phase 6F interaction behavior remains frozen.
- Phase 6G quantitative surface-to-mask fidelity is not enabled.
- No clinical validation is claimed.

## Manual validation required

Validate the right sidebar at 1366x768 and at a larger desktop resolution. Confirm that the
Volume Rendering hierarchy is readable, all action buttons are coherent, no controls are lost,
and scrolling remains usable. Reopen at least two ready studies and confirm MPR/3D volume both
restore correctly. Run both read-only diagnostics and preserve their text output as evidence for
the next stabilization step.
