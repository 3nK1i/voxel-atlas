# Phase 4A - Anatomical Reconstruction Foundation

Phase 4A establishes the patient-specific anatomical reconstruction boundary without yet producing a skull or brain surface.

## Scope

- Reuse the qualified Phase 3 canonical patient volume as the only reconstruction input.
- Validate the canonical float32 array, shape, spacing, axis order, and invertible DICOM patient-LPS affine before reconstruction work starts.
- Define a stable provider boundary for future skull and brain reconstructors.
- Define one canonical internal triangle-mesh contract in **patient LPS millimetres**.
- Persist anatomy artifacts under the study-derived area, with source-volume descriptor identity, algorithm provenance, mesh counts, physical bounds, and SHA256.
- Reject stale anatomy when its source-volume descriptor identity no longer matches the current canonical volume.
- Expose an authenticated, `no-store` reconstruction-status endpoint without exposing internal filesystem paths or raw provider parameters.

## Modality qualification at this checkpoint

- **Skull:** qualified reconstruction input is CT with HU intensities.
- **Brain:** first V1-qualified reconstruction input is MR. CT brain reconstruction is not claimed by this foundation.

These are source-qualification rules only. Phase 4A does not claim that a reconstruction provider is already implemented.

## Canonical anatomy artifact

Future reconstructors return:

- `vertices_lps_mm`: `N x 3` finite vertex coordinates in DICOM patient LPS millimetres.
- `faces`: `M x 3` integer triangle indices.

The publisher stores a private compressed NPZ mesh plus JSON provenance. The browser does not receive the private artifact path. A web-ready representation is intentionally deferred until the patient-specific viewer integration step.

## Dependency boundary

Phase 4A requires no new heavy runtime dependency. `numpy` is already a Phase 3C backend dependency. `scipy`, `scikit-image`, `SimpleITK`, `trimesh`, and `pyvista` remain in the deferred medical-processing inventory until a later reconstruction implementation explicitly qualifies and promotes the required subset.

## Real-data qualification probe

After applying Phase 4A to a workstation that already contains the qualified Phase 3 patient volume, run:

```bash
python scripts/check_phase4a_latest_reconstruction_input.py
```

For the current real CT study, the expected foundation result is a present canonical source with `SKULL_INPUT_ELIGIBLE=YES` and no anatomy artifact claimed ready yet.

## Next steps

- **Phase 4B:** implement and validate the first real CT skull reconstructor and publish the patient skull through this contract.
- **Phase 4C:** implement and validate the first real MR brain reconstructor.
- **Phase 4D / Phase 5:** qualify multi-layer patient-space alignment and connect real Skull / Brain / Skull + Brain layers to the Three.js viewer.
