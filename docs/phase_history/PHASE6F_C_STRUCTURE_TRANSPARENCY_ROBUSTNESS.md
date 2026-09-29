# Phase 6F-C — Per-structure transparency robustness

Phase 6F-C hardens the existing per-structure opacity control without introducing a second opacity system. The user-selected structure opacity remains the authoritative value across Surface / Combined, Fidelity / Presentation, Show / Hide, and Iso / Restore transitions.

## Opacity investigation

Manual real-study evidence showed a noticeable visual change between about 85% and 100% opacity. The first inspection found a hidden near-opaque material threshold: segmentation surfaces began writing depth at `opacity >= 0.98` while remaining in the transparent queue until 100%. That made 98–99% inconsistent.

A real-study retest exposed a second discontinuity exactly at 100%: setting `transparent=false` moved the semantic segmentation surface into Three.js' opaque render queue. In Surface/Combined views, Direct CT presentation geometry could then render over or compete with the segmentation surface, washing out the semantic color even though user opacity was exactly 100%.

6F-C therefore keeps segmentation surfaces in the transparent render lane for the full 0–100% range. User alpha remains exact. Values below 100% keep depth writes disabled; exactly 100% uses alpha 1.0 with depth writes enabled, but remains in the transparent queue so the existing segmentation `renderOrder` keeps semantic overlays after Direct CT presentation surfaces.

A second real-study retest showed that this was sufficient in Combined mode but not Surface mode. The reason is deliberate Phase 6E-E balancing: Combined lowers Direct CT presentation opacity, which also disables Direct CT depth writes, while Surface mode previously restored Direct CT to alpha 1 with depth writes enabled. The opaque Direct CT depth buffer could therefore occlude a co-present 100% semantic surface before render order could help. Phase 6F-C now activates a display-only semantic-coexistence policy only when Surface mode has both Direct CT and Segmentation sources visible: Direct CT keeps exact alpha 1 but moves to the transparent render lane with depth writes disabled, allowing the semantic surface lane to remain visible. Direct-CT-only Surface mode remains unchanged. This is a rendering composition policy only: it does not offset, rebuild, or mutate geometry.

## Locked invariants

- Structure opacity is exact and user-authoritative.
- Profile, mode, isolation, and visibility changes do not overwrite opacity.
- No segmentation inference, mask mutation, geometry rebuild, vertex/topology mutation, or Patient-LPS transform change is introduced.
- The Phase 6B refined-to-accurate fallback remains unchanged.
- Phase 6F-D per-structure clipping is not enabled.
- Phase 6F-E exploded/group presentation is not enabled.
- Phase 6F-F final real-study qualification is not closed.
- No clinical validation claim is made.
