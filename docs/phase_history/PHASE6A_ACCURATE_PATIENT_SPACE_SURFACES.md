# Phase 6A - Accurate Patient-Space Surfaces

## Scope

Phase 6A evolves the existing Phase 5F1 segmentation-surface pipeline. It does not create a second visualization stack. The existing study binding, canonical label-map service, authenticated FastAPI route, structure-panel synchronization, Three.js anatomy group, and combined volume integration are preserved.

The Phase 5F1 voxel/block-face surface remains available only as an explicit legacy preview. The application default is now the accurate Phase 6A artifact.

## Accurate extraction contract

For one requested nonzero label that is actually present in the immutable canonical `uint16` label map:

1. The backend validates current-study ownership, canonical Patient LPS metadata, source artifact shape/dtype, and the canonical label-map SHA256.
2. The occupied-label bounding box is found with bounded slice-wise scanning rather than a full-volume coordinate list.
3. An isolated medical-processing worker crops the native-resolution mask and adds a one-voxel zero exterior.
4. `skimage.measure.marching_cubes` extracts the binary 0.5 interface without smoothing or simplification.
5. The zero exterior places boundary-touching surfaces at the correct voxel-cell envelope: `-0.5` and `N-0.5` in array-index coordinates.
6. Vertices are transformed with the complete canonical `array_index_to_patient_lps` affine. Axis alignment, identity transforms, positive determinant, and isotropic spacing are not assumed.
7. Winding is reconciled once, globally, after the affine, including reflected/negative-determinant transforms. The interpolated marching-cubes gradient normals are used as an inside/outside orientation reference rather than an absolute per-triangle acceptance test, and deterministic area-weighted vertex normals are then produced from the final Patient-LPS triangle geometry.
8. A versioned v2 binary payload transports Patient-LPS float32 positions, Patient-LPS float32 normals, and uint32 triangle indices. SHA256 is verified by the browser before geometry is accepted.

## Identity and provenance

An accurate surface receives a deterministic `surf-...` identity derived from an immutable provenance record covering the label-map artifact, source study/series, source canonical volume digests, segmentation job terminal provenance, provider/model/task identity, provider mask digest, complete transforms, requested label, surface schema, extraction algorithm version, and the qualified isolated runtime fingerprint (Python, NumPy, and scikit-image versions). A runtime change therefore cannot silently reuse an artifact identity created by a different scientific stack.

The canonical source label map is read-only. Surface generation never writes back to `labels.npy`. Temporary patient-derived mesh bytes are created only under the private data hierarchy and removed after the response artifact has been loaded into memory.

## Compatibility

The existing Phase 5F1 v1 `preview` and `balanced` artifacts remain supported for regression and temporary fallback. The same `/api/studies/latest/segmentation-surfaces/{label_id}` route is retained. The default `quality` is now `accurate`; `preview` and `balanced` remain explicit legacy values.

The browser decoder accepts both v1 and v2 payloads. V2 consumes server-provided Patient-LPS normals; v1 continues to compute viewer normals locally.

The workspace presents the active default artifact as a **Patient LPS accurate surface** and uses Phase 6A cache identities for both the application module and segmentation-surface viewer. The legacy Phase 5F1 preview path remains explicit compatibility behavior and is not labeled as the active accurate artifact.

## Resource bounds

Phase 6A is one-structure-at-a-time and does not eagerly mesh all present structures. ROI voxels, vertices, triangles, payload bytes, worker report size, and worker runtime are bounded. Exceeding a bound fails explicitly; Phase 6A does not silently apply later mesh-refinement policy.

`scikit-image` remains outside `requirements/backend.txt` and is imported only by the isolated surface worker. Phase 6A provides a narrow `requirements/segmentation-surfaces.txt` runtime profile containing only NumPy and scikit-image rather than requiring the full optional medical-processing stack. The runtime is configured explicitly with `VOXELATLAS_SURFACE_PYTHON` and qualified through a subprocess probe; the FastAPI backend import/startup path neither imports nor initializes scikit-image. Accurate extraction fails closed when this runtime is absent or unqualified, while the explicit Phase 5F1 preview path remains available.

## Deferred roadmap work

Phase 6A intentionally does not implement Phase 6B topology/mesh refinement, Phase 6C final anatomical presentation, Phase 6D visualization-mode UX, Phase 6E fidelity/presentation profiles, Phase 6F exploded/group interaction, Phase 6G final deviation qualification, Phase 6H exports, or Phase 6I closure.

## Validation

Automated validation covers isolated-runtime qualification and fingerprint binding, native-resolution extraction, deterministic output, v2 binary integrity, Patient-LPS bounds/normals/winding, boundary-touching masks, reflected affines, a synthetic complex-mask regression where a minority of local gradient-normal comparisons disagree with an otherwise coherent global winding, malformed or changed artifacts, source immutability, legacy Phase 5F1 transport compatibility, browser v1/v2 decoding, full previous regression, compile/syntax checks, heavy-runtime isolation, patient-data Git safety, and diff whitespace.

Real-study qualification is separate and must be run against the already-qualified canonical label map before manual UI review. Manual review is limited to the new/affected behavior: accurate selected-structure surface appearance, alignment with the existing MPR/volume presentation, structure color/opacity/visibility synchronization, and a small backward-compatibility check of the legacy preview.

No clinical validation, diagnostic accuracy, regulatory approval, certified metrology, or model ranking is claimed.
