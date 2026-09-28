# Phase 6J-D4 — MRI segmentation-derived 3D surfaces

## Scope

Phase 6J-D4 reuses the existing provider-neutral segmentation-surface pipeline for the already accepted canonical `total_mr` MRI label map.

The step does **not** rerun TotalSegmentator, does not import a new MRI result, and does not threshold MRI intensities. The exact/reference MRI mesh remains the standard Phase 6A accurate surface artifact. The presentation-only refined derivative may now reconstruct a smoother display surface directly from the immutable canonical label map when the source descriptor is `MR / totalsegmentator / total_mr`.

## Integration contract

- The exact MRI label map advertised by the source-bound read-only MRI workflow is the only map eligible for D4 activation.
- The MPR overlay descriptor must already identify `MR / totalsegmentator / total_mr`.
- The segmentation-surface descriptor must remain bound to the same active label-map ID and current study and must identify `MR / totalsegmentator / total_mr` with `clinical_validation=not_claimed`.
- Existing Patient-LPS accurate/reference extraction, SHA256 verification, structure colors, clipping, exploded presentation, and Surface/Combined mode controller are reused unchanged.
- The MRI `total_mr` display derivative uses a dedicated bounded refinement profile to reduce coarse stair-step presentation. The exact/reference surface remains immutable and available.
- CT keeps the original Phase 6B refinement policy unchanged.
- Structure-to-3D selection remains explicit. D4 does not automatically build all labels from a 50-class MRI result.
- MRI correction/editing remains outside this step.
- CT behavior remains unchanged.

## Presentation-quality correction

The first D4 attempt proved that stronger post-mesh Taubin smoothing alone was not sufficient for the accepted MRI `fastest` label map. The corrected D4 profile therefore keeps the accurate/reference mesh unchanged and upgrades only the presentation derivative:

- the immutable canonical MRI label map is loaded again inside the isolated refinement worker,
- a bounded Gaussian-smoothed presentation field is reconstructed from the selected binary label,
- a new Patient-LPS presentation mesh is extracted from that smoothed field,
- the result is accepted only if the repaired closed-manifold topology matches the repaired reference topology,
- the presentation derivative remains constrained inside canonical voxel-cell bounds,
- the presentation derivative remains explicitly non-clinical,
- scientific reconstruction stays isolated in the already-qualified Phase 6A surface runtime; `scikit-image` is not added to the normal application virtualenv,
- if the MRI presentation reconstruction cannot satisfy its topology and displacement qualification gates, the refined build fails closed instead of silently falling back to the old blocky presentation path.

For this MRI-only display profile, the maximum accepted presentation deviation is bounded to **3.0 mm**. This bound is intentionally larger than the minimum native voxel spacing because the visible staircase artifact comes from the accepted provider grid (`fastest` total_mr import), not from the browser renderer. The exact/reference surface remains the provenance anchor.

## User-visible result

Once an MRI structure is explicitly selected for 3D, its segmentation-derived Patient-LPS surface can be built and shown in the large 3D viewport. After resident geometry exists, the normal `Surface` and `Combined` visualization modes become available using the existing mode controller.

The refined MRI surface is a presentation derivative, not a new segmentation. It can reduce voxel stair-stepping but cannot recover anatomical detail that is absent from the accepted segmentation mask. The accurate/reference mesh remains the provenance anchor.

## Safety

- `MRI_INFERENCE=NOT_RUN`
- `PRODUCTION_MRI_IMPORT=NOT_RUN`
- `MRI_INTENSITY_THRESHOLD_SURFACE=NOT_USED`
- `MRI_REFERENCE_SURFACE=UNCHANGED`
- `MRI_PRESENTATION_RECONSTRUCTION=GAUSSIAN_LABEL_MAP_ISOSURFACE`
- `MRI_PRESENTATION_MAX_DISPLACEMENT_MM=3.0`
- `CLINICAL_VALIDATION=NOT_CLAIMED`
