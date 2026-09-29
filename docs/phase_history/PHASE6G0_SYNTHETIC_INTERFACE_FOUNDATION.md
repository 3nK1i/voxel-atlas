# Phase 6G0 — synthetic interface-residual foundation (NOT 6G closure)

Baseline: `497e9f5f1e40346ae3e9476b2575d2cb8ce640f5` on `phase6-accurate-surfaces`.

Scope: additive, opt-in, read-only numerical helper and synthetic tests only. It is **not** connected to the workspace, production APIs, DICOM, or stored patient artifacts. The helper accepts an already-selected 3D *boolean* mask, its full array-index-to-Patient-LPS affine (for an ROI, pass the correctly translated ROI affine), and sample points already in Patient LPS. It does not read or mutate the canonical labels or any mesh buffers. It does not infer anatomy, evaluate model accuracy, or change the presentation profile.

Metric: `|trilinear(mask at P)-0.5| / ||gradient_LPS(trilinear mask at P)||`, in mm, for a nonzero local gradient. Virtual zero exterior makes half-voxel interfaces at acquisition boundaries explicit. The metric is a **first-order local residual proxy**, NOT an exact nearest-triangle/mask-boundary distance, a Dice score, or a medical acceptance criterion. Zero gradient is reported as undefined, never silently converted to zero. A zero residual at an accurate-surface vertex checks consistency with the 0.5 interface but cannot alone certify a mesh (sampling can miss defects).

Synthetic tests: anisotropic and oblique Patient-LPS affines, half-voxel volume boundary, known physical offset, read-only source, undefined gradients, and invalid input fail-closed. The tests never access patient data.

Next 6G increments: inspect canonical descriptor/worker service binding; add source-bound signed/unsigned **actual** bidirectional mask-interface-to-mesh distances in physical mm (including triangle interiors rather than just vertices), sampling coverage and tolerance reporting for anisotropic acquisitions, synchronized axial/coronal/sagittal MPR agreement, bounded runtime/memory, provenance and revision checks, and real-study qualification with no clinical claims. Do not use 6G0 as the final fidelity report or change smoothing limits on the strength of this local metric.
