# Phase 6D1 — Volume-derived surfaces

Phase 6D1 adds a direct surface path from the immutable canonical patient volume, without TotalSegmentator and without a semantic label map.

## Qualified baseline

- Source: canonical patient volume (`derived/volume.npy`).
- Qualified modality: CT with preserved Hounsfield Unit semantics.
- Default bone baseline: 300 HU when that isovalue lies inside the source value range.
- Custom CT isovalues are accepted only when finite and strictly inside the observed canonical-volume range.
- Extraction: native-resolution Lewiner marching cubes at the requested isovalue.
- After the full Patient-LPS transform, numerically zero-area faces (`double area <= 1e-12 mm²`) are removed only when their fraction is at most `1e-4` (0.01%). The worker fails closed above that bound rather than hiding a larger extraction problem. No smoothing, hole filling, decimation, or anatomy invention is performed by this cleanup.
- Unreferenced vertices are compacted after the bounded face filter and vertex normals are recomputed from the retained Patient-LPS faces. Cleanup counts/fraction are preserved in worker report and surface provenance.
- Coordinates: full canonical array-index-to-Patient-LPS affine; output positions and normals are Patient LPS millimetres.
- Source volume remains immutable and is SHA256-bound before and after worker execution.
- Transport is dedicated `VXVS` volume-surface schema; it is intentionally distinct from segmentation `VXSF` transport and provenance.
- Generation is explicit. Loading a study or direct 3D volume never automatically builds a volume-derived surface.
- MRI is not silently interpreted with CT HU thresholds. A qualified MRI intensity-surface policy is outside this baseline.

The 6D1 viewer is a narrow **surface-only preview** in the existing patient-space scene after an explicit **Build Surface** action. The direct volume remains visible while the first surface is being built and is temporarily hidden only after a successful surface build; **Remove** restores the direct-volume visibility policy, including the user's existing opacity state. A failed or cancelled first build therefore leaves the direct volume visible. This deliberately avoids an implicit Combined presentation before Phase 6D2. Phase 6D2 visualization modes (Volume / Surface / Combined and source selection) are not enabled here. Phase 6E fidelity/presentation profiles, including the deferred view-independent lighting/material polish, are also not enabled here.

Study-truncation boundaries are preserved rather than artificially capped or anatomically invented. This is an intensity isosurface, not a semantic anatomical segmentation.

Clinical validation is not claimed.

## Real-data correction evidence

The first 300 HU Head/Neck qualification probe exposed 13 numerically degenerate faces out of 1,655,929 raw marching-cubes triangles (`0.000007850578`, about 0.000785%). Peak worker RSS was about 808 MB and the failure occurred in under two seconds, so the observed issue was geometric/numerical rather than a current OOM condition. The bounded cleanup above was added specifically to handle this tiny real-data artifact while failing closed if future data exceeds the documented fraction. The corrected real-study qualifier then passed with 830,890 final vertices, 1,655,916 final triangles, full Patient-LPS geometry, immutable canonical source volume, and no segmentation dependency.

Manual 300 HU review subsequently exposed an implicit volume-plus-surface overlap: the direct ray-marched volume remained visible after the volume-derived surface became ready, which visually appeared as a large rectangular/slab-like background and would have amounted to an uncontrolled Combined presentation. Boundary diagnostics found only 1,063 axis-0-min and 195 axis-0-max boundary-aligned triangles out of 1,655,929 raw triangles, with none on axes 1 or 2, so valid mesh geometry is preserved. The 6D1 surface-only preview correction changes viewer visibility state only; it does not remove boundary-touching anatomy or alter the qualified mesh.

Worker failures expose only an allow-listed bounded error code through the service; arbitrary worker exception text is not propagated to the HTTP client.
