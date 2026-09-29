# Post-6F / pre-6G Stabilization B2A — segmentation viewer face orientation

Expected base: GitHub `phase6-accurate-surfaces` HEAD `ede3db9148fe59cc822e61c1893467de7984a619`, clean tree. This is a **narrow browser-only presentation correctness change**, not another segmentation extraction or a clinical fidelity claim.

## Source review and issue

`phase6a_surface_worker.py` canonicalizes each accurate Patient-LPS surface's face winding and derives vertex normals to match that winding. The browser's fixed Patient LPS -> viewer matrix in `segmentation-surface-viewer.js` maps `(L,P,S)` to `(-L,S,-P)` with a positive scale; its linear determinant is **negative**. `BufferGeometry.applyMatrix4()` transforms positions and normals but does not reverse the triangle indices. The existing segmentation material uses `FrontSide`; reflected triangle winding can consequently disagree with transformed normals and cause front-face culling/shading inconsistencies. This property was established from the source matrix and a synthetic triangle calculation; it has **not** yet been visually qualified on a real study.

## Correction and invariants

For every newly received segmentation surface, create a **separate viewer-only** index array with each triangle's second and third indices exchanged *before* applying the existing viewer transform. No triangle, vertex or index is dropped; index-buffer length and per-triangle membership remain constant. The decoded authoritative VXSF source indices, positions, normals, payload bytes, SHA256, reference surface ID, provenance and Patient LPS geometry remain unchanged. For v2, the supplied normals become geometrically consistent with the reflected viewer triangles. For legacy v1, vertex normals are calculated as before, after applying the matrix. The original material profiles, colors, opacity, clipping, structure interactions, surface quality and accurate fallback behavior remain unchanged. No new surface build or network request is introduced; the correction applies once per new resident segmentation mesh, not on profile/mode switches.

The new test imports the *actual* viewer transform, verifies the negative determinant, proves the transformed face normal aligns only after swapping winding, checks source index buffer immutability and double-swap roundtrip, and verifies the viewer consumes the helper. Selected Phase 6A/6B/6C/6E/6F and B1B2 regression checks are rerun by `scripts/run_post6f_pre6g_stabilization_b2a_checks.sh`.

## Qualification and limits

Run the automated script on the full development checkout first. Then in the **already isolated local preview only**, view a small representative set of existing segmentation structures at a fixed camera angle in Surface/Presentation and confirm their visible *exterior* is not unexpectedly inverted, absent or less readable. Briefly switch Fidelity/Presentation and check that their original per-structure colors and visibility controls remain intact. This does **not** promise a complete skull from an incomplete CT, recover missing segmentation structures, certify anatomical accuracy, or eliminate legitimate internal cavities or acquisition boundaries. If real-study presentation regresses, leave B2A uncommitted and report the observed structure/angle before any broader change. Phase 6G must use the original accurate Patient-LPS surface and canonical mask, never the viewer-space index winding or any presentation-only visibility settings.

No production change, login deployment, commit or push is included in this patch.
