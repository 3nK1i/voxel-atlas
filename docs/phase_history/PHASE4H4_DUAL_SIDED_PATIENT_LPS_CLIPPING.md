# Phase 4H4 - Dual-Sided Six-Plane Patient LPS Clipping

## Scope

Phase 4H4 upgrades each Axial, Coronal, and Sagittal clipping control from one retained-side plane to an independently adjustable anatomical range. Each enabled axis contributes two physical boundaries, producing six Patient LPS clipping planes in total:

- Axial: Inferior to Superior
- Coronal: Posterior to Anterior
- Sagittal: Right to Left

The former retained-side dropdowns are removed. Each compact dual-handle control reports both ergonomic percentage positions and both physical Patient LPS coordinates in millimetres. Handles cannot cross, and Reset clipping disables every axis and restores the full-volume range.

## Medical and geometric contract

Patient LPS uses positive X toward Left, positive Y toward Posterior, and positive Z toward Superior. Axial and Sagittal ergonomic direction therefore follow increasing physical coordinates. Coronal is intentionally reversed in the control: Posterior starts at the maximum Y coordinate and Anterior ends at the minimum Y coordinate. Before rendering, each pair is sorted into its true physical minimum and maximum.

Enabled ranges intersect into one rectangular patient-space region of interest. The renderer clips ray entry and exit against both physical boundaries on every enabled axis before sampling. The same bounds also reject samples in Slice and Thick Slab modes, so Volume / DVR, MIP, MinIP, Average Intensity, Slice, and Thick Slab all obey the same region.

Clipping state is independent from the synchronized MPR crosshair. Adjusting a clipping boundary does not move or re-render MPR navigation. Phase 4H4 does not add clipping overlays to MPR panels; that visualization is reserved for Phase 4H5.

All clipping changes update shader uniforms only. The verified RG8 texture remains resident and the canonical medical volume, CT HU or MR relative-intensity semantics, transfer settings, and provenance remain unchanged.

## Validation

The H4 checks cover all six physical boundaries, bounded and non-crossing ranges, the reversed coronal ergonomic mapping, shader interval intersection, all rendering modes, same-texture/resource identity, MPR crosshair independence, accessibility, removal of retained-side dropdowns, full prior regression, JavaScript and Python syntax, diff whitespace, and patient-data Git safety.

Run:

```bash
bash scripts/run_phase4h4_checks.sh
```
