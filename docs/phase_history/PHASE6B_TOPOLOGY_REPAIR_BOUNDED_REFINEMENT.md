# Phase 6B — Topology repair and carefully bounded smoothing/decimation

## Status

Implementation candidate, corrected refinement algorithm version 2. Phase 6B is not closed until the complete automated regression, separate real-study qualification, manual refined-surface review, staged-state review, commit, and push are complete.

## Scope

Phase 6B refines the exact Phase 6A accurate Patient-LPS surface artifact without creating a second mask-to-mesh pipeline. The Phase 6A `accurate` artifact remains available and byte-immutable as the geometric reference. Phase 6B adds a `refined` derivative for presentation use.

This step is intentionally limited to:

- deterministic safe compact cleanup of degenerate/duplicate faces and unreferenced vertices on the derived working copy;
- strictly bounded local face-only repair when a tiny edge-topology anomaly can be removed without moving any surviving Patient-LPS vertex;
- explicit edge-manifold and vertex-fan-manifold validation;
- fixed, bounded Taubin smoothing;
- deterministic vertex-cluster decimation only when the repaired topology and geometric bounds remain valid;
- deterministic Patient-LPS winding/normals after refinement;
- immutable cryptographic binding back to the exact Phase 6A accurate surface;
- same surface service, API endpoint, v2 binary transport, study binding, and browser layer.

Phase 6B does **not** add final anatomical presentation (6C), visualization-mode UX (6D), profiles (6E), exploded/group views (6F), surface-to-mask deviation qualification (6G), or export (6H).

## Reference preservation

The API remains backward-compatible with `quality=accurate` as its default. The browser descriptor may prefer `quality=refined` for presentation, but the refined artifact records the exact Phase 6A reference surface ID, payload SHA256, provenance, reference geometry counts, refinement algorithm version, fixed policy, and scientific runtime fingerprint.

Repeated requests for the Phase 6A accurate surface before and after refinement must return byte-identical payloads and the same surface ID/SHA256. Topology repair is performed only on the derived Phase 6B working copy.

## Corrected topology model

Refinement algorithm version 2 distinguishes three states explicitly:

1. **Phase 6A accurate reference** — immutable, even if a tiny local topological defect is present.
2. **Phase 6B repaired topology baseline** — safe compact cleanup plus, only when all gates pass, zero-displacement local face-only repair.
3. **Final refined surface** — bounded smoothing/decimation that must preserve the repaired topology baseline exactly.

The final refined topology is therefore not required to reproduce a defective Euler signature from the Phase 6A reference. It must instead reproduce the validated repaired baseline after the repair operation has been fully recorded.

## Fixed bounded-refinement policy

The corrected Phase 6B policy is deliberately conservative and versioned:

- refinement: `bounded_taubin_vertex_clustering`;
- refinement algorithm version: 2;
- smoothing iterations: 2;
- Taubin lambda: 0.33;
- Taubin mu: -0.34;
- smoothing displacement cap: 0.25 × the minimum physical voxel-step lower bound;
- total refinement displacement cap: 0.80 × the minimum physical voxel-step lower bound;
- minimum final triangle retention relative to the exact Phase 6A triangle count: 70%;
- deterministic vertex-cluster candidate cell sizes in index units: 0.50, 0.65, 0.70, 0.80;
- local topology repair candidate-face budget: at most 12 implicated faces;
- local topology repair removal budget: at most 6 faces;
- local topology repair removed-face fraction: at most 0.0001 (0.01%);
- local topology repair removed-area fraction: at most 0.0001 (0.01%);
- local topology repair coordinate displacement: exactly 0 mm;
- repaired and final surfaces must have zero boundary edges, zero non-manifold edges, and zero disconnected vertex fans.

The physical voxel-step bound is derived conservatively from the minimum singular value of the full canonical index-to-Patient-LPS affine linear transform. This avoids assuming axis-aligned, diagonal, positive-only, or isotropic geometry.

A decimation candidate is accepted only if it:

1. stays within the total displacement bound;
2. retains at least 70% of the exact Phase 6A triangles;
3. preserves the repaired baseline component count, global Euler characteristic, per-component Euler-characteristic signature, boundary-edge count, non-manifold-edge count, and non-manifold vertex-fan count;
4. remains inside the canonical Patient-LPS voxel-cell envelope.

If no candidate satisfies every gate, Phase 6B keeps the valid smoothed repaired-baseline mesh instead of forcing decimation.

