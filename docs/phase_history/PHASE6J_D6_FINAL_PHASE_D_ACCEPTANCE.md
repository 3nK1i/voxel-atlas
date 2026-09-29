# Phase 6J-D6 — Final Phase-D acceptance and closure

Base: `phase6-accurate-surfaces` at `cfbe6d7` after D5D integrated lifecycle acceptance.

## Scope

D6 is the final qualification and closure step for Phase 6J-D. It does not redesign or modify production reconstruction behavior. No `backend/` or `web/` production file belongs in the D6 delta unless a new defect is independently demonstrated and reviewed.

Phase D now has one continuous engineering acceptance chain:

- D2 qualified and persisted the already accepted `total_mr` result as an immutable canonical Patient-LPS label map without rerunning MRI inference.
- D3 exposed that persisted map through synchronized Patient-LPS MPR overlays.
- D4 exposed explicit segmentation-derived Brain / Spinal Cord 3D presentation while preserving the exact/reference geometry provenance anchor.
- D4.5 added Direct MR as a segmentation-independent normalized-signal isosurface over the immutable canonical MR volume while preserving Direct CT/HU behavior.
- D5 hardened cross-study stale-async ownership, same-study Direct/Semantic coexistence, non-destructive resident-geometry reuse, and the MRI → CT → MRI lifecycle.

Clinical validation is not claimed by Phase D.

## Final automated-gate composition

D6 deliberately does not replay historical/previous-step exact-delta guards whose allowed file sets belong to their own already-closed qualification steps.

- `scripts/run_phase6j_d45d_checks.sh` remains bound to the old D4.5D qualification-only delta and must not be replayed as a whole after later production changes.
- `scripts/run_phase6j_d5d_checks.sh` remains bound to the three D5D qualification-only files and therefore must not be replayed while the new D6 qualification files are present.

Instead, D6 composes the current production-relevant gates and focused acceptance contracts:

- full D5C lifecycle gate, which nests D5B and the current D4.5C + D4 regression chain;
- focused D5D integrated-acceptance contracts;
- D2 import-stage reporting regression in addition to the canonical-import contract already reached through the D4 chain;
- focused D4.5D acceptance contract plus read-only qualifier availability/safety checks;
- patient-data Git safety, syntax/compile checks, whitespace checks, and an exact D6 qualification-only delta guard.

The D6 automated gate must not run MRI model inference, must not perform a production MRI import, and must not alter the canonical patient volume or label map.

## Locked Phase-D semantics

- MRI semantic presentation remains source-bound to the accepted `totalsegmentator / total_mr` canonical label map.
- MRI MPR label sampling remains Patient-LPS and nearest-neighbor.
- MRI semantic 3D presentation remains segmentation-derived; the exact/reference surface stays the provenance anchor.
- Direct MR remains non-semantic, segmentation-independent, `normalized_signal`, robust 2nd–98th percentile normalization, physical Gaussian sigma 0.75 mm, and backend default isovalue 0.50.
- The manually preferred 0.35 isovalue remains sample-specific to the qualified T1 study and is not a universal default.
- Direct CT remains native HU with the established 300 HU baseline and CT-only region evidence.
- Volume / Surface / Combined mode changes remain presentation-only for resident geometry.
- MRI → CT → MRI study changes must not retain stale patient-scoped geometry or stale asynchronous completions.
- No normal presentation action authorizes or starts MRI segmentation inference.
- No Phase-D final acceptance step performs another production MRI import.

## Final manual acceptance

After the D6 automated gate passes, perform one final local smoke acceptance with MRI inference explicitly disabled:

1. Load the qualified Brain MR study and confirm MPR plus the persisted segmentation overlay are available.
2. Confirm semantic Brain / Spinal Cord surfaces and Direct MR can coexist in Surface and Combined.
3. Confirm Direct MR uses normalized signal, not HU; CT-only region visibility is absent; 0.50 remains the backend baseline and 0.35 remains only the qualified sample preference.
4. Exercise Volume → Surface → Combined → Volume without MRI segmentation starting and without destructive geometry loss.
5. Load the Head & Neck CT study and confirm no MRI geometry survives; Direct CT uses native HU, the 300 HU baseline and CT-only region visibility.
6. Return to Brain MR and confirm no CT geometry/HU controls survive, persisted MRI segmentation is rediscovered, and Direct MR + semantic presentation remains available.
7. Confirm the server/browser logs contain no unexpected errors, no MRI model-start request, and no production MRI-import operation.

This final smoke validates engineering integration only. It is not clinical validation or diagnostic approval.

## Closure rule

Phase 6J-D is closed only when:

- `PHASE6J_D6_CHECKS_OK=YES` and `TEST_RC=0`;
- the D6 qualification-only delta contains only the D6 documentation, runner and focused test;
- the final manual MRI → CT → MRI smoke is accepted;
- MRI inference is not rerun;
- production MRI import is not rerun;
- the D6 commit is pushed and HEAD equals `origin/phase6-accurate-surfaces` with a clean worktree.
