# Phase 4H3A - Medical projection rendering modes

## Scope

Phase 4H3A adds three scalar projection modes beside the existing Volume / DVR renderer:

- MIP selects the maximum sampled medical intensity along each clipped ray.
- MinIP selects the minimum sampled medical intensity along each clipped ray.
- Average Intensity computes the arithmetic mean of the sampled intensities.

Volume / DVR remains the default and preserves the existing front-to-back transfer-function compositing.

## Medical and geometric contract

All four modes sample the same verified GPU 3D texture derived from the authoritative canonical patient volume. A mode change updates one shader uniform and schedules a new render; it does not fetch, reconstruct, re-upload, or mutate the patient volume.

Projection aggregation occurs over samples inside the selected intensity interval and over the ray segment already limited by the active DICOM Patient LPS clipping planes. Window center/level and width are applied after the scalar projection. Intensity minimum and maximum remain independent cutoff boundaries, and Overall opacity remains available. DVR-specific Absorption, Opacity softness, Edge definition, and Depth shading controls are disabled while a projection mode is active so their applicability is explicit.

CT values retain HU semantics. MR values retain native relative-intensity semantics and are never labeled as HU. These modes are derived views of real patient voxels; they are not segmentation, surface extraction, or replacement of the canonical medical volume.

## Validation

The H3A checks cover deterministic projection reference values, mode metadata and UI wiring, shader ordering, uniform-only switching with the same texture/material/resource identities, canonical-volume and Patient LPS invariants, JavaScript and Python syntax, the full prior regression, diff whitespace, and patient-data Git safety.

Run:

```bash
bash scripts/run_phase4h3a_checks.sh
```