## Topology repair policy

The first derived cleanup may only:

- remove index-degenerate faces;
- remove zero-area faces;
- remove duplicate faces;
- remove unreferenced vertices.

If topology is already closed and vertex-manifold after this cleanup, no local topology repair occurs.

If edge anomalies remain, the local face-only repair is allowed only when all anomaly-touching candidates fit the fixed candidate budget. Candidate subsets are searched deterministically from the smallest removal count upward. A candidate is accepted only when every touched edge either remains two-manifold or disappears, all original edge anomalies are eliminated, the connected-component count is unchanged, the result has no boundary/non-manifold edges, the result has no disconnected vertex fan, face/area removal fractions stay within the fixed limits, and no surviving vertex coordinate is moved.

A vertex-only bow-tie/disconnected-fan defect with no safely removable edge anomaly is rejected rather than guessed. Broad anomalies, hole filling, component merging, remeshing, aggressive self-intersection repair, or anatomy-inventing topology changes are not performed in this step.

## Real-study correction rationale

The first real label-91 Phase 6B attempt exposed a topology condition absent from the synthetic fixtures. After safe compact cleanup, the accurate derived working copy contained two boundary edges and two non-manifold edges, with maximum edge incidence 3. A read-only feasibility probe found a deterministic face-only repair requiring exactly two additional face removals. The removed-face fraction was `0.000008319052`, removed area was `0.732421875 mm²`, removed-area fraction was `0.000005963439`, connected-component count remained 2, the repaired result had zero boundary/non-manifold edges, and topology-repair coordinate displacement was exactly `0.000000 mm`.

These diagnostic results are implementation evidence only. The corrected worker must still pass the formal separate real-study qualification before Phase 6B can close.

## Coordinate-system contract

All transported vertices, bounds, normals, and derived geometry remain in DICOM Patient LPS millimetres. The canonical complete affine remains authoritative. Boundary-touching anatomy remains valid at voxel-cell boundaries (`-0.5` and `N - 0.5` in canonical array-index coordinates).

## Runtime isolation

Phase 6B reuses the explicitly qualified isolated surface Python runtime introduced in Phase 6A. Heavy scientific dependencies remain outside FastAPI's lightweight startup/import path. The Phase 6B worker uses NumPy operations and validates the same runtime fingerprint as the accurate reference pipeline.

## Browser/API contract

- endpoint remains `/api/studies/latest/segmentation-surfaces/{label_id}`;
- API default remains `quality=accurate`;
- `quality=refined` returns the same v2 Patient-LPS binary media type;
- refinement/reference identity and bounded-geometry evidence remain part of the service/API contract;
- browser presentation may prefer the descriptor's `presentation_quality=refined`;
- Phase 6A accurate reference identity remains explicitly represented in the UI contract.

## Validation gates

Automated validation covers:

- focused Phase 6B unit/API/browser contracts;
- exact preservation of Phase 6A accurate artifacts;
- regression for the observed two-boundary/two-non-manifold-edge local anomaly pattern;
- integrated worker/backend acceptance of a repaired topology baseline;
- vertex-fan manifoldness using a closed edge-manifold bow-tie fixture;
- repaired-topology invariant preservation through smoothing/decimation;
- displacement and triangle-retention gates;
- boundary-touching Patient-LPS containment;
- deterministic refined payloads/provenance;
- Phase 6A, Phase 5G, and Phase 5F1 regressions;
- complete previous automated regression excluding only current Phase 6B tests and explicitly superseded historical assertions;
- Python/JavaScript/shell syntax;
- patient-data Git safety;
- heavy-runtime isolation;
- canonical source-label immutability;
- explicit later-phase roadmap-boundary checks that allow the literal `deferred_to_phase6g` provenance marker without mistaking it for Phase 6G implementation;
- whitespace/diff checks.

Real-study qualification is deliberately separate and must compare the refined artifact with the known Phase 6A accurate label-91 reference. It reports the post-compact reference anomalies, bounded topology repair evidence, repaired baseline, final manifoldness, triangle retention, displacement, performance, and immutable accurate-reference identity. Manual review is limited to refinement quality/alignment and directly affected interaction behavior.

## Claims boundary

Phase 6B is non-clinical visualization/engineering work. It does not claim clinical validation, diagnostic accuracy, certified metrology, or superiority/ranking of models or algorithms.
