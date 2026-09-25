# Phase 6J-D3 — MRI MPR overlays

## Scope

D3 exposes an already persisted, D2-qualified `total_mr` canonical label map through the existing Patient-LPS MPR segmentation overlay presentation path.

D3 does **not** authorize or execute MRI inference, import a new MRI result, alter the canonical MRI label map, resample labels, or make a clinical-validation claim.

## Integration

- The existing `SegmentationOverlayService` remains provider-neutral and unchanged.
- The existing structure catalog supplies the pinned `total_mr` MRI taxonomy.
- The read-only MRI workflow reports `available` only when a persisted label map matches the exact current source, succeeded source-bound MRI job, TotalSegmentator `total_mr` task, 50-label contract, and `clinical_validation=not_claimed`.
- An active source-bound MRI job keeps lifecycle-status precedence over any older persisted map.
- The browser may activate the already persisted MRI map for MPR visualization, but it never POSTs an MRI start request for that path.
- MRI activation deliberately does not initialize segmentation-derived 3D surfaces; that remains Phase 6J-D4.
- MRI activation does not enable correction-draft editing in D3; the sealed D2 label map remains presentation-only.
- MRI workflow states without a qualified persisted map retain the previous execution-disabled behavior.

## Safety invariants

- `mri_execution_authorized` remains `false`.
- `can_start` remains `false` for MRI.
- No TotalSegmentator invocation is added.
- No production MRI import is added or retried.
- MPR overlay sampling remains nearest-neighbor in Patient-LPS.
- CT workflow behavior remains unchanged.
- Clinical validation remains `not_claimed`.
