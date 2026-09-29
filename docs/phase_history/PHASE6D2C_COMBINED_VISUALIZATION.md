# Phase 6D2C — Combined visualization and surface-source presentation

Expected continuation base: `e96f0138bbfe55963b7069680d8ead3d641d64d7` on `phase6-accurate-surfaces`, with validated Phase 6D2A and 6D2B changes applied but not staged.

Phase 6D2C activates the locked **Combined** reconstruction mode and completes the explicit presentation separation between visualization mode and surface source without changing validated geometry generation.

## Combined mode

Combined mode becomes eligible only when the direct patient volume is resident and at least one selected surface source is already resident. It presents the existing direct volume together with the selected resident surface source(s). Mode changes never build, fetch, regenerate, clear, or dispose geometry.

The two surface-source identities remain:

- **Direct CT** — the Phase 6D1 canonical-volume CT isosurface.
- **Segmentation** — the existing Phase 6C refined segmentation surfaces selected explicitly by the user.

Compact source controls in the 3D View panel are presentation-only. They are enabled only when the corresponding geometry is resident. Deselecting a source hides it without removing it. Re-selecting it reuses the resident geometry immediately. The segmentation source also remains subordinate to the existing semantic **Show** lifecycle; visualization-source selection does not reactivate a semantically disabled segmentation surface layer.

The Phase 6D1 CT isovalue remains editable with the qualified **300 HU** baseline. Building a direct CT surface and selecting segmentation structures remain explicit actions. Combined mode and source selection do not start semantic segmentation or invoke surface extraction.

## Deliberate boundary

Phase **6D2D** remains responsible for final study-change, reset, removal, error/fallback and cross-mode qualification before Phase 6D2 closes.

No Phase 6E Fidelity/Presentation profile, lighting/material overhaul, or opacity-profile redesign is introduced here. No Phase 6F advanced grouping, clipping/isolation expansion, exploded view, or export behavior is introduced.

Clinical validation is not claimed.
