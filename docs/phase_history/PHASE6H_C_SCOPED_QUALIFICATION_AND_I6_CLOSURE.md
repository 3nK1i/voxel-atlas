# Phase 6H-C — scoped real-study technical qualification / I.6 closure candidate

Development branch: `phase6-accurate-surfaces`. Required pre-closure commit:
`44f5a59c50fc893f309769d1661120955b44f778` (6H-A harness). This
additive documentation and regression gate does not alter source studies,
label maps, surfaces, worker code, the application, UI, or production.

## What the evidence establishes

The local 6H-A preflight confirmed source/MPR binding, unmodified canonical
source artifacts, a selected CT label ROI within the 6G analysis budget, and
**acquisition-boundary contact**. A first execution under the lightweight
application Python was blocked by absent SciPy/scikit-image; a subsequent
import check and preflight under the existing dedicated surface Python passed.
The bounded real-study execution then produced separate accurate and refined
`sampled_evidence_only` reports, with unchanged source artifacts. The developer
reported a clean Git tree after execution. This is a *source-bound technical
qualification of one selected CT label and three selected MPR world planes*,
not a study-independent assurance for every label or acquired slice.

| Quantity, in millimeters unless stated | Accurate | Refined |
| --- | ---: | ---: |
| Largest **sampled** bidirectional 3D distance | 0.000 | 0.062 |
| Largest **sampled** axial contour distance | 0.000 | 0.072 |
| Largest **sampled** coronal contour distance | 0.000 | 0.114 |
| Largest **sampled** sagittal contour distance | 0.000 | 0.095 |

These are values **rounded to three decimals**, not exact zero-error claims,
clinical thresholds, independent anatomical ground truth, or full-surface
maxima. Each 3D direction sampled only 128 source triangles from roughly
240,000, approximately **0.0532%** of triangles per direction. Selected MPR
planes used 96 sampled contour segments per direction, not exhaustive slice
coverage. Sampling fractions are not continuous area-coverage guarantees.
No whole-surface Hausdorff distance, raster-overlay pixel equivalence, or
clinical validation was computed or claimed.

## Focused visual review and known limitations

The developer's local preview showed Surface and Combined presentations,
changing axial/coronal/sagittal slices, segmentation overlays, an isolated
skull, and a separate isolated first rib. In the final isolated skull view,
**Follow Directional Cut was disabled and all three clipping planes were
unchecked**; the frontal surface appeared coherent without a conspicuous
large displaced/detached piece. Earlier rotated views showed a superior
**open-looking scan-limited rim**. The scan-boundary contact is independently
reported by preflight; these screenshots do **not** prove globally open
mesh topology, complete cranial acquisition, absence of every small artifact,
or a pixel-exact mesh/overlay correspondence. Do not fabricate a closed skull
cap or imply tissue beyond the acquisition was scanned.

A visible grey rectangular sheet occurred only with the separate Direct CT
surface's full-geometry presentation and must not be attributed to the
segmentation mesh. With Direct CT disabled, the selected segmentation surface
could be inspected without that sheet. UI Fidelity/Presentation options are
*rendering profiles*, not Accurate/Refined mesh-quality selection. The current
UI did not provide a demonstrated side-by-side quality switch for the same
isolated label. Separate numerical evidence exists for both mesh qualities,
but **direct visual Accurate-vs-Refined equivalence remains unverified**.

A different rib label returned HTTP 422 for `refined`, then HTTP 200 for
`accurate`; the isolated rib remained visible in the preview. This supports
an **observed fallback** for that particular request, not proof of the reason
for refined unavailability, full fallback coverage, or fault-free processing.
The underlying 422 classification remains an explicit follow-up, not a
silent success or a reason to change the qualified skull geometry.

## Scoped closure disposition and handoff

Following a passing 6H-C synthetic/regression gate and exact-file review,
**Phase I.6 may close as a non-clinical, bounded research/prototype technical
milestone**: source-preserving Patient-LPS surface generation, existing UI
presentation/interaction, and sampled source-bound real-study fidelity evidence
have been exercised. This does *not* qualify an entire CT study, all 49
structures, the displayed full anatomy, MRI workflows, patient diagnosis,
clinical measurement, or all deployment environments. Production is untouched.

Known follow-ups are (1) locally classify the rib's refined HTTP 422 and retain
accurate fallback, (2) strengthen multi-region/multi-slice sampling if a
broader fidelity claim is later needed, (3) keep acquisition-limit semantics
explicit in future UI work, and (4) consider the separate Direct CT grey-sheet
presentation issue independently of segmentation geometry. Any MRI adapter
and broader roadmap decisions come **after** the scoped I.6 closure, as
previously agreed; no MRI qualification is inferred here.

No patient identifiers, source-data paths, labels.npy, DICOM, study hashes,
private logs, mesh payloads, or screenshots are included in this repository
change. The only intended change is this record, its read-only regression
runner, and its synthetic documentation-contract tests. A passing test run
**does not retroactively prove the unresolved visual or HTTP items**; it
confirms that the stated scope and prior automated contracts are preserved.
Do not deploy or auto-push as part of the verification script.
