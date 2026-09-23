# CT-B1 — 3D-only segmentation surface color override foundation

CT-A found that editing the existing structure color also changes the MPR segmentation overlay. CT-B1 adds an internal, label-map-scoped presentation override only to the segmentation **3D surface material**, preserving `structure.colorHex`, canonical label maps, existing structure controls, patient geometry, MPR overlays, opacity, clipping and surface quality.

The viewer exposes `set3dColorOverrides(Map<labelId, "#rrggbb">)`. The input is validated before any resident material is modified; passing an empty Map restores source colors. An override is retained when changing the internal lighting/presentation profile, refreshing structure presentation and creating newly requested surface materials. Overrides are cleared when the label-map identity changes or the surface layer is cleared. No color change triggers segmentation, a surface fetch, or mesh regeneration.

This is an **API-only foundation**. CT-B2 must determine anatomical label-classification and present a reversible user-facing appearance control. No automatic anatomical color classification, color persistence across reloads, UI button, or MRI support is claimed here. The existing scientific/label color presentation is unchanged unless the new API is explicitly invoked.

Validation: `bash scripts/run_ct_b1_checks.sh`; existing CT and MPR manual review should be focused on unaffected behavior. Nonclinical research visualization; this change does not establish anatomical or clinical qualification.
