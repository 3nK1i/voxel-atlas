# Phase 6E-A — Fidelity / Presentation profile architecture

## Base and scope

Phase 6E-A continues from accepted Phase 6D2 commit `a7b8637460bc3c5ae657b4fd5ef8a8d5199ee474`. It introduces the presentation-profile state boundary for the locked Phase 6E scope without changing validated patient geometry, extraction, semantic segmentation, or the Volume / Surface / Combined visualization-mode system.

Exactly two profiles are defined: **Fidelity** and **Presentation**. Fidelity is the deterministic default. The profile controller is browser-local presentation state and is deliberately independent from reconstruction visualization mode and surface-source selection.

## Presentation-only contract

Changing the profile performs no API request, geometry build, geometry fetch, segmentation start, mesh replacement, Patient-LPS transform change, CT isovalue change, provenance mutation, or source-data mutation. The right-side 3D View panel exposes the profile choice and reports the selected rendering intent while geometry and source data remain unchanged.

This foundation does not yet apply lighting or material parameters. The shared lighting/material implementation belongs to **6E-B**. Fidelity profile qualification belongs to 6E-C, Presentation profile and the deferred skull/cavity lighting polish belong to 6E-D, Combined-mode visual balancing belongs to 6E-E, and real-study/manual closure belongs to 6E-F.

## Boundaries

Phase 6E-A does not modify the Phase 6A/6B segmentation-surface geometry, the Phase 6D1 volume-derived CT surface geometry or 300 HU baseline, or Phase 6D2 resident-geometry reuse. Phase 6F advanced grouping, exploded views, and expanded structure interaction remain out of scope.

Clinical validation is not claimed.
