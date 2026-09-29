# Phase 6J-C1 — MRI task/runtime qualification (non-executing)

Baseline: `phase6-accurate-surfaces` at `771b5ef5587e23abe22d4b704308ec9ba65775b7`.

This slice adds a **separate read-only total_mr runtime probe**. Its installed-task
class fingerprint must agree with the pinned 50 MRI labels. It verifies the
TotalSegmentator 2.18.0 Python API and CUDA visibility via an isolated child
interpreter; never reuses the CT `total` runtime report. The observed
`6774138e...` mapping fingerprint is the canonical JSON mapping SHA256 from
installed TotalSegmentator 2.18.0 (distinct from the B1 inspected AST snippet
fingerprint). Any mismatch fails closed.

**Runtime qualified is NOT execution ready.** No MRI weights have been
qualified, no VRAM adequacy or MRI-sequence suitability is established, and
there is no MRI provider registration, DICOM access, download, model execution,
CT changes, persisted study change, or claim of clinical fitness. The C0
inventory only found CT weight directories in the inspected locations;
other caches have not been exhaustively inspected. The RTX 2060 being visible
to CUDA does not demonstrate inference fits its 6 GiB VRAM.

Execute `PYTHON=.venv/bin/python bash scripts/run_phase6j_c1_checks.sh` on the
full repo; it includes the prior B2B/CT regressions. Run the read-only real
probe separately using the dedicated TotalSegmentator interpreter, without
modifying shell runtime configuration. Never enable `VOXELATLAS_SEGMENTATION_PYTHON`
for MRI merely because this probe passes. Do not commit or push before review.
