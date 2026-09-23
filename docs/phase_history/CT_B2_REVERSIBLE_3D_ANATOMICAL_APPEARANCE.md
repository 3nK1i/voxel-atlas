# CT-B2 — Reversible 3D anatomical appearance

Base: `250d0167ec31ed65a54be72be51a3bc4bfbc69d8`, branch `phase6-accurate-surfaces`.

- Add a segmentation-surface-only appearance selector. Scientific (default) uses the saved per-structure colors; Anatomical applies 3D-only palette overrides for catalog groups `spine`, `skeletal`, and `muscles`. Costal cartilage and unclassified groups retain their label colors.
- CT-B1's `set3dColorOverrides` updates resident materials and future surface materials, without changing the shared `structure.colorHex` used in MPR, geometry, segmentation, coordinate systems, per-structure opacity or clipping policy.
- Switching to Scientific sends an empty override map and recovers the current user-edited label colors. A new canonical label-map ID resets the selection to Scientific. Control remains disabled until the surface descriptor and structure presentation match.
- Preset applies *only* color to existing segmentation surfaces. It cannot add anatomy not segmented or outside the source CT field of view. Nonclinical visualization; no clinical color semantics.

Validation: `bash scripts/run_ct_b2_checks.sh`, then focused local browser review in an already segmented CT study: Scientific → Anatomical → Scientific, MPR overlay unchanged, custom per-structure colors preserved, surface/combined mode transitions, label-map switch reset. Do not automatically run segmentation for the UI switch.
