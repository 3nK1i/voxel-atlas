# Phase 6J-D5C — Same-study Direct/Semantic surface lifecycle

## Scope

D5C hardens same-study presentation ownership after D5B isolated cross-study asynchronous state. It does not change Direct-MR normalization, CT HU extraction, Patient-LPS geometry, segmentation inference, label-map geometry, or clinical-validation claims.

## Inspection finding

The existing visualization controller already separates surface `available`, `resident`, and `selected` state. Both Direct and segmentation-derived layers expose presentation-only visibility controls, so hiding a source or switching Volume/Surface/Combined does not destroy resident geometry. Existing segmentation-surface synchronization also avoids re-fetching labels that are already resident.

One asymmetric same-study path remained: when a segmentation-derived surface was already resident and kept Surface or Combined active, selecting a non-resident Direct CT/MR source recorded user intent but did not prepare that Direct source until another mode request occurred. Segmentation selection already prepared its selected non-resident presentation source.

## D5C correction

Selecting `volume-derived` while Surface or Combined is already active now prepares the selected Direct source only when no Direct mesh is resident and the current same-study Direct descriptor is eligible. Selecting the Direct source while Volume mode is active remains intent-only; the existing Surface/Combined mode request remains the preparation trigger. A resident Direct surface is always reused.

The correction does not call the segmentation workflow, start MRI inference, clear semantic geometry, or rebuild a resident Direct source.

## Required invariants

- Direct and segmentation-derived surfaces may coexist for the same study.
- Source visibility and mode changes are presentation-only for resident geometry.
- Re-enabling a resident source reuses it without reconstruction.
- A non-resident Direct source selected while Surface/Combined is already active is prepared on demand.
- Volume mode source selection does not eagerly construct Direct geometry.
- Direct preparation never starts segmentation.
- Existing semantic activation does not rebuild resident Direct geometry.
- D5B cross-study stale-completion isolation remains intact.

## Acceptance

Focused D5C contracts and browser lifecycle simulation must pass together with the complete D5B gate, Direct-MR/CT regressions, semantic-MRI regressions, syntax checks, and `git diff --check`. Manual acceptance then exercises same-study Direct + segmentation source selection across Volume, Surface, and Combined without inference or unexpected rebuilds.
