# Phase 6E-B — Shared lighting and material foundation

Expected base: `4c6fa747e4f14eb5e28e0e4b42536b992acba805`.

Phase 6E-B centralizes the 3D surface lighting and material policy used by both direct CT volume-derived surfaces and segmentation-derived surfaces. Fidelity and Presentation now drive rendering parameters through one presentation-only module while validated patient-space geometry, topology, source data, semantic labels, opacity, and provenance remain unchanged.

The shared lighting rig replaces duplicated inline scene-light constants. Direct CT and segmentation surface layers can update resident material parameters in place when the presentation profile changes; switching profiles performs no geometry build, geometry fetch, segmentation start, geometry disposal, or patient-space transform change. Segmentation colors continue to come from each structure's `colorHex` and structure opacity remains authoritative.

6E-B establishes the shared runtime and safe profile binding. 6E-C remains responsible for Fidelity-profile qualification. 6E-D remains responsible for final Presentation-profile tuning, including the deferred superior-skull/cavity readability problem. Combined-mode balancing remains later in 6E. Phase 6F advanced interaction is not enabled.

Clinical validation is not claimed.
