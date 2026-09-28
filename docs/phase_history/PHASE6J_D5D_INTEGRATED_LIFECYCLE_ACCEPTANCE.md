# Phase 6J-D5D — Integrated MRI / CT lifecycle acceptance

Base: `phase6-accurate-surfaces` at `6211da1`.

## Scope

D5D is an integrated qualification/closure step for the already-implemented Phase 6J-D2 through D5 lifecycle. It does not redesign production behavior. No backend or web production file is modified by D5D.

The qualification composes the current D5C gate, which already nests D5B cross-study lifecycle protection, Direct-MR/Direct-CT regression, and the D4 semantic-MRI chain. D4 in turn covers the D3 MPR-overlay contract and D2 canonical MRI label-map import contract.

D5D also reuses the focused D4.5D acceptance contract directly. It deliberately does **not** invoke `scripts/run_phase6j_d45d_checks.sh` as a whole because that historical runner contains a qualification-only delta guard bound to the old D4.5D base `c688507`. Replaying that historical delta guard after legitimate D5B/D5C production changes would be an invalid acceptance criterion.

## Integrated acceptance contract

D5D must establish together that:

- the existing qualified MRI label-map import contract remains source-bound and Patient-LPS;
- persisted MRI MPR overlays remain tied to the active qualified map;
- semantic Brain / Spinal Cord surfaces remain segmentation-derived Patient-LPS presentation geometry;
- Direct MR remains normalized-signal, non-semantic and segmentation-independent;
- Direct CT remains HU-based with the existing 300 HU baseline and CT-only region semantics;
- MR → CT → MR switching preserves D5B stale-completion isolation;
- same-study Direct + semantic source coexistence preserves D5C non-destructive resident-geometry reuse;
- Volume / Surface / Combined remain presentation-only;
- presentation actions do not start MRI segmentation and do not perform a new production MRI import;
- clinical validation is not claimed.

## Automated gate

Run:

```bash
PYTHON=.venv/bin/python \
VOXELATLAS_SURFACE_PYTHON="$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python" \
  bash scripts/run_phase6j_d5d_checks.sh
```

Success ends with `PHASE6J_D5D_CHECKS_OK=YES` and `TEST_RC=0`.

## Manual closure

After the automated gate, D5D-C performs one final integrated local preview using the already-qualified MRI and CT resources:

1. MRI: confirm persisted MPR overlay, semantic Brain / Spinal Cord presentation and Direct MR coexistence.
2. Same-study: exercise Direct / Segmentation source toggles and Volume / Surface / Combined without destructive rebuilds.
3. Cross-study: switch MRI → CT → MRI and confirm no stale presentation survives.
4. CT: confirm Direct CT uses HU semantics, the 300 HU baseline and CT-only region visibility.
5. MRI return: confirm Direct MR normalized-signal semantics and absence of CT-only controls.
6. Confirm no MRI inference was started and no new production MRI import was performed.

D5D is an engineering lifecycle acceptance step. It does not constitute clinical validation.
