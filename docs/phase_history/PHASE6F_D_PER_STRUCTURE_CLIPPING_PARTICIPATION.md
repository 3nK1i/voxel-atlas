# Phase 6F-D — Per-structure clipping participation

Phase 6F-D activates the clipping-participation state introduced in Phase 6F-A without introducing a second sectioning system. The existing Directional Cut remains the only source of axial, coronal and sagittal Patient-LPS clipping bounds.

## Scope

- The selected anatomical structure gains one compact **Follow Directional Cut** checkbox.
- Structures default to participating in Directional Cut.
- Turning participation off leaves that resident segmentation surface intact while other participating surfaces continue to follow the same cut bounds.
- Direct CT surfaces follow Directional Cut so Surface and Combined modes section the CT-derived context consistently with the patient volume.
- Patient-LPS clipping bounds are converted into viewer-space material clipping planes only after geometry has already been transformed for display.
- Three.js local clipping is enabled once for surface materials.

## Invariants

- `clippingEnabled` remains part of the existing structure interaction state; no duplicate clipping state is introduced.
- Directional Cut owns the clipping bounds. Phase 6F-D does not create independent per-organ clipping planes.
- Clipping is display-only. It does not mutate vertices, indices, topology, source labels, canonical volumes, Patient-LPS coordinates or provenance.
- Changing clipping participation does not run TotalSegmentator, marching cubes, refinement or any other geometry-generation pipeline.
- Show/Hide, Iso/Restore, semantic color, exact per-structure opacity, refined→accurate fallback, Fidelity/Presentation and Surface/Combined semantics remain independent.
- Phase 6F-E exploded presentation remains disabled.

## Manual qualification

Use a real CT with Direct CT plus at least two resident segmentation surfaces.

1. In Surface mode, move one Directional Cut boundary so Direct CT and both segmentation surfaces are visibly clipped.
2. Select one segmentation structure and turn **Follow Directional Cut** off. That structure must become whole while Direct CT and the other participating structure remain clipped.
3. Turn the checkbox back on. The same structure must immediately return to the shared cut without any surface rebuild.
4. Repeat the participation toggle in Combined mode.
5. Preserve a distinctive opacity, then perform Fidelity→Presentation→Fidelity, Surface→Combined→Surface and Iso→Restore. Opacity and clipping participation must survive unchanged.
6. Clear the browser Network panel before toggling participation and moving existing clipping bounds. These display-only actions must not issue new segmentation-surface or volume-surface geometry requests.
7. Verify Reset returns clipping participation to enabled for structures through the existing structure reset semantics.

This is a visualization interaction feature only and does not constitute clinical validation.
