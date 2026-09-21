# Post-6F / Pre-6G Stabilization B1B2A — resident triangle visibility

Base: `60d66b9dc3175a9656c1faadbfa09486db9ad74c` on `phase6-accurate-surfaces` (GitHub).

This is the **browser-side reversible visibility engine**, not yet a shipped occlusion correction.
The B1B1 per-triangle region association is not yet transported through the authenticated
API or bound to a browser control. The user-visible Direct-CT slab is therefore unchanged.

`createDirectCtRegionVisibility` binds one byte per triangle to the exact resident mesh.
Labels 1/2 denote distinct ranked broad-support regions, **not** anatomy, patient, or
an acquisition support. Label 0 contains unresolved and other triangles and always
remains visible. On creation, the entire original index buffer is visible. An explicit
call to `show("hide-region-1")` or `show("hide-region-2")` compacts visible *indices*
within the SAME index attribute and adjusts its draw range, without re-extracting,
reallocating vertex buffers, changing topology of the source geometry, or writing
patient data. `show("all")` restores the exact original index order. Invalid/missing
or single-region evidence cannot enable region hiding.

The viewer requires the exact resident surface ID when binding evidence. Study change,
removal, or a new surface rebuild disposes its old binding. A profile/visualization
change does not call region logic or rebuild the surface. Binding and hiding must be
explicit; no region is automatically hidden on first load. Production, backend/API,
login, and existing visual behavior are unchanged in B1B2A.

Next: authenticate and transport compact, source-bound face labels to the browser;
add a clear 'Full geometry' restoration control and optional region presentation,
then run synthetic and real-study visual qualification. No clinical validation claimed.
