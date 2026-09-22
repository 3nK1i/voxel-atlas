# Phase 6I-B2 — existing segmentation surfaces in automatic presentation

Baseline: `c1f019b6e7f3d66eb718048313ca67c80ac20397` on
`phase6-accurate-surfaces` after Phase 6I-B1 was validated, committed and pushed.

## Narrow changes

- Continue using the existing Phase 6I-B1 mode coordinator and both existing
  surface layers. Direct CT presentation and patient-volume rendering remain
  unchanged. No new segmentation job is launched from a mode or source switch.
- Surface/Combined can wait for a **previously activated, study-bound** label
  map's **explicitly selected** 3D structures if segmentation is enabled and
  selected as a surface source. Resident geometry is reused; loading is
  already de-duplicated by the existing segmentation layer.
- The gate is tied to the active study and label-map identity. A new study,
  deselection, disabled segmentation surfaces, a later mode request, or a
  terminal surface error invalidates pending presentation intent. Hiding
  surfaces in Volume does not erase resident geometry.
- Segmentation sources become selectable when the corresponding activated
  label-map descriptor is ready, without waiting for a mesh to be resident.
  No structure is selected automatically; the Phase 6D0 explicit structure
  selection policy remains unchanged.
- The existing **Use Segmentation** action receives only scoped visual styling
  when an existing result is ready. Its original activation handler and
  on-demand job semantics are unchanged.
- Patient-LPS source binding, per-label Accurate/Refined requests, the
  previously documented Refined HTTP 422 -> Accurate fallback, geometry
  provenance, structure visibility and clipping are untouched.

## Local acceptance (non-clinical)

1. From an existing qualified development CT with a pre-existing segmentation,
   use **Use Segmentation** explicitly, select a visible 3D structure, deselect
   Direct CT in Surface sources, and verify Surface/Combined display the
   segmentation-derived geometry. If no pre-existing label map exists, mark
   this path **NOT TESTED**; do not run an expensive job merely to test B2.
2. Switch to Volume, then Surface; previously resident segmentation geometry
   should be reusable. With a fresh selected surface (if safely available),
   switch quickly to Volume during loading; stale work must not force Surface.
3. Unselect Segmentation as a surface source and verify that it is not shown;
   previously selected Direct CT still works, and disabling 3D segmentation
   does not remove the source label map.
4. Verify the existing Use Segmentation button is readable, keyboard focus is
   visible, and its original explicit behavior is unchanged. Confirm MPR,
   6I-A help and Direct CT Surface/Combined/Volume remain functional.

Browser acceptance, scientific worker validation, Git review, and production
qualification are separate gates. No clinical validation is claimed.
