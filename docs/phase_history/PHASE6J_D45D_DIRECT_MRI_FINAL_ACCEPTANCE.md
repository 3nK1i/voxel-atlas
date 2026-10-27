# Phase 6J-D4.5D — Direct MRI final acceptance and D4.5 closure

Authoritative base: `c688507` on `phase6-accurate-surfaces` (Phase 6J-D4.5C closed).

## Scope

Phase 6J-D4.5D is a **qualification-only acceptance step**. It does not redesign or modify the qualified Direct MR implementation from D4.5B/D4.5C. Production backend, browser UI, normalized-signal policy, Patient LPS geometry, CT/HU behavior, segmentation-derived MRI surfaces, and the canonical patient volume remain unchanged.

The purpose of D4.5D is to bind the Direct MR implementation to the real MRI study already used during D4.5B/C, quantify three representative normalized isovalues, verify source immutability and bounded geometry, preserve CT backward compatibility, and formalize the final manual visual/performance matrix before D4.5 is closed.

## Locked Direct MR semantics

- Source: immutable canonical MR volume.
- Source intensity units: `modality`.
- Surface intensity units: `normalized_signal`.
- Robust normalization: 2nd–98th percentile, clipped to [0, 1].
- Presentation smoothing: physical Gaussian sigma 0.75 mm.
- Coordinate system: Patient LPS millimetres.
- Segmentation required: no.
- Semantic identity: none.
- Clinical validation: not claimed.

The backend default remains **0.50**. The value **0.35** is recorded only as the manually preferred presentation value for the currently qualified T1 sample; it is not promoted to a universal MRI default.

## Automated qualification-only gate

Run:

```bash
export VOXELATLAS_SURFACE_PYTHON="$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python"
bash scripts/run_phase6j_d45d_checks.sh
```

The gate reruns the complete D4.5C UI/CT/mode regression, the D4 semantic-MRI regression, D4.5D acceptance contracts, syntax checks, patient-data Git safety, and an exact qualification-only delta guard. No production `backend/` or `web/` path may change in D4.5D.

Success ends with `PHASE6J_D45D_AUTOMATED_CHECKS_OK=YES`.

## Real MRI engineering qualification

Use the current qualified T1 MRI and the already-qualified isolated surface runtime:

```bash
.venv/bin/python scripts/qualify_phase6j_d45d_real_mri.py \
  --data-dir $PWD/data \
  --surface-python "$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python" \
  --manual-preferred-isovalue 0.35
```

The qualifier extracts Direct MR surfaces at normalized isovalues 0.35, 0.50, and 0.65. For each value it records wall time, vertex count, triangle count, payload size, bounds, surface/provenance identities, and cleanup statistics. It verifies that all surfaces remain within the qualified geometry budgets, are in Patient LPS, contain no invalid geometry, use normalized MRI signal, remain segmentation-independent, and do not modify the canonical source volume.

The three payload hashes must be distinct, proving that the normalized-signal control changes the extracted geometry rather than only changing presentation metadata.

The qualifier does **not** decide which threshold looks best. `--manual-preferred-isovalue 0.35` records the user's already-completed visual judgment for this sample only.

Success ends with:

```text
PHASE6J_D45D_REAL_MRI_QUALIFICATION_OK=YES
SOURCE_VOLUME=IMMUTABLE
GEOMETRY_CHAIN=PATIENT_LPS
DIRECT_MR_SEGMENTATION_REQUIRED=NO
DIRECT_MR_DEFAULT_ISOVALUE=0.50
MANUAL_PREFERRED_SAMPLE_ISOVALUE=0.35
MRI_INFERENCE=NOT_RUN
CLINICAL_VALIDATION=NOT_CLAIMED
```

## Final manual acceptance matrix

1. **MRI / Surface / 0.35** — confirm the smoothest useful whole-head/tissue presentation for the current T1 sample, with responsive orbit/zoom/pan.
2. **MRI / Surface / 0.50** — confirm the neutral backend baseline remains valid and visually distinct from 0.35.
3. **MRI / Surface / 0.65** — confirm the higher threshold remains functional even when the extracted boundary becomes more fragmented.
4. **MRI / Combined** — confirm canonical MRI volume and Direct MR surface coexist and remain aligned.
5. **MRI / Direct MR + segmentation** — confirm Direct MR can coexist with semantic Brain/Spinal Cord surfaces without changing their semantic identity or triggering new MRI inference.
6. **Mode round trip** — Volume → Surface → Combined → Volume must preserve state and must not trigger MRI segmentation solely because of mode changes.
7. **MRI modality truthfulness** — UI shows Direct MR / normalized signal, hides CT-only region visibility, and never uses HU semantics for MRI.
8. **CT backward sanity** — load a qualified CT study and confirm Direct CT remains available at the 300 HU baseline, CT region evidence remains available, and Surface/Combined behavior is unchanged.
9. **Performance observation** — record whether the real ~million-triangle Direct MR surface remains interactively usable on the target machine. D4.5D does not silently decimate the qualified geometry.
10. **Logs** — browser console and server log must show no unexpected errors. Explicit surface rebuild requests are expected when changing isovalue.

## Closure rule

D4.5 closes only when all three independent gates pass:

- `PHASE6J_D45D_AUTOMATED_CHECKS_OK=YES`;
- `PHASE6J_D45D_REAL_MRI_QUALIFICATION_OK=YES`;
- the final manual MRI + CT acceptance matrix is accepted.

Only then should the eight D4.5D qualification-only files be staged, reviewed, committed, and pushed. Three of those files are regression-harness maintenance updates: the legacy Phase 6J-B1 and Phase 6J-B2B cache-version assertions accept the already-qualified D4.5C cache suffix, and the Phase 6I-B2 segmentation-mode regression test now scopes its check to the modality-aware `ensureAutomaticDirectVolumeSurface` helper introduced by D4.5C instead of the retired CT-specific helper name. They do not change production behavior. Phase 6J-D5 workflow/lifecycle integration remains the next step. Clinical validation is not claimed.
